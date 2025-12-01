# BeatNet Beat-Service & Wrapper – Product Requirements Document

## 1. Überblick

Dieses Dokument beschreibt die Anforderungen und das technische Design für die Integration eines separaten Beat-Services auf Basis von **BeatNet** in die bestehende **StemSeparator**-Applikation.

Ziel ist es, hochqualitative Beat- und Downbeat-Informationen für Loop-Detection bereitzustellen, ohne die bestehende Python-3.11-/Audio-Separation-Umgebung zu destabilisieren. BeatNet wird in einem separaten Environment gebaut und als eigenständiges Binary in das StemSeparator-Bundle eingebettet.

## 2. Ziele

- **Präzise Beat- und Downbeat-Detektion** (inkl. Tempo) zur Verbesserung der Loop-Erkennung.
- **Kapselung** der BeatNet-Abhängigkeiten in einem separaten Beat-Service-Binary.
- **Keine Runtime-Abhängigkeit** auf Conda oder zusätzliche Python-Installationen beim Endnutzer.
- Bereitstellung einer **einzigen gepackten Applikation** (z.B. macOS `.app` + `.dmg`).
- Nutzung von **Hardware-Beschleunigung** (MPS auf Apple Silicon, optional CUDA auf NVIDIA).
- Saubere **GUI-Integration**:
  - Loop-Visualisierung auf Basis der BeatNet-Ergebnisse.
  - Loop-Vorhörfunktion mit exakten Beat-/Bar-Grenzen.
  - Fortschrittsanzeige und robustes Prozess-Management.

## 3. Systemkontext & Komponenten

### 3.1 Komponenten

- **StemSeparator (Main App)**
  - PySide6-basierte GUI.
  - Läuft auf Python 3.11.
  - Nutzt `audio-separator>=0.20.0`, Torch (MPS), etc.
  - Bereitstellung der Loop-Detection-UI.

- **BeatNet Beat-Service (Binary)**
  - Eigenständiges Binary (z.B. über PyInstaller gebaut).
  - Läuft in separatem Build-Environment (z.B. Python 3.8/3.9 mit BeatNet, numba 0.54.1).
  - Führt Beat/Downbeat/Tempo-Analyse durch.
  - Kommuniziert via CLI (Argumente) und JSON (stdout/Datei).

- **BeatNet Wrapper (Client)**
  - Python-Modul in StemSeparator (z.B. `utils/beat_service_client.py`).
  - Startet das Beat-Service-Binary als Subprozess.
  - Kapselt JSON-Ein-/Ausgabe in typsichere Python-Dataclasses.
  - Handhabt Timeouts, Fehler und Prozess-Beendigung.

### 3.2 Laufzeit-Datenfluss (High-Level)

1. Nutzer wählt eine Audiodatei oder ein Stem im StemSeparator.
2. GUI startet über den Wrapper eine Beat-Analyse:
   - Wrapper ruft Beat-Service-Binary mit Pfad zur Audiodatei auf.
3. Beat-Service:
   - Lädt Audio.
   - Führt BeatNet-Analyse durch (ggf. GPU-beschleunigt).
   - Gibt JSON mit Tempo, Beats, Downbeats etc. zurück.
4. Wrapper:
   - Parsed JSON in `BeatAnalysisResult`.
5. Loop-Logik:
   - Erzeugt Loop-Kandidaten (z.B. 1/2/4-Takte) auf Basis der Beat-Grid.
6. GUI:
   - Visualisiert Beat-/Bar-Grid.
   - Erlaubt Vorhören und Auswahl/Export von Loops.

---

## 4. Funktionale Anforderungen

### 4.1 Beat-Service CLI

**Ziel:** Definiertes, stabiles CLI für den Beat-Service, das unabhängig von der GUI-Version verwendet werden kann.

**Aufruf-Beispiel:**

```bash
beatnet-service \
  --input /path/to/audio.wav \
  --output - \
  --max-duration 300 \
  --device auto
```

**Pflichtargumente:**

- `--input <path>`  
  Absolute oder kanonische Pfadangabe zu einer Audiodatei (WAV, FLAC, MP3 etc.).

**Optionale Argumente:**

- `--output <path>|-`
  - `-` → JSON auf stdout.
  - Pfad → schreibt JSON in Datei.
- `--max-duration <seconds>`
  - Beschränkt die analysierte Länge (z.B. nur erste X Sekunden).
- `--device <cpu|mps|cuda|auto>`
  - Steuerung der Hardware-Beschleunigung:
    - `auto` (Default): bevorzugt MPS auf Apple Silicon, sonst CUDA, sonst CPU.
- `--sample-rate <int>`
  - Optionales Resampling (Standard: internes Default von BeatNet).
- `--verbose`
  - Zusätzliche Logging-Ausgabe auf stderr.

### 4.2 Beat-Service JSON-Ausgabe

**Erfolgsausgabe (Beispiel):**

```json
{
  "version": "1.0.0",
  "model": "BeatNet-1.1.3",
  "backend": "mps",
  "tempo": 123.45,
  "tempo_confidence": 0.92,
  "time_signature": "4/4",
  "beats": [
    { "time": 0.512, "index": 0, "bar": 1, "beat_in_bar": 1 },
    { "time": 1.004, "index": 1, "bar": 1, "beat_in_bar": 2 }
  ],
  "downbeats": [
    { "time": 0.512, "bar": 1 },
    { "time": 2.497, "bar": 2 }
  ],
  "analysis_duration": 12.34,
  "audio_duration": 180.0,
  "warnings": []
}
```

**Fehlerausgabe (z.B. auf stdout/stderr, Exit-Code ≠ 0):**

```json
{
  "error": "InputError",
  "message": "Unsupported audio format.",
  "details": {
    "path": "/path/to/file.xyz"
  }
}
```

**Minimalanforderungen:**

- Feld `tempo` (float, BPM).
- Feld `beats` (Liste von Objekten mit mindestens `time`).
- Optional `downbeats`, `time_signature`, `analysis_duration`, `warnings`.

### 4.3 BeatNet-Wrapper (Python API in StemSeparator)

**Ziel:** Einfache, typsichere API für die GUI/Loop-Logik.

#### 4.3.1 Dataclasses

```python
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Literal


BeatBackend = Literal["cpu", "mps", "cuda", "auto"]


@dataclass
class Beat:
    """Ein einzelner Beat im Track."""
    time: float               # Sekunden ab Track-Start
    index: int                # Laufender Beat-Index (0-basiert)
    bar: Optional[int] = None # Takt-Nummer (1-basiert), falls bekannt
    beat_in_bar: Optional[int] = None  # Position im Takt (z.B. 1..4 für 4/4)


@dataclass
class Downbeat:
    """Start eines Takts (Downbeat)."""
    time: float               # Sekunden
    bar: int                  # Takt-Nummer (1-basiert)


@dataclass
class BeatAnalysisResult:
    """Ergebnis der BeatNet-Analyse."""
    tempo: float
    tempo_confidence: float
    time_signature: str
    beats: List[Beat]
    downbeats: List[Downbeat]
    analysis_duration: float
    audio_duration: Optional[float] = None
    backend: Optional[str] = None      # cpu/mps/cuda
    warnings: Optional[List[str]] = None
```

#### 4.3.2 Wrapper-Interface

```python
class BeatServiceError(Exception):
    """Allgemeiner Fehler des Beat-Services."""


class BeatServiceTimeout(BeatServiceError):
    """Timeout beim Warten auf den Beat-Service."""
```

```python
def analyze_beats(
    audio_path: Path,
    *,
    max_duration: Optional[float] = None,
    device: BeatBackend = "auto",
    timeout_seconds: float = 60.0,
) -> BeatAnalysisResult:
    """
    Führt eine Beat-Analyse über den BeatNet-Service durch.

    Args:
        audio_path: Pfad zur Audiodatei.
        max_duration: Optionale Begrenzung der Analysedauer (Sekunden).
        device: Gewünschter Backend-Modus ('cpu', 'mps', 'cuda', 'auto').
        timeout_seconds: Harte Obergrenze für die Analysezeit.

    Raises:
        FileNotFoundError: Wenn die Audiodatei nicht existiert.
        BeatServiceTimeout: Wenn der Prozess das Timeout überschreitet.
        BeatServiceError: Bei allen anderen Fehlern (inkl. nicht-0 Exit-Code).
    """
    ...
```

**Implementierungsanforderungen (Wrapper):**

- Ermittelt den Pfad zum Beat-Service-Binary relativ zu `sys.executable` bzw. `sys._MEIPASS` (PyInstaller).
- Startet Subprozess mit `subprocess.Popen` oder `subprocess.run` (ohne `shell=True`).
- Nutzt `communicate(timeout=timeout_seconds)`, um Deadlocks zu vermeiden.
- Beendet den Prozess bei Timeout:
  - Erst SIGINT, dann SIGTERM, schließlich SIGKILL (plattformabhängig).
- Loggt stderr-Inhalte für Debugging (z.B. in bestehendes Logging-System).

---

## 5. GUI-Integration & UX

### 5.1 Nutzungsszenarien

- Nutzer wählt in der StemSeparator-GUI einen Track/Stem.
- Klick auf „Beat-Analyse“ oder „Loops automatisch erkennen“.
- Während der Analyse:
  - Fortschrittsbalken (indeterminiert oder grobe Zeitabschätzung).
  - Möglichkeit, den Vorgang abzubrechen.
- Nach der Analyse:
  - Beat-/Bar-Grid über der Wellenform, Loops werden vorgeschlagen.
  - Nutzer kann Loops anklicken, vorhören, exportieren.

### 5.2 UX-Anforderungen

- **Feedback:**
  - Statusmeldungen („Beat-Analyse gestartet“, „BeatNet läuft (MPS)“, „Fertig“ bzw. „Fehlgeschlagen“).
- **Abbruch:**
  - Cancel-Button stoppt laufende Analyse, Prozess wird beendet, UI bleibt reaktionsfähig.
- **Fallback:**
  - Falls Beat-Service fehlschlägt, greift Loop-Detection auf bestehende BPM/Beat-Lösungen zurück (z.B. `deeprhythm` + `librosa`), damit keine Funktion komplett ausfällt.

---

## 6. Performance & Hardware-Beschleunigung

- **Zielwerte:**
  - 3–5-Minuten-Track auf Apple Silicon:
    - Ziel: < 10 s Analysezeit.
    - Maximal: 30 s, danach Timeout + Fallback.
- **Backends:**
  - `device=auto`:
    - Bevorzugt MPS (Apple Silicon, `torch.backends.mps`).
    - Sonst CUDA (wenn verfügbar).
    - Sonst CPU.
- Beat-Service soll beim Start loggen, welches Backend verwendet wird (für Debugging).

---

## 7. Prozess-Management & Robustheit

- Jede Analyse wird in einem eigenen Subprozess ausgeführt.
- Der Wrapper stellt sicher, dass:
  - stdout/stderr komplett gelesen werden (kein Deadlock).
  - bei Timeout/Abbruch der Prozess zuverlässig beendet wird.
  - im Fehlerfall ein strukturierter Fehler (`BeatServiceError`) zurückgegeben wird.
- Keine Hintergrundprozesse ohne Bezug zur UI:
  - Der Wrapper hält keine „versteckten“ langen Prozesse offen.

---

## 8. Build- & Packaging-Anforderungen

- Zwei Build-Umgebungen:
  - **Main-Env (Py 3.11)** für StemSeparator.
  - **BeatNet-Env (Py 3.x < 3.10)** für den Beat-Service.
- Build-Schritte (High-Level):
  1. Beat-Service im BeatNet-Env mit PyInstaller bauen → `beatnet-service` Binary.
  2. Binary ins StemSeparator-Projekt kopieren (z.B. `resources/beatnet/beatnet-service`).
  3. StemSeparator mit PyInstaller bauen:
     - Beat-Service-Binary wird in `Contents/MacOS` oder `Contents/Resources` eingebettet.
- Endnutzer:
  - keine Conda-/Python-Installation notwendig.
  - Startet nur die StemSeparator-App / DMG.

---

## 9. Tests & Validierung (Minimum)

- **Unit-Tests:**
  - Parser für JSON-Ausgabe des Beat-Services.
  - Fehlerpfade im Wrapper (Timeout, Exit-Code ≠ 0, ungültiges JSON).
- **Integrationstests:**
  - End-to-end: Audio → Beat-Service → Loop-Grid in GUI.
  - Test auf verschiedenen Genre-Tracks (Pop, EDM, Rock, komplexere Rhythmen).
- **Performance-Tests:**
  - Messung der Analysezeit auf typischen Zielgeräten (M1/M2).
- **Stabilität:**
  - Mehrfache Analysen in einer Session (kein Ressourcenleck, keine Zombie-Prozesse).

---

## 10. Offene Design-Entscheidungen

- Exakte CLI-Argumentnamen und JSON-Feldnamen finalisieren.
- Ggf. Konfigurierbarkeit über UI (z.B. Backend-Auswahl CPU/MPS).
- Detaillierte Logging-Strategie (Log-Level, Log-Ziel).

---

## 11. Zusammenfassung

Dieses Dokument spezifiziert:

- Die Rolle des BeatNet-Beat-Services als separates, eingebettetes Binary.
- Die Wrapper-API in StemSeparator zur Kommunikation mit diesem Dienst.
- Die Anforderungen an GUI, UX, Performance, Hardware-Beschleunigung und Prozess-Management.
- Build- und Packaging-Vorgaben zur Auslieferung als eine konsistente, kondafreie Desktop-Applikation.

Es dient als Grundlage für Implementierung, Code-Design und weitere technische Diskussionen – und kann direkt von einem KI-Assistenten oder Entwickler genutzt werden, um das Feature umzusetzen.


