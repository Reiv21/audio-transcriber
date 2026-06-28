#!/usr/bin/env python3
import os
import sys
import argparse
import json
import gc
from datetime import timedelta
import requests
from dotenv import load_dotenv

# Wczytanie zmiennych środowiskowych z .env
load_dotenv()

def format_timestamp(seconds: float) -> str:
    """Formatowanie sekund do postaci [HH:MM:SS]."""
    td = timedelta(seconds=int(seconds))
    return f"[{str(td)}]"

def format_timestamp_ms(seconds: float) -> str:
    """Formatowanie sekund do postaci HH:MM:SS.mmm."""
    ms = int((seconds - int(seconds)) * 1000)
    td = timedelta(seconds=int(seconds))
    return f"{str(td)}.{ms:03d}"

def clean_gpu_memory():
    """Czyszczenie pamięci VRAM (bardzo ważne na kartach z 8GB VRAM)."""
    try:
        import torch
        gc.collect()
        torch.cuda.empty_cache()
    except ImportError:
        pass

def transcribe_and_diarize(
    audio_path: str,
    hf_token: str,
    model_name: str = "medium",
    device: str = "cuda",
    compute_type: str = "float16",
    min_speakers = None,
    max_speakers = None,
    batch_size: int = 4,
    initial_prompt: str = None
):
    """Główna funkcja transkrypcji i podziału na mówców za pomocą WhisperX."""
    print("[-] Ładowanie WhisperX...")
    import whisperx
    import torch

    # Sprawdzenie dostępności CUDA
    if device == "cuda" and not torch.cuda.is_available():
        print("[!] Ostrzeżenie: CUDA jest niedostępne. Przełączam na CPU.")
        device = "cpu"
        compute_type = "int8"

    print(f"[*] Wybrane urządzenie: {device.upper()} (Precyzja obliczeń: {compute_type})")
    
    # Krok 1: Wczytanie pliku audio
    print(f"[-] Wczytywanie pliku audio: {audio_path}")
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Nie znaleziono pliku: {audio_path}")
    
    audio = whisperx.load_audio(audio_path)

    # Krok 2: Transkrypcja podstawowa (Whisper)
    print(f"[-] Krok 1/4: Transkrypcja Whisper (model: {model_name})...")
    # initial_prompt podpowiada modelowi nazwy własne i kontekst (poprawia nazwiska)
    asr_options = {}
    if initial_prompt:
        asr_options["initial_prompt"] = initial_prompt
        print(f"[*] Używam podpowiedzi (initial_prompt) dla lepszego rozpoznawania nazw")
    try:
        model = whisperx.load_model(model_name, device, compute_type=compute_type,
                                    asr_options=asr_options if asr_options else None)
    except TypeError:
        # Starsza wersja whisperx bez asr_options
        model = whisperx.load_model(model_name, device, compute_type=compute_type)
    result = model.transcribe(audio, batch_size=batch_size)
    
    # Usunięcie modelu transkrypcji w celu zwolnienia pamięci VRAM
    print("[-] Zwalnianie pamięci VRAM po transkrypcji...")
    del model
    clean_gpu_memory()

    # Krok 3: Dopasowanie tekstu do osi czasu (Alignment)
    language_code = result["language"]
    print(f"[-] Krok 2/4: Wyrównywanie czasu (Alignment) dla języka: '{language_code}'...")
    try:
        model_a, metadata = whisperx.load_align_model(language_code=language_code, device=device)
        result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
        del model_a
        clean_gpu_memory()
    except Exception as e:
        print(f"[!] Błąd podczas wyrównywania czasu (Alignment): {e}")
        print("[!] Kontynuowanie z niewyrównaną transkrypcją...")

    # Krok 4: Diaryzacja (Speaker Diarization)
    print("[-] Krok 3/4: Podział na mówców (Diarization) za pomocą PyAnnote...")
    if not hf_token:
        print("[!] Błąd: Brak tokenu Hugging Face (HF_TOKEN) w pliku .env.")
        print("[!] Podział na mówców zostanie pominięty. Otrzymasz samą transkrypcję.")
        return result, False

    try:
        from whisperx.diarize import DiarizationPipeline
        diarize_model = DiarizationPipeline(token=hf_token, device=device)
        diarize_segments = diarize_model(audio, min_speakers=min_speakers, max_speakers=max_speakers)
        
        # Krok 5: Dopasowanie mówców do konkretnych słów i segmentów
        print("[-] Krok 4/4: Przypisywanie mówców do słów...")
        result = whisperx.assign_word_speakers(diarize_segments, result)
        
        del diarize_model
        clean_gpu_memory()
        diarized = True
    except Exception as e:
        print(f"[!] Błąd podczas diaryzacji (PyAnnote): {e}")
        print("[!] Upewnij się, że zaakceptowałeś warunki modeli pyannote na Hugging Face i masz poprawny token.")
        print("[!] Kontynuowanie bez podziału na mówców...")
        diarized = False

    if diarized:
        result = smooth_word_speakers(result)
        result = split_segments_by_speaker(result)

    return result, diarized

def load_name_corrections(path):
    """Wczytuje słownik korekt z pliku. Format: 'błędna forma=poprawna forma' per linia."""
    corrections = {}
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                wrong, right = line.split("=", 1)
                wrong = wrong.strip()
                right = right.strip()
                if wrong and right:
                    corrections[wrong] = right
    return corrections

def apply_name_corrections(result, corrections):
    """Stosuje słownik korekt nazw własnych do tekstu segmentów i słów."""
    if not corrections:
        return result

    import re as _re

    # Skompiluj wzorce raz
    patterns = [(_re.compile(r'\b' + _re.escape(w) + r'\b', _re.IGNORECASE), r) for w, r in corrections.items()]

    def correct_text(text):
        for pat, right in patterns:
            text = pat.sub(right, text)
        return text

    count = 0
    for seg in result.get("segments", []):
        original = seg.get("text", "")
        corrected = correct_text(original)
        if corrected != original:
            count += 1
        seg["text"] = corrected
        for w in seg.get("words", []):
            w["word"] = correct_text(w.get("word", ""))

    if count:
        print(f"[+] Korekta nazw: poprawiono tekst w {count} segmentach")
    return result

def smooth_word_speakers(result):
    """Wygładza przypisanie mówców: naprawia pojedyncze słowa błędnie przypisane
    na granicach wypowiedzi (np. wtrącenia, końcówki zdań). Jeśli pojedyncze słowo
    ma innego mówcę niż oba sąsiednie słowa o tym samym mówcy — przypisz je sąsiadom."""
    # Zbierz płaską listę wszystkich słów z odniesieniem do segmentu
    all_words = []
    for seg in result.get("segments", []):
        seg_spk = seg.get("speaker", "UNKNOWN")
        for w in seg.get("words", []):
            all_words.append(w)

    if len(all_words) < 3:
        return result

    # Pass 1: napraw izolowane pojedyncze słowa (A B A -> A A A)
    changed = 0
    for i in range(1, len(all_words) - 1):
        prev_spk = all_words[i-1].get("speaker")
        cur_spk = all_words[i].get("speaker")
        next_spk = all_words[i+1].get("speaker")
        if prev_spk and prev_spk == next_spk and cur_spk != prev_spk:
            all_words[i]["speaker"] = prev_spk
            changed += 1

    # Pass 2: napraw izolowane pary na granicach (krótkie wtrącenia 2 słów)
    for i in range(1, len(all_words) - 2):
        prev_spk = all_words[i-1].get("speaker")
        s1 = all_words[i].get("speaker")
        s2 = all_words[i+1].get("speaker")
        after = all_words[i+2].get("speaker")
        if prev_spk and prev_spk == after and s1 == s2 and s1 != prev_spk:
            all_words[i]["speaker"] = prev_spk
            all_words[i+1]["speaker"] = prev_spk
            changed += 1

    if changed:
        print(f"[+] Wygładzanie mówców: poprawiono {changed} granic wypowiedzi")
    return result

def split_segments_by_speaker(result):
    """Post-processing: rozdziela segmenty gdzie WhisperX przypisał słowa do różnych mówców."""
    new_segments = []
    for seg in result.get("segments", []):
        words = seg.get("words", [])
        if not words or len(words) < 2:
            new_segments.append(seg)
            continue
        
        # Check if all words have the same speaker
        speakers_in_seg = set()
        for w in words:
            spk = w.get("speaker", seg.get("speaker", "UNKNOWN"))
            speakers_in_seg.add(spk)
        
        if len(speakers_in_seg) <= 1:
            new_segments.append(seg)
            continue
        
        # Split segment at speaker boundaries
        current_speaker = words[0].get("speaker", seg.get("speaker", "UNKNOWN"))
        current_words = [words[0]]
        
        for w in words[1:]:
            w_speaker = w.get("speaker", seg.get("speaker", "UNKNOWN"))
            if w_speaker != current_speaker:
                # Emit current sub-segment
                sub_seg = {
                    "start": current_words[0].get("start", seg["start"]),
                    "end": current_words[-1].get("end", seg["end"]),
                    "text": " ".join(w.get("word", "") for w in current_words),
                    "speaker": current_speaker,
                    "words": current_words
                }
                new_segments.append(sub_seg)
                current_speaker = w_speaker
                current_words = [w]
            else:
                current_words.append(w)
        
        # Emit last sub-segment
        if current_words:
            sub_seg = {
                "start": current_words[0].get("start", seg["start"]),
                "end": current_words[-1].get("end", seg["end"]),
                "text": " ".join(w.get("word", "") for w in current_words),
                "speaker": current_speaker,
                "words": current_words
            }
            new_segments.append(sub_seg)
    
    result["segments"] = new_segments
    print(f"[+] Post-processing diaryzacji: {len(result['segments'])} segmentów (po rozdzieleniu)")
    return result

def process_with_ollama(transcript_text: str, ollama_url: str, model_name: str) -> str:
    """Formatowanie i poprawianie tekstu za pomocą lokalnego modelu LLM (Ollama)."""
    print(f"[-] Krok opcjonalny: Post-processing transkrypcji za pomocą Ollama (model: {model_name})...")
    
    prompt = f"""
Jesteś profesjonalnym edytorem transkrypcji. Poniżej znajduje się surowa transkrypcja z podziałem na mówców (Speaker 0, Speaker 1 itd.).
Twoim zadaniem jest ulepszenie tego tekstu bez zmieniania sensu wypowiedzi:
1. Popraw oczywiste błędy gramatyczne, interpunkcyjne oraz literówki.
2. Usuń dźwięki namysłu (np. "eee", "yyy", "uhm"), powtórzenia słów wynikające z zająknięć.
3. Podziel wypowiedzi na logiczne akapity, jeśli są bardzo długie.
4. Zachowaj oznaczenia mówców (np. **Speaker 0:**) na początku każdej wypowiedzi.
5. Jeśli z kontekstu rozmowy wynika, jak mówcy mają na imię (np. ktoś mówi "Cześć Janek"), możesz zamienić oznaczenia typu "Speaker 0" na imię mówcy (np. "**Janek:**").
6. Zwróć tylko poprawiony tekst transkrypcji. Nie pisz wstępów ani komentarzy.

Oto tekst do poprawy:
{transcript_text}
"""
    
    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False
            },
            timeout=180
        )
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            print(f"[!] Błąd Ollama: Kod statusu HTTP {response.status_code}")
            return ""
    except Exception as e:
        print(f"[!] Błąd połączenia z Ollama: {e}")
        return ""

def generate_summary_with_ollama(transcript_text: str, ollama_url: str, model_name: str) -> str:
    """Generowanie podsumowania rozmowy za pomocą Ollama."""
    print("[-] Generowanie podsumowania za pomocą Ollama...")
    
    prompt = f"""
Na podstawie poniższej transkrypcji rozmowy, stwórz zwięzłe podsumowanie w języku polskim w formacie Markdown:
1. Główne tematy rozmowy (w punktach).
2. Najważniejsze wnioski lub ustalenia.
3. Lista zadań / akcji do wykonania (Action Items) jeśli występują.

Transkrypcja:
{transcript_text}
"""
    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False
            },
            timeout=180
        )
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            print(f"[!] Błąd Ollama podczas podsumowania: Kod statusu HTTP {response.status_code}")
            return ""
    except Exception as e:
        print(f"[!] Błąd połączenia z Ollama (podsumowanie): {e}")
        return ""

def save_results(result, diarized: bool, output_dir: str, base_filename: str):
    """Zapis wyników do plików TXT, JSON oraz MD."""
    os.makedirs(output_dir, exist_ok=True)
    
    txt_path = os.path.join(output_dir, f"{base_filename}.txt")
    json_path = os.path.join(output_dir, f"{base_filename}.json")
    md_path = os.path.join(output_dir, f"{base_filename}.md")

    # 1. Zapis do JSON (pełna struktura)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"[+] Zapisano pełne dane do pliku: {json_path}")

    # 2. Tworzenie formatu tekstowego
    txt_lines = []
    current_speaker = None
    
    for segment in result["segments"]:
        start_time = format_timestamp(segment.get("start", 0))
        speaker = segment.get("speaker", "Nieznany Mówca") if diarized else "Mówca"
        text = segment.get("text", "").strip()
        
        if speaker != current_speaker:
            txt_lines.append(f"\n{start_time} {speaker}:")
            current_speaker = speaker
        
        txt_lines.append(f"  {text}")

    txt_content = "\n".join(txt_lines).strip()
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt_content)
    print(f"[+] Zapisano prosty tekst do pliku: {txt_path}")

    # 3. Tworzenie podstawowego pliku Markdown
    md_lines = [f"# Transkrypcja: {base_filename}\n"]
    current_speaker = None
    
    for segment in result["segments"]:
        start_time = format_timestamp(segment.get("start", 0))
        speaker = segment.get("speaker", "Mówca") if diarized else "Mówca"
        text = segment.get("text", "").strip()
        
        if speaker != current_speaker:
            md_lines.append(f"\n### **{speaker}** *({start_time.strip('[]')})*")
            current_speaker = speaker
        
        md_lines.append(f"{text} ")

    md_content = "\n".join(md_lines)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[+] Zapisano dokument Markdown do pliku: {md_path}")
    
    return txt_content, md_content

def main():
    parser = argparse.ArgumentParser(description="Lokalna transkrypcja audio/video z podziałem na mówców")
    parser.add_argument("-i", "--input", required=True, help="Ścieżka do pliku audio (mp3, wav) lub wideo (mp4, mkv)")
    parser.add_argument("-o", "--output-dir", default="./transcripts", help="Katalog wyjściowy dla transkrypcji (domyślnie: ./transcripts)")
    parser.add_argument("-m", "--model", default="medium", help="Model Whisper (np. tiny, base, small, medium, large-v3). Domyślnie: medium")
    parser.add_argument("-d", "--device", default="cuda", help="Urządzenie obliczeniowe: cuda lub cpu (domyślnie: cuda)")
    parser.add_argument("-c", "--compute-type", default="float16", help="Typ obliczeń: float16, float32, int8 (domyślnie: float16)")
    parser.add_argument("-b", "--batch-size", type=int, default=4, help="Rozmiar wsadu (batch size) do transkrypcji (mniejsza wartość = mniejsze zużycie VRAM, domyślnie: 4)")
    parser.add_argument("--min-speakers", type=int, default=None, help="Minimalna oczekiwana liczba mówców (opcjonalnie)")
    parser.add_argument("--max-speakers", type=int, default=None, help="Maksymalna oczekiwana liczba mówców (opcjonalnie)")
    parser.add_argument("--use-ollama", action="store_true", help="Użyj lokalnego modelu Ollama do ulepszenia tekstu i podsumowania")
    parser.add_argument("--initial-prompt", default=None, help="Podpowiedź dla Whispera — lista nazwisk/nazw własnych poprawiająca rozpoznawanie (np. 'Dorota Spyrka, Adrian Zandberg')")
    parser.add_argument("--names-file", default="names.txt", help="Plik ze słownikiem korekt nazw (format: błędna=poprawna), domyślnie names.txt")
    
    args = parser.parse_args()

    # Wczytanie tokenu z .env lub zmiennych środowiskowych
    hf_token = os.getenv("HF_TOKEN")
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3")

    # Sprawdzenie pliku wejściowego
    if not os.path.exists(args.input):
        print(f"[!] Błąd: Plik '{args.input}' nie istnieje!")
        sys.exit(1)

    base_name = os.path.splitext(os.path.basename(args.input))[0]

    try:
        # 1. Transkrypcja i diaryzacja
        result, diarized = transcribe_and_diarize(
            audio_path=args.input,
            hf_token=hf_token,
            model_name=args.model,
            device=args.device,
            compute_type=args.compute_type,
            min_speakers=args.min_speakers,
            max_speakers=args.max_speakers,
            batch_size=args.batch_size,
            initial_prompt=args.initial_prompt
        )

        # 1b. Korekta nazw własnych ze słownika (names.txt)
        corrections = load_name_corrections(args.names_file)
        if corrections:
            print(f"[*] Wczytano {len(corrections)} reguł korekty nazw z {args.names_file}")
            result = apply_name_corrections(result, corrections)

        # 2. Zapis wyników bazowych
        txt_content, md_content = save_results(result, diarized, args.output_dir, base_name)

        # 3. Opcjonalny post-processing w Ollama
        if args.use_ollama:
            if not txt_content.strip():
                print("[!] Błąd: Brak treści transkrypcji do wysłania do Ollama.")
                return

            print("\n[-] Uruchamianie integracji z Ollama...")
            # Poprawienie transkrypcji
            improved_transcript = process_with_ollama(txt_content, ollama_url, ollama_model)
            if improved_transcript:
                improved_path = os.path.join(args.output_dir, f"{base_name}_ollama_edited.md")
                with open(improved_path, "w", encoding="utf-8") as f:
                    f.write(f"# Transkrypcja ulepszona przez Ollama ({ollama_model})\n\n{improved_transcript}")
                print(f"[+] Zapisano ulepszoną wersję transkrypcji do pliku: {improved_path}")
            
            # Generowanie podsumowania
            summary = generate_summary_with_ollama(txt_content, ollama_url, ollama_model)
            if summary:
                summary_path = os.path.join(args.output_dir, f"{base_name}_summary.md")
                with open(summary_path, "w", encoding="utf-8") as f:
                    f.write(summary)
                print(f"[+] Zapisano podsumowanie rozmowy do pliku: {summary_path}")

        print("\n[+] Proces zakończony pomyślnie!")
        print(f"\n[i] Aby otworzyć interaktywny viewer transkrypcji, uruchom:")
        print(f"    python viewer.py --dir {args.output_dir} --audio {args.input}")

    except Exception as e:
        print(f"\n[!] Wystąpił błąd krytyczny podczas działania programu: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
