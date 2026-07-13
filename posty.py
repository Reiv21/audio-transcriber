#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
posty.py
────────────────────────────────────────────────────────────────────────────────
Skrypt do automatycznego generowania postów na X (Twitter) z transkrypcji
wypowiedzi medialnych, z wykorzystaniem lokalnego modelu AI (Ollama).

Skrypt:
1. Wczytuje transkrypcję (.txt) z katalogu transcripts/.
2. Wczytuje plik z przykładowymi postami (posty.txt) jako wzór stylu.
3. Wysyła to do Ollamy z precyzyjnym promptem, który uczy model pisania postów.
4. Wyświetla wygenerowane posty i zapisuje je do pliku.

Sposób użycia:
  python posty.py -t transcripts/7.txt
  python posty.py -t transcripts/7.txt --osoba "Adrian Zandberg"
  python posty.py -t transcripts/7.txt -n 5
  python posty.py -t transcripts/7.txt --program "@OficjalneZero"
"""

import os
import sys
import argparse
import subprocess
import requests
from dotenv import load_dotenv

# Wczytanie zmiennych środowiskowych z .env
load_dotenv()


def check_venv():
    """Automatyczne przełączenie na interpreter wewnątrz venv."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(current_dir, "venv", "bin", "python3")
    if os.path.exists(venv_python) and sys.executable != venv_python:
        cmd = [venv_python] + sys.argv
        try:
            sys.exit(subprocess.call(cmd))
        except Exception as e:
            print(f"[!] Błąd podczas automatycznej aktywacji venv: {e}")
            sys.exit(1)


def load_example_posts(posts_file: str) -> str:
    """Wczytuje przykładowe posty z pliku."""
    if not os.path.exists(posts_file):
        print(f"\033[93m[!] Plik z przykładowymi postami '{posts_file}' nie istnieje. Generowanie bez wzorców.\033[0m")
        return ""
    with open(posts_file, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_transcript(transcript_path: str) -> str:
    """Wczytuje transkrypcję z pliku .txt."""
    if not os.path.exists(transcript_path):
        print(f"\033[91m[!] Plik transkrypcji '{transcript_path}' nie istnieje!\033[0m")
        sys.exit(1)
    with open(transcript_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def generate_posts(
    transcript: str,
    example_posts: str,
    ollama_url: str,
    ollama_model: str,
    osoba: str,
    username: str,
    program: str,
    num_posts: int,
    hashtags: list[str],
) -> str:
    """Generuje posty za pomocą Ollama."""

    # Budowanie promptu
    hashtag_str = " ".join(hashtags)

    example_section = ""
    if example_posts:
        example_section = f"""
=== PRZYKŁADOWE POSTY (WZÓR STYLU) ===
Poniżej znajdują się posty, które zostały wcześniej opublikowane. Musisz pisać w IDENTYCZNYM stylu.
Analizuj ich strukturę, ton, użycie emoji, formatowanie i sposób cytowania wypowiedzi.

{example_posts}

=== KONIEC PRZYKŁADÓW ===
"""

    system_prompt = f"""Jesteś rygorystycznym ekstraktorem cytatów. Twoim JEDYNYM zadaniem jest kopiowanie słowo w słowo najważniejszych zdań z podanego tekstu i formatowanie ich jako posty.

BEZWZGLĘDNE ZASADY:
1. ZABRONIONE jest streszczanie tekstu, opisywanie go własnymi słowami, wymyślanie linków czy dodawanie jakichkolwiek własnych komentarzy!
2. Każdy post to po prostu 1-3 bezpośrednie zdania WYCIĄGNIĘTE SŁOWO W SŁOWO z transkrypcji (możesz jedynie pominąć zająknięcia jak "yyy").
3. Każdy post MUSI zaczynać się od: 💬 {username} w {program}:
4. Każdy post MUSI kończyć się hashtagiem: #RAZEMwMEDIACH (NIGDY nie używaj hashtagu #LigaDebat).

PRZYKŁAD DZIAŁANIA:
Tekst wejściowy: "Tak, panie redaktorze, szczególnie, że... Najważniejsza rzecz w komunikacji publicznej to jest to, żeby transport publiczny był dostępny. On powinien być dostępny cenowo, powinien być wygodny do skorzystania, powinien umożliwać ludziom przemieszczanie się tak, żeby wybierali transport publiczny, Ja uważam, że powinniśmy rozważyć przywrócenie biletu dwudziestominutowego."

Twój wygenerowany post:
💬 {username} w {program}: Najważniejsza rzecz w komunikacji publicznej to jest to, żeby transport publiczny był dostępny. On powinien być dostępny cenowo, wygodny do skorzystania i powinien umożliwać ludziom przemieszczanie się tak, żeby wybierali transport publiczny. Ja uważam, że powinniśmy rozważyć przywrócenie biletu dwudziestominutowego. #RAZEMwMEDIACH

Teraz zrób to samo dla poniższego tekstu użytkownika. Wygeneruj dokładnie {num_posts} postów. Oddzielaj posty podwójną nową linią (\\n\\n). Nie pisz żadnych wstępów."""

    prompt = f"TRANSKRYPCJA DO PRZETWORZENIA:\n{transcript}\n\nWygeneruj dokładnie {num_posts} postów."

    print(f"\033[94m[-] Wysyłanie do Ollama (model: {ollama_model})...\033[0m")

    try:
        response = requests.post(
            f"{ollama_url}/api/chat",
            json={
                "model": ollama_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {
                    "temperature": 0.0
                }
            },
            timeout=300,  # 5 minut timeout, bo generowanie wielu postów może potrwać
        )
        if response.status_code == 200:
            return response.json().get("message", {}).get("content", "").strip()
        else:
            print(f"\033[91m[!] Błąd Ollama: HTTP {response.status_code}\033[0m")
            print(response.text[:500])
            return ""
    except requests.exceptions.ConnectionError:
        print(f"\033[91m[!] Nie można połączyć się z Ollama pod adresem {ollama_url}.\033[0m")
        print(f"    Upewnij się, że Ollama jest uruchomiona (ollama serve).")
        return ""
    except Exception as e:
        print(f"\033[91m[!] Błąd połączenia z Ollama: {e}\033[0m")
        return ""


def main():
    check_venv()

    parser = argparse.ArgumentParser(
        description="Generuj posty na X (Twitter) z transkrypcji za pomocą lokalnego AI (Ollama)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-t", "--transcript", required=True,
        help="Ścieżka do pliku .txt z transkrypcją (np. transcripts/7.txt)",
    )
    parser.add_argument(
        "--posty", default="posty.txt",
        help="Ścieżka do pliku z przykładowymi postami (domyślnie: posty.txt)",
    )
    parser.add_argument(
        "--osoba", default="Dorota Spyrka",
        help="Imię i nazwisko osoby, o której posty mają być pisane (domyślnie: Dorota Spyrka)",
    )
    parser.add_argument(
        "--username", default="@dorota_spyrka",
        help="Username na X/Twitterze (domyślnie: @dorota_spyrka)",
    )
    parser.add_argument(
        "--program", default="@OficjalneZero",
        help="Nazwa programu / kanału (domyślnie: @OficjalneZero)",
    )
    parser.add_argument(
        "-n", "--num-posts", type=int, default=5,
        help="Ile postów wygenerować (domyślnie: 5)",
    )
    parser.add_argument(
        "--hashtags", nargs="+", default=["#RAZEMwMEDIACH"],
        help="Lista hashtagów do dodania (domyślnie: #RAZEMwMEDIACH). NIE dołączaj #LigaDebat.",
    )
    parser.add_argument(
        "-o", "--output", default=None,
        help="Ścieżka do pliku wyjściowego z wygenerowanymi postami (opcjonalnie)",
    )

    args = parser.parse_args()

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1")

    # Wczytanie danych
    print(f"\033[92m[*] Generowanie postów na X (Twitter)\033[0m")
    print(f"    Osoba:       {args.osoba} ({args.username})")
    print(f"    Program:     {args.program}")
    print(f"    Model:       {ollama_model}")
    print(f"    Hashtagi:    {' '.join(args.hashtags)}")
    print(f"    Liczba:      {args.num_posts}")
    print()

    transcript = load_transcript(args.transcript)
    example_posts = load_example_posts(args.posty)

    # Generowanie
    result = generate_posts(
        transcript=transcript,
        example_posts=example_posts,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
        osoba=args.osoba,
        username=args.username,
        program=args.program,
        num_posts=args.num_posts,
        hashtags=args.hashtags,
    )

    if not result:
        print("\033[91m[!] Nie udało się wygenerować postów.\033[0m")
        sys.exit(1)

    # Wyświetlenie wyników
    print()
    print("\033[1m" + "═" * 60 + "\033[0m")
    print("\033[1m  WYGENEROWANE POSTY\033[0m")
    print("\033[1m" + "═" * 60 + "\033[0m")
    print()
    print(result)
    print()
    print("\033[1m" + "═" * 60 + "\033[0m")

    # Zapis do pliku
    if args.output:
        output_path = args.output
    else:
        base_name = os.path.splitext(os.path.basename(args.transcript))[0]
        output_path = os.path.join(
            os.path.dirname(args.transcript) or ".",
            f"{base_name}_posty.txt",
        )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"\n\033[92m[+] Posty zapisane do: {output_path}\033[0m")


if __name__ == "__main__":
    main()
