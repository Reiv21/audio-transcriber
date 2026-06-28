# Lokalna Transkrypcja i Podział na Mówców (Diarization)

Projekt umożliwia lokalną transkrypcję plików audio/wideo (`mp3`, `mp4`, `wav`, `mkv`) na tekst z automatycznym podziałem wypowiedzi na poszczególnych mówców (np. *Speaker 0*, *Speaker 1*). Posiada także opcjonalną integrację z **Ollama** w celu korekty językowej i generowania podsumowań spotkań.

Projekt wykorzystuje bibliotekę **WhisperX** (wraz z modelami **Whisper** od OpenAI/Faster-Whisper do transkrypcji oraz **PyAnnote** do diaryzacji).

---

## 🛠️ Wymagania i Instalacja

### 1. Klonowanie / przejście do folderu projektu
Upewnij się, że jesteś w katalogu projektu:
```bash
cd /home/reiv/.gemini/antigravity/scratch/audio-transcriber
```

### 2. Utworzenie wirtualnego środowiska Pythona
Stwórz i aktywuj środowisko wirtualne, aby nie zaśmiecać systemu:
```bash
python3 -m venv venv
# Dla bash/zsh:
source venv/bin/activate
# Dla fish:
source venv/bin/activate.fish
```

### 3. Instalacja bibliotek
Zainstaluj wymagane zależności (w tym PyTorch z obsługą CUDA dla Twojej karty graficznej RTX 3070):
```bash
pip install -r requirements.txt
```

---

## 🔑 Konfiguracja Hugging Face (Dla podziału na mówców)

Diaryzacja opiera się o modele PyAnnote, które wymagają bezpłatnej rejestracji i zaakceptowania ich regulaminu na platformie Hugging Face.

1. Zaloguj się lub zarejestruj na [Hugging Face](https://huggingface.co/).
2. Zaakceptuj warunki korzystania dla dwóch modeli (musisz być zalogowany):
   * [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
   * [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
3. Przejdź do [Hugging Face Token Settings](https://huggingface.co/settings/tokens) i utwórz token typu **Read**.
4. Skopiuj plik `.env.example` jako `.env`:
   ```bash
   cp .env.example .env
   ```
5. Otwórz plik `.env` i wklej swój token w miejsce `HF_TOKEN`.

---

## 🚀 Sposób Użycia

Aktywuj środowisko (jeśli nie jest aktywne):
```bash
# Dla bash/zsh:
source venv/bin/activate
# Dla fish:
source venv/bin/activate.fish
```

### Podstawowe uruchomienie
Transkrypcja pliku wideo lub audio na domyślnym modelu `medium` (bardzo dobry stosunek jakości do prędkości):
```bash
python3 transcribe.py -i /sciezka/do/pliku.mp4
```
Wyniki zostaną zapisane w folderze `./transcripts` w trzech formatach: `.txt`, `.json` oraz `.md`.

### Zaawansowane opcje
* **Wybór modelu:** Dostępne modele to np. `small`, `medium`, `large-v3`. Im większy model, tym lepsza dokładność, ale większe zużycie pamięci GPU (model `medium` jest optymalny dla kart z 8GB VRAM).
  ```bash
  python3 transcribe.py -i plik.mp3 -m medium
  ```
* **Określenie liczby mówców:** Jeśli wiesz dokładnie, ile osób brało udział w rozmowie, możesz to zdefiniować w celu poprawy dokładności podziału:
  ```bash
  python3 transcribe.py -i plik.mp3 --min-speakers 2 --max-speakers 2
  ```

---

## 🤖 Integracja z Ollama / Open WebUI

Jeśli masz uruchomioną lokalnie instancję Ollama, skrypt może automatycznie przesłać do niej gotową transkrypcję, aby:
1. Usunąć zająknięcia i powtórzenia (np. "eee", "yyy").
2. Poprawić interpunkcję i podzielić monologi na czytelne akapity.
3. Spróbować zastąpić nazwy mówców typu `Speaker 0` ich prawdziwymi imionami (jeśli padły w rozmowie).
4. Stworzyć podsumowanie spotkania w formacie Markdown z listą zadań (Action Items).

### Jak użyć:
1. Upewnij się, że Ollama działa (np. pod adresem `http://localhost:11434`).
2. W pliku `.env` ustaw preferowany model (np. `OLLAMA_MODEL=llama3`).
3. Uruchom skrypt z flagą `--use-ollama`:
   ```bash
   python3 transcribe.py -i plik.mp3 --use-ollama
   ```
Po zakończeniu transkrypcji w katalogu wyjściowym pojawią się dodatkowe pliki:
* `[nazwa_pliku]_ollama_edited.md` – poprawiony, sformatowany tekst.
* `[nazwa_pliku]_summary.md` – przejrzyste podsumowanie spotkania.

---

## 🖥️ Interaktywny Viewer Transkrypcji

Po zakończeniu transkrypcji możesz otworzyć interaktywny viewer w przeglądarce. Viewer wyświetla tekst z podziałem na mówców i pozwala kliknąć na dowolne słowo, aby odsłuchać je w nagraniu.

### Uruchomienie viewera:
```bash
python3 viewer.py --dir ./transcripts --audio /ścieżka/do/pliku.mp3
```

### Funkcje viewera:
* **Klikalne słowa** – kliknij dowolne słowo, a audio przeskoczy do momentu, w którym jest ono wypowiadane.
* **Podświetlanie w czasie rzeczywistym** – aktualnie odtwarzane słowo jest podświetlone (styl karaoke).
* **Edycja nazw mówców** – kliknij na nazwę mówcy (np. `SPEAKER_00`), aby wpisać imię (np. `Janek`). Wszystkie wystąpienia zostaną zaktualizowane. Nazwy zapisują się w przeglądarce (`localStorage`).
* **Skróty klawiszowe** – `Spacja` = play/pause, `←`/`→` = przewiń ±5 sekund.
* **Zmiana prędkości odtwarzania** – przycisk tempa (0.5×–2×).

---

## ⚡ Zintegrowane Uruchamianie (Wszystko w jednym)

Aby maksymalnie uprościć cały proces, stworzono skrypt **`run.py`**, który:
1. **Automatycznie aktywuje środowisko wirtualne** `venv` (nie musisz wpisywać `source venv/...`).
2. **Umożliwia opcjonalne wycięcie fragmentu** za pomocą `ffmpeg` (idealne do szybkiego testowania).
3. **Uruchamia transkrypcję** z domyślnie włączonym ulepszaniem przez **Ollama**.
4. **Od razu uruchamia serwer viewera** i **otwiera stronę w przeglądarce**.

### Przykłady poleceń:

1. **Transkrypcja całego pliku z poprawkami Ollama i otwarciem strony:**
   ```bash
   python3 run.py -i plik.mp3
   ```

2. **Transkrypcja tylko wybranego fragmentu (np. od 1 minuty 30 sekund przez 45 sekund):**
   ```bash
   python3 run.py -i plik.mp3 -s 00:01:30 -d 45
   ```

3. **Opcje skryptu `run.py`:**
   * `-i` / `--input` (wymagane) – Ścieżka do pliku audio/wideo.
   * `-s` / `--start` – Czas rozpoczęcia fragmentu (np. `90` lub `00:01:30`).
   * `-e` / `--end` – Czas zakończenia fragmentu (np. `120` lub `00:02:00`).
   * `-d` / `--duration` – Czas trwania fragmentu w sekundach (np. `30`).
   * `-m` / `--model` – Model Whisper (domyślnie `medium`).
   * `--no-ollama` – Wyłączenie post-processingu Ollama (korekty).
   * `--port` – Port dla viewera (domyślnie `8765`).

