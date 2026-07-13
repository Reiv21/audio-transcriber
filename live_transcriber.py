#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
live_transcriber.py
───────────────────────────────────────────────────────────────────────────────
Backend module for live audio streaming transcription.
Captures audio from PulseAudio/PipeWire sources, processes in chunks via WhisperX,
and streams results back through a queue for SSE delivery.
"""

import gc
import io
import json
import os
import queue
import re
import struct
import subprocess
import sys
import threading
import time
import wave
from dataclasses import dataclass, field
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class AudioSource:
    id: str
    name: str
    media_name: str
    sink: str = ""


@dataclass
class ChunkResult:
    chunk_index: int
    time_offset: float
    duration: float
    segments: list = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# PulseAudio Source Listing
# ──────────────────────────────────────────────────────────────────────────────

def list_audio_sources() -> list[AudioSource]:
    """List available PulseAudio/PipeWire sink inputs (application audio streams)."""
    try:
        result = subprocess.run(
            ["pactl", "list", "sink-inputs"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode != 0:
            return []
        return parse_pactl_output(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def parse_pactl_output(output: str) -> list[AudioSource]:
    """Parse pactl list sink-inputs output into AudioSource objects."""
    sources = []
    current_id = None
    current_props = {}

    for line in output.split('\n'):
        line_stripped = line.strip()

        # New sink input block
        match = re.match(r'Sink Input #(\d+)', line_stripped)
        if match:
            # Save previous
            if current_id is not None:
                sources.append(AudioSource(
                    id=current_id,
                    name=current_props.get('application.name', f'Source #{current_id}'),
                    media_name=current_props.get('media.name', ''),
                    sink=current_props.get('sink', '')
                ))
            current_id = match.group(1)
            current_props = {}
            continue

        # Properties
        if '=' in line_stripped and current_id is not None:
            # Handle both "key = value" and "key = \"value\""
            kv_match = re.match(r'([\w.]+)\s*=\s*"?([^"]*)"?', line_stripped)
            if kv_match:
                current_props[kv_match.group(1)] = kv_match.group(2)

        # Sink field
        sink_match = re.match(r'Sink:\s*(\d+)', line_stripped)
        if sink_match and current_id is not None:
            current_props['sink'] = sink_match.group(1)

    # Don't forget the last one
    if current_id is not None:
        sources.append(AudioSource(
            id=current_id,
            name=current_props.get('application.name', f'Source #{current_id}'),
            media_name=current_props.get('media.name', ''),
            sink=current_props.get('sink', '')
        ))

    return sources



# ──────────────────────────────────────────────────────────────────────────────
# CaptureEngine — Audio capture from PulseAudio via parec
# ──────────────────────────────────────────────────────────────────────────────

class CaptureEngine:
    """Captures raw PCM audio from a PulseAudio sink-input via parec."""

    SAMPLE_RATE = 16000
    CHANNELS = 1
    SAMPLE_WIDTH = 2  # 16-bit
    BYTES_PER_SECOND = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH  # 32000

    def __init__(self, source_id: str):
        self.source_id = source_id
        self._process: Optional[subprocess.Popen] = None
        self._buffer = bytearray()
        self._buffer_lock = threading.Lock()
        self._running = False
        self._capture_thread: Optional[threading.Thread] = None
        self._all_pcm = bytearray()  # Full recording for MP3 save

    def start(self):
        """Spawn parec and start reading audio."""
        if self._running:
            return
        # Find the monitor source for the sink that this sink-input is connected to
        # We use parec with --monitor-stream to capture a specific sink-input
        self._process = subprocess.Popen(
            [
                "parec",
                "--format=s16le",
                "--rate=16000",
                "--channels=1",
                f"--monitor-stream={self.source_id}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._running = True
        self._capture_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._capture_thread.start()

    def _read_loop(self):
        """Continuously read PCM data from parec stdout."""
        try:
            while self._running and self._process and self._process.poll() is None:
                data = self._process.stdout.read(4096)
                if not data:
                    break
                with self._buffer_lock:
                    self._buffer.extend(data)
                    self._all_pcm.extend(data)
        except Exception:
            pass
        self._running = False

    def pause(self):
        """Kill parec process, retain buffer."""
        self._running = False
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

    def resume(self):
        """Re-spawn parec and continue."""
        self.start()

    def stop(self) -> bytes:
        """Stop capture, return remaining buffered data."""
        self.pause()
        with self._buffer_lock:
            remaining = bytes(self._buffer)
            self._buffer.clear()
        return remaining

    def get_chunk(self, duration_seconds: int) -> Optional[bytes]:
        """Get exactly duration_seconds worth of PCM data, or None if not enough yet."""
        needed = self.BYTES_PER_SECOND * duration_seconds
        with self._buffer_lock:
            if len(self._buffer) >= needed:
                chunk = bytes(self._buffer[:needed])
                del self._buffer[:needed]
                return chunk
        return None

    def get_available_bytes(self) -> int:
        """Return number of buffered bytes available."""
        with self._buffer_lock:
            return len(self._buffer)

    @property
    def is_source_alive(self) -> bool:
        return self._running and self._process is not None and self._process.poll() is None

    def get_all_pcm(self) -> bytes:
        """Return all captured PCM data for saving."""
        return bytes(self._all_pcm)



# ──────────────────────────────────────────────────────────────────────────────
# ChunkProcessor — WhisperX transcription of PCM chunks
# ──────────────────────────────────────────────────────────────────────────────

class ChunkProcessor:
    """Processes audio chunks through WhisperX. Keeps model loaded in VRAM."""

    def __init__(self, model_name: str = "small", device: str = "cuda", compute_type: str = "float16"):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def load_model(self):
        """Load WhisperX model into VRAM."""
        import whisperx
        import torch

        if self.device == "cuda" and not torch.cuda.is_available():
            print("[live] CUDA unavailable, falling back to CPU")
            self.device = "cpu"
            self.compute_type = "int8"

        # Clear GPU before loading
        if self.device == "cuda":
            gc.collect()
            torch.cuda.empty_cache()

        print(f"[live] Loading WhisperX model '{self.model_name}' on {self.device}...")
        self._model = whisperx.load_model(self.model_name, self.device, compute_type=self.compute_type)
        print(f"[live] Model loaded successfully.")

    def transcribe_chunk(self, pcm_bytes: bytes, sample_rate: int = 16000) -> dict:
        """Transcribe a PCM audio chunk. Returns segments with word-level timestamps.

        OOM retry logic:
        - First attempt uses batch_size=16 (default).
        - On GPU OOM: clear VRAM, retry exactly once with batch_size=1.
        - On second failure: raise RuntimeError (no further retries).
        - After every successful transcription: call torch.cuda.empty_cache() for VRAM cleanup.
        """
        import whisperx
        import torch
        import numpy as np

        if self._model is None:
            self.load_model()

        # Convert PCM bytes to float32 numpy array
        audio_array = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Normalize audio volume — boost quiet recordings
        peak = np.abs(audio_array).max()
        if peak > 0.001:
            # Normalize to ~0.7 peak (leaving headroom)
            gain = min(0.7 / peak, 10.0)  # Cap at 10x gain
            audio_array = audio_array * gain

        # Clear GPU cache before transcription to prevent OOM
        if self.device == "cuda":
            torch.cuda.empty_cache()

        # Transcribe with OOM retry logic
        try:
            result = self._model.transcribe(audio_array, batch_size=16, language="pl")
        except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
            # Only handle CUDA OOM errors — re-raise other RuntimeErrors
            if isinstance(e, RuntimeError) and "CUDA out of memory" not in str(e):
                raise

            # First OOM: clear GPU memory and retry with batch_size=1
            print(f"[live] GPU OOM on transcription, clearing cache and retrying with batch_size=1: {e}")
            gc.collect()
            torch.cuda.empty_cache()
            try:
                result = self._model.transcribe(audio_array, batch_size=1, language="pl")
            except (torch.cuda.OutOfMemoryError, RuntimeError) as e2:
                # Second failure — raise without further retries
                raise RuntimeError(
                    f"Transcription failed after OOM retry with batch_size=1: {e2}"
                ) from e2

        # Post-chunk VRAM cleanup — release GPU memory after every successful transcription
        if self.device == "cuda":
            torch.cuda.empty_cache()

        # Skip alignment to save VRAM (word-level timestamps are nice-to-have,
        # but alignment model takes ~1-2GB extra VRAM which causes OOM on 8GB cards)
        segments = result.get("segments", [])
        return {"segments": segments, "language": result.get("language", "pl")}

    def unload_model(self):
        """Free VRAM."""
        import torch
        if self._model is not None:
            del self._model
            self._model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("[live] Model unloaded, VRAM freed.")

    def check_vram(self) -> float:
        """Return available VRAM in GB (0 if CPU)."""
        try:
            import torch
            if torch.cuda.is_available():
                free, total = torch.cuda.mem_get_info()
                return free / (1024**3)
        except Exception:
            pass
        return 0.0



# ──────────────────────────────────────────────────────────────────────────────
# TranscriptAccumulator — Accumulates chunk results with continuous timestamps
# ──────────────────────────────────────────────────────────────────────────────

class TranscriptAccumulator:
    """Accumulates chunk results into a growing transcript."""

    def __init__(self):
        self.segments: list = []
        self.total_words: int = 0
        self.total_duration: float = 0.0

    def append_chunk(self, chunk_result: dict, time_offset: float) -> list:
        """Append chunk segments with adjusted timestamps. Returns the new segments."""
        new_segments = []
        for seg in chunk_result.get("segments", []):
            adjusted_seg = {
                "start": round((seg.get("start", 0) or 0) + time_offset, 3),
                "end": round((seg.get("end", 0) or 0) + time_offset, 3),
                "text": seg.get("text", "").strip(),
                "speaker": "SPEAKER_00",
                "words": []
            }
            for w in seg.get("words", []):
                adjusted_word = {
                    "word": w.get("word", ""),
                    "start": round((w.get("start", 0) or 0) + time_offset, 3),
                    "end": round((w.get("end", 0) or 0) + time_offset, 3),
                }
                if "score" in w:
                    adjusted_word["score"] = w["score"]
                adjusted_seg["words"].append(adjusted_word)
                self.total_words += 1

            if adjusted_seg["text"]:
                new_segments.append(adjusted_seg)
                self.segments.append(adjusted_seg)

            if adjusted_seg["end"] > self.total_duration:
                self.total_duration = adjusted_seg["end"]

        return new_segments

    def get_full_transcript(self) -> dict:
        """Return complete transcript in WhisperX-compatible format."""
        return {"segments": self.segments}

    def get_summary(self) -> dict:
        """Return session summary."""
        return {
            "duration": round(self.total_duration, 1),
            "chunks": 0,  # Will be set by SessionManager
            "words": self.total_words
        }

    def clear(self):
        self.segments = []
        self.total_words = 0
        self.total_duration = 0.0



# ──────────────────────────────────────────────────────────────────────────────
# SessionManager — Orchestrates live transcription session
# ──────────────────────────────────────────────────────────────────────────────

class SessionManager:
    """Manages the lifecycle of a live transcription session."""

    def __init__(self, transcript_dir: str = "./transcripts"):
        self.transcript_dir = transcript_dir
        self.state = "idle"  # idle | recording | paused | stopped
        self.session_id: Optional[str] = None
        self.source_id: Optional[str] = None
        self.model_name: str = "small"
        self.chunk_duration: int = 15

        self._capture: Optional[CaptureEngine] = None
        self._processor: Optional[ChunkProcessor] = None
        self._accumulator = TranscriptAccumulator()
        self._event_queue: queue.Queue = queue.Queue()

        self._capture_thread: Optional[threading.Thread] = None
        self._process_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()

        self._start_time: float = 0
        self._recording_duration: float = 0
        self._pause_start: float = 0
        self._chunks_completed: int = 0
        self._chunks_processing: int = 0
        self._error: Optional[str] = None

    def start_session(self, source_id: str, model_name: str = "small",
                      chunk_duration: int = 15, device: str = "cuda") -> str:
        """Start a new live session. Capture starts IMMEDIATELY, model loads in background."""
        if self.state != "idle":
            raise RuntimeError("Session already active")

        self.session_id = f"live_{int(time.time())}"
        self.source_id = source_id
        self.model_name = model_name
        self.chunk_duration = max(10, min(30, chunk_duration))
        self.state = "recording"
        self._start_time = time.time()
        self._recording_duration = 0
        self._chunks_completed = 0
        self._chunks_processing = 0
        self._error = None
        self._stop_event.clear()
        self._pause_event.clear()
        self._accumulator.clear()

        # Initialize capture engine and START IMMEDIATELY
        self._capture = CaptureEngine(source_id)
        self._capture.start()

        # Initialize processor (model will load in processing thread on first chunk)
        self._processor = ChunkProcessor(model_name=model_name, device=device)

        # Start processing loop in background (model loads lazily on first chunk)
        self._process_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self._process_thread.start()

        self._emit_status()
        return self.session_id

    def pause_session(self):
        """Pause audio capture."""
        if self.state != "recording":
            return
        self.state = "paused"
        self._pause_start = time.time()
        self._pause_event.set()
        if self._capture:
            self._capture.pause()
        self._emit_status()

    def resume_session(self):
        """Resume capture."""
        if self.state != "paused":
            return
        # Account for pause duration
        pause_dur = time.time() - self._pause_start
        self.state = "recording"
        self._pause_event.clear()
        if self._capture:
            self._capture.resume()
        self._emit_status()

    def stop_session(self) -> dict:
        """Stop session, finalize, return summary."""
        if self.state == "idle" or self.state == "stopped":
            return self.get_summary()

        self.state = "stopped"
        self._stop_event.set()

        # Stop capture
        remaining = b""
        if self._capture:
            remaining = self._capture.stop()

        # Process remaining audio if substantial (at least 2 seconds)
        if remaining and len(remaining) > CaptureEngine.BYTES_PER_SECOND * 2:
            try:
                self._chunks_processing += 1
                self._emit_status()
                result = self._processor.transcribe_chunk(remaining)
                time_offset = self._recording_duration
                new_segs = self._accumulator.append_chunk(result, time_offset)
                self._recording_duration += len(remaining) / CaptureEngine.BYTES_PER_SECOND
                self._chunks_completed += 1
                self._chunks_processing -= 1
                if new_segs:
                    self._emit_event("chunk", {
                        "chunk_index": self._chunks_completed,
                        "time_offset": time_offset,
                        "segments": new_segs
                    })
            except Exception as e:
                print(f"[live] Error processing final chunk: {e}")

        # Unload model
        if self._processor:
            self._processor.unload_model()

        summary = self.get_summary()
        self._emit_event("session_ended", summary)
        return summary

    def save_transcript(self, filename: str) -> dict:
        """Save transcript as JSON + audio as WAV to transcripts dir."""
        os.makedirs(self.transcript_dir, exist_ok=True)

        # Clean filename
        safe_name = re.sub(r'[^\w\-]', '_', filename)
        json_path = os.path.join(self.transcript_dir, f"{safe_name}.json")
        audio_path = os.path.join(self.transcript_dir, f"{safe_name}.wav")

        # Check collision
        if os.path.exists(json_path):
            return {"error": "file_exists", "path": json_path}

        # Save JSON
        transcript = self._accumulator.get_full_transcript()
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(transcript, f, indent=2, ensure_ascii=False)

        # Save audio as WAV
        if self._capture:
            pcm_data = self._capture.get_all_pcm()
            if pcm_data:
                with wave.open(audio_path, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(pcm_data)

        return {"status": "success", "json_path": json_path, "audio_path": audio_path}

    def get_status(self) -> dict:
        """Return current session status."""
        elapsed = 0
        if self.state == "recording" and self._start_time:
            elapsed = self._recording_duration + (time.time() - self._start_time - self._recording_duration)
        elif self.state in ("paused", "stopped"):
            elapsed = self._recording_duration

        return {
            "state": self.state,
            "session_id": self.session_id,
            "duration": round(self._recording_duration, 1),
            "elapsed": round(elapsed, 1),
            "chunks_completed": self._chunks_completed,
            "chunks_processing": self._chunks_processing,
            "total_words": self._accumulator.total_words,
            "error": self._error,
            "model": self.model_name,
            "chunk_duration": self.chunk_duration,
        }

    def get_summary(self) -> dict:
        summary = self._accumulator.get_summary()
        summary["chunks"] = self._chunks_completed
        summary["duration"] = round(self._recording_duration, 1)
        return summary

    def get_event(self, timeout: float = 1.0) -> Optional[dict]:
        """Get next SSE event from queue (blocking with timeout)."""
        try:
            return self._event_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def reset(self):
        """Reset to idle state for a new session."""
        if self.state != "stopped" and self.state != "idle":
            self.stop_session()
        self.state = "idle"
        self.session_id = None
        self._capture = None
        self._processor = None
        self._accumulator.clear()

    def reset_to_idle(self):
        """Full cleanup: unload model, stop capture, clear all state.
        
        Transitions to 'idle' so that a new start_session() call works
        without restarting the application. Safe to call from any state.
        """
        # Unload model to free VRAM
        if self._processor:
            try:
                self._processor.unload_model()
            except Exception as e:
                print(f"[live] Error unloading model during reset: {e}")

        # Stop audio capture
        if self._capture:
            try:
                self._capture.stop()
            except Exception as e:
                print(f"[live] Error stopping capture during reset: {e}")

        # Clear transcript accumulator
        self._accumulator.clear()

        # Reset state to idle
        self.state = "idle"
        self.session_id = None
        self._capture = None
        self._processor = None

        # Clear threading events so they don't block a future session
        self._stop_event.clear()
        self._pause_event.clear()

    # ── Internal ──────────────────────────────────────────────────────────

    def _processing_loop(self):
        """Background thread: loads model, then waits for chunks and processes them.

        Error handling:
        - Per-chunk: on transcription failure after retry, skip chunk, advance
          timestamps, emit recoverable error, continue with next chunk.
        - Outer catch-all: on unhandled exception, emit non-recoverable error,
          stop session and reset to idle so user can start a new session.
        - Source death: detect via is_source_alive, pause + emit error event.
        """
        # Load model on first iteration (lazy — allows capture to start immediately)
        model_loaded = False

        try:
            while not self._stop_event.is_set():
                # If paused, wait
                if self._pause_event.is_set():
                    time.sleep(0.2)
                    continue

                if self._capture is None:
                    break

                # Check if source died
                if not self._capture.is_source_alive and self.state == "recording":
                    self._error = "Źródło audio zostało utracone"
                    self.pause_session()
                    self._emit_event("error_event", {"message": self._error, "recoverable": True})
                    continue

                # Try to get a full chunk
                chunk = self._capture.get_chunk(self.chunk_duration)
                if chunk is None:
                    time.sleep(0.3)
                    continue

                # Load model on first chunk (lazy loading)
                if not model_loaded:
                    self._emit_event("status", {**self.get_status(), "message": "Ładowanie modelu WhisperX..."})
                    try:
                        self._processor.load_model()
                        model_loaded = True
                    except Exception as e:
                        self._error = f"Nie udało się załadować modelu: {e}"
                        self._emit_event("error_event", {"message": self._error, "recoverable": False})
                        self.state = "stopped"
                        return

                # Process chunk — per-chunk error handling
                self._chunks_processing += 1
                self._emit_status()

                try:
                    time_offset = self._recording_duration
                    result = self._processor.transcribe_chunk(chunk)
                    chunk_duration_actual = len(chunk) / CaptureEngine.BYTES_PER_SECOND
                    self._recording_duration += chunk_duration_actual
                    new_segs = self._accumulator.append_chunk(result, time_offset)
                    self._chunks_completed += 1
                    self._chunks_processing -= 1

                    if new_segs:
                        self._emit_event("chunk", {
                            "chunk_index": self._chunks_completed,
                            "time_offset": time_offset,
                            "segments": new_segs
                        })
                    self._emit_status()

                except Exception as e:
                    # Chunk failed after retry — skip it, advance timestamps, continue
                    self._chunks_processing -= 1
                    chunk_index = self._chunks_completed + 1
                    err_msg = f"Błąd transkrypcji porcji #{chunk_index}: {str(e)}"
                    print(f"[live] {err_msg}")
                    self._emit_event("error_event", {
                        "message": err_msg,
                        "recoverable": True,
                        "skipped_chunk": chunk_index
                    })
                    # Advance recording duration so subsequent timestamps stay correct
                    self._recording_duration += len(chunk) / CaptureEngine.BYTES_PER_SECOND
                    self._chunks_completed += 1
                    continue

        except Exception as e:
            # Unhandled exception (not chunk-related) — fatal error recovery
            err_msg = f"Nieoczekiwany błąd w pętli przetwarzania: {str(e)}"
            print(f"[live] FATAL: {err_msg}")
            self._error = err_msg
            self._emit_event("error_event", {
                "message": err_msg,
                "recoverable": False
            })
            # Stop session and reset to idle for clean recovery
            try:
                self.stop_session()
            except Exception:
                pass
            try:
                self.reset_to_idle()
            except Exception:
                # If reset_to_idle is not yet implemented, fall back to basic reset
                self.state = "idle"

    def _emit_event(self, event_type: str, data: dict):
        """Push event to SSE queue."""
        self._event_queue.put({"event": event_type, "data": data})

    def _emit_status(self):
        """Push a status event."""
        self._emit_event("status", self.get_status())


# ── Singleton instance (one session at a time) ────────────────────────────────
_session_manager: Optional[SessionManager] = None


def get_session_manager(transcript_dir: str = "./transcripts") -> SessionManager:
    """Get or create the global SessionManager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(transcript_dir=transcript_dir)
    return _session_manager
