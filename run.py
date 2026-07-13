#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run.py
──────────────────────────────────────────────────────────────────────────────
Zintegrowany skrypt uruchamiający cały potok:
1. (Opcjonalnie) Wycięcie fragmentu audio z pliku wejściowego za pomocą ffmpeg.
2. Transkrypcja i diaryzacja (WhisperX + PyAnnote) z użyciem transcribe.py.
3. Korekta i poprawki w Ollama (włączona domyślnie!).
4. Automatyczne uruchomienie interaktywnego viewera (viewer.py) w przeglądarce.

Sposób użycia:
  python run.py -i plik.mp4                      # Pełny plik + Ollama + Viewer
  python run.py -i plik.mp4 -s 00:01:00 -d 30    # 30-sekundowy fragment od 1 minuty
"""

import os
import sys
import argparse
import subprocess
import shutil

def check_venv():
    """Automatyczne przełączenie na interpreter wewnątrz wirtualnego środowiska (venv),
    dzięki czemu użytkownik nie musi go ręcznie aktywować w shellu."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(current_dir, "venv", "bin", "python3")
    
    # Jeśli istnieje venv i nie jesteśmy w nim uruchomieni, zrestartujmy proces z venv_python
    if os.path.exists(venv_python) and sys.executable != venv_python:
        # Zachowujemy wszystkie argumenty przekazane do skryptu
        cmd = [venv_python] + sys.argv
        try:
            sys.exit(subprocess.call(cmd))
        except Exception as e:
            print(f"[!] Błąd podczas automatycznej aktywacji wirtualnego środowiska: {e}")
            sys.exit(1)

def run_command(cmd):
    """Pomocnicza funkcja do uruchamiania poleceń shellowych."""
    print(f"\n\033[94m[-] Uruchamianie: {' '.join(cmd)}\033[0m")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    # Wyświetlanie wyjścia na bieżąco
    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())
            
    rc = process.poll()
    return rc

def main():
    # Zabezpieczenie na venv
    check_venv()

    parser = argparse.ArgumentParser(description="Zintegrowany skrypt transkrypcji i podglądu")
    parser.add_argument("-i", "--input", required=False, default=None, help="Ścieżka do pliku audio/wideo (opcjonalna — bez tego uruchamia sam viewer)")
    parser.add_argument("-s", "--start", default=None, help="Czas rozpoczęcia fragmentu (np. 90 lub 00:01:30)")
    parser.add_argument("-e", "--end", default=None, help="Czas zakończenia fragmentu (np. 120 lub 00:02:00)")
    parser.add_argument("-d", "--duration", default=None, help="Czas trwania fragmentu w sekundach (np. 30)")
    parser.add_argument("-m", "--model", default="medium", help="Model Whisper (domyślnie: medium)")
    parser.add_argument("--no-ollama", action="store_true", help="Wyłącz poprawianie tekstu za pomocą Ollama")
    parser.add_argument("--port", type=int, default=8765, help="Port dla interaktywnego viewera (domyślnie: 8765)")
    parser.add_argument("-b", "--batch-size", type=int, default=4, help="Rozmiar wsadu (batch size) transkrypcji (domyślnie: 4, ustaw 1-2 w razie problemów z VRAM)")
    parser.add_argument("--device", default="cuda", help="Urządzenie obliczeniowe: cuda lub cpu (domyślnie: cuda)")
    parser.add_argument("-c", "--compute-type", default="float16", help="Typ obliczeń: float16, float32, int8 (domyślnie: float16)")
    # Generowanie postów
    parser.add_argument("--posty", action="store_true", help="Po transkrypcji wygeneruj posty na X (Twitter) za pomocą Ollama")
    parser.add_argument("--osoba", default="Dorota Spyrka", help="Imię osoby do postów (domyślnie: Dorota Spyrka)")
    parser.add_argument("--username", default="@dorota_spyrka", help="Username na X (domyślnie: @dorota_spyrka)")
    parser.add_argument("--program", default="@OficjalneZero", help="Nazwa programu (domyślnie: @OficjalneZero)")
    parser.add_argument("-n", "--num-posts", type=int, default=5, help="Ile postów wygenerować (domyślnie: 5)")
    parser.add_argument("--min-speakers", type=int, default=None, help="Minimalna liczba mówców (domyślnie: auto)")
    parser.add_argument("--max-speakers", type=int, default=None, help="Maksymalna liczba mówców (domyślnie: auto)")
    
    args = parser.parse_args()

    os.makedirs("transcripts", exist_ok=True)

    # Jeśli nie podano pliku wejściowego — uruchom sam viewer
    if not args.input:
        print(f"\033[92m[*] Uruchamianie viewera (tryb przeglądania)...\033[0m", flush=True)
        viewer_cmd = [
            sys.executable, "viewer.py",
            "--dir", "./transcripts",
            "--port", str(args.port),
        ]
        try:
            subprocess.run(viewer_cmd)
        except KeyboardInterrupt:
            print("\n\033[93m[-] Zamykanie viewera...\033[0m")
        return

    # Sprawdzenie pliku wejściowego
    if not os.path.exists(args.input):
        print(f"\033[91m[!] Plik '{args.input}' nie istnieje!\033[0m")
        sys.exit(1)

    input_path = os.path.abspath(args.input)

    # 1. Wycięcie fragmentu lub konwersja wideo do MP3 w celu optymalizacji i kompatybilności z przeglądarką
    audio_to_transcribe = input_path
    is_fragment = args.start or args.end or args.duration

    ext = os.path.splitext(input_path)[1].lower()
    is_video = ext in [".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".wmv", ".mpeg", ".mpg"]
    is_supported_audio = ext in [".mp3", ".wav", ".m4a", ".ogg", ".aac"]

    # Jeśli program 'ffmpeg' jest wymagany
    needs_ffmpeg = is_fragment or is_video or not is_supported_audio
    if needs_ffmpeg:
        if not shutil.which("ffmpeg"):
            print("\033[91m[!] Błąd: Program 'ffmpeg' nie jest zainstalowany w systemie, a jest wymagany do konwersji/cięcia plików!\033[0m")
            sys.exit(1)

    base_name = os.path.splitext(os.path.basename(input_path))[0]

    if is_fragment:
        print("\033[93m[*] Przygotowywanie wycinka audio za pomocą ffmpeg...\033[0m")
        fragment_filename = f"{base_name}_fragment.mp3"
        audio_to_transcribe = os.path.abspath(os.path.join("transcripts", fragment_filename))

        ffmpeg_cmd = ["ffmpeg", "-y"]
        if args.start:
            ffmpeg_cmd += ["-ss", str(args.start)]
        ffmpeg_cmd += ["-i", input_path]
        if args.end:
            ffmpeg_cmd += ["-to", str(args.end)]
        elif args.duration:
            ffmpeg_cmd += ["-t", str(args.duration)]
        
        ffmpeg_cmd += ["-q:a", "0", "-map", "a", audio_to_transcribe]

        print(f"[-] Komenda ffmpeg: {' '.join(ffmpeg_cmd)}")
        res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"\033[91m[!] Błąd podczas wycinania audio przez ffmpeg:\033[0m\n{res.stderr}")
            sys.exit(1)
        print(f"\033[92m[+] Wycięto pomyślnie! Fragment zapisany jako: {audio_to_transcribe}\033[0m")

    elif is_video or not is_supported_audio:
        # Konwersja całego pliku wideo/nieobsługiwanego dźwięku do MP3 (aby strona w przeglądarce działała szybko i stabilnie)
        converted_filename = f"{base_name}.mp3"
        audio_to_transcribe = os.path.abspath(os.path.join("transcripts", converted_filename))

        if not os.path.exists(audio_to_transcribe):
            print(f"\033[93m[*] Wykryto format wideo lub nieobsługiwany dźwięk ({ext}). Wyodrębniam ścieżkę audio do MP3...\033[0m")
            ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path, "-q:a", "0", "-map", "a", audio_to_transcribe]
            print(f"[-] Komenda ffmpeg: {' '.join(ffmpeg_cmd)}")
            res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"\033[91m[!] Błąd podczas wyodrębniania audio przez ffmpeg:\033[0m\n{res.stderr}")
                sys.exit(1)
            print(f"\033[92m[+] Wyodrębniono pomyślnie! Plik audio zapisany jako: {audio_to_transcribe}\033[0m")
        else:
            print(f"\033[92m[+] Znaleziono już wyodrębniony wcześniej plik audio: {audio_to_transcribe}\033[0m")

    # 2. Uruchomienie transkrypcji
    transcribe_cmd = [
        sys.executable, "transcribe.py",
        "-i", audio_to_transcribe,
        "-m", args.model,
        "--device", args.device,
        "--compute-type", args.compute_type,
        "--batch-size", str(args.batch_size),
    ]
    if args.min_speakers is not None:
        transcribe_cmd.extend(["--min-speakers", str(args.min_speakers)])
    if args.max_speakers is not None:
        transcribe_cmd.extend(["--max-speakers", str(args.max_speakers)])
    if not args.no_ollama:
        transcribe_cmd.append("--use-ollama")

    print(f"\n\033[92m[*] Rozpoczynanie transkrypcji pliku: {os.path.basename(audio_to_transcribe)}...\033[0m")
    rc = run_command(transcribe_cmd)
    if rc != 0:
        print(f"\033[91m[!] Transkrypcja zakończyła się błędem (kod: {rc})\033[0m")
        sys.exit(rc)

    # 3. Generowanie postów (opcjonalnie)
    if args.posty:
        # Znajdź plik .txt z transkrypcją
        transcript_txt = os.path.join("transcripts", f"{base_name}.txt")
        if is_fragment:
            transcript_txt = os.path.join("transcripts", f"{base_name}_fragment.txt")

        if os.path.exists(transcript_txt):
            posty_cmd = [
                sys.executable, "posty.py",
                "-t", transcript_txt,
                "--osoba", args.osoba,
                "--username", args.username,
                "--program", args.program,
                "-n", str(args.num_posts),
            ]
            print(f"\n\033[92m[*] Generowanie postów na X (Twitter)...\033[0m")
            run_command(posty_cmd)
        else:
            print(f"\033[93m[!] Nie znaleziono pliku transkrypcji tekstowej: {transcript_txt}\033[0m")
            print(f"    Posty nie zostaną wygenerowane.")

    # 4. Uruchomienie viewera
    default_name = f"{base_name}_fragment" if is_fragment else base_name
    viewer_cmd = [
        sys.executable, "viewer.py",
        "--dir", "./transcripts",
        "--audio", audio_to_transcribe,
        "--port", str(args.port),
        "--default", default_name
    ]
    print(f"\n\033[92m[*] Uruchamianie interaktywnego viewera na porcie {args.port}...\033[0m")
    
    # viewer.py uruchomi się i sam otworzy przeglądarkę
    try:
        subprocess.run(viewer_cmd)
    except KeyboardInterrupt:
        print("\n\033[93m[-] Zamykanie viewera...\033[0m")

if __name__ == "__main__":
    main()
