# Audio Transcriber

Local audio/video transcription with speaker diarization, interactive viewer, and AI-powered post generation.

Built on WhisperX + PyAnnote for transcription/diarization, served through a Python HTTP viewer with real-time word highlighting.

## Requirements

- Python 3.10+
- NVIDIA GPU with CUDA (tested on RTX 3070 8GB) — or CPU (slower)
- ffmpeg
- Hugging Face token (for PyAnnote diarization models)
- Ollama (optional, for text cleanup and post generation)
- yt-dlp (optional, for YouTube downloads)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate  # or: source venv/bin/activate.fish
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add your HF_TOKEN
```

Accept PyAnnote model terms on Hugging Face (free):
- https://huggingface.co/pyannote/segmentation-3.0
- https://huggingface.co/pyannote/speaker-diarization-3.1

## Usage

### Quick start (transcribe + open viewer)

```bash
python3 run.py -i recording.mp4
```

### Just open the viewer (browse existing transcripts)

```bash
python3 run.py
```

### Transcribe a fragment

```bash
python3 run.py -i recording.mp4 -s 00:01:30 -d 45
```

### Transcribe without Ollama post-processing

```bash
python3 run.py -i recording.mp3 --no-ollama
```

### Direct transcription (without viewer)

```bash
python3 transcribe.py -i file.mp3 -m medium --use-ollama
```

Output goes to `./transcripts/` as `.json`, `.txt`, and `.md`.

## Viewer features

The web viewer runs at `http://localhost:8765` and provides:

- Click any word to jump to that timestamp
- Real-time word highlighting during playback (karaoke style)
- Editable speaker names (saved per-transcript in browser)
- Show/hide speakers panel
- Speed control (0.5x–2x)
- Keyboard: Space = play/pause, ←/→ = skip ±5s

## Post generation

Generate social media posts from transcripts using a local LLM (Ollama):

- Extracts verbatim quotes from the transcript
- Configurable speaker filter, person name, username, program
- Smart autocomplete for previously used names/programs
- Feedback system (👍/👎) that feeds into future generations
- Source highlighting in transcript

## Speaker Finder (YouTube)

Paste a YouTube URL + person's name → the app downloads audio, transcribes it, and uses the LLM to identify which SPEAKER_XX matches that person (with phonetic tolerance for Polish names).

## Live transcription

Real-time audio capture from any PulseAudio/PipeWire source (e.g., a specific app's audio output). Transcription grows live as you listen. Access at `/live`.

## File upload

Upload audio/video files directly through the web UI — no command line needed. Includes progress tracking.

## Key files

| File | Purpose |
|------|---------|
| `run.py` | Main entry point — transcribe + launch viewer |
| `viewer.py` | HTTP server + full web UI (single file) |
| `transcribe.py` | WhisperX transcription + diarization pipeline |
| `posty.py` | CLI post generation from transcript |
| `live_transcriber.py` | Live audio capture + streaming transcription |
| `posty.txt` | Example posts (used as style reference) |
| `.env` | Config: HF_TOKEN, OLLAMA_URL, OLLAMA_MODEL |

## CLI options (run.py)

| Flag | Description |
|------|-------------|
| `-i FILE` | Input audio/video (optional — without it, just opens viewer) |
| `-s TIME` | Start time for fragment (e.g. `90` or `00:01:30`) |
| `-d SEC` | Duration in seconds |
| `-m MODEL` | Whisper model: tiny, base, small, medium, large-v3 |
| `--no-ollama` | Skip Ollama text cleanup |
| `--device` | cuda or cpu |
| `--port` | Viewer port (default: 8765) |
| `--min-speakers N` | Hint for diarization |
| `--max-speakers N` | Hint for diarization |
