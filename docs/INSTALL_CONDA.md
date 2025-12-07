# Installation mit Conda

## Schnellstart

```bash
# 1. Conda Environment erstellen
conda env create -f environment.yml

# 2. Environment aktivieren
conda activate stem-separator

# 3. Installation verifizieren
python main.py

# 4. Tests ausführen
pytest
```

## Schritt-für-Schritt Anleitung

### 1. Environment erstellen

Das `environment.yml` enthält alle notwendigen Dependencies:

```bash
conda env create -f environment.yml
```

Dies erstellt ein Environment namens `stem-separator` mit Python 3.11 und allen Dependencies.

**Hinweis:** Die Installation kann einige Minuten dauern, da viele Pakete heruntergeladen werden müssen (~500MB+).

### 2. Environment aktivieren

```bash
conda activate stem-separator
```

### 3. Verifizieren der Installation

```bash
# Prüfe Python-Version
python --version
# Sollte: Python 3.11.x anzeigen

# Prüfe ob alle Imports funktionieren
python -c "import PySide6; import soundfile; import numpy; print('All imports successful!')"

# Starte die App (Phase 1)
python main.py
```

### 4. Tests ausführen

```bash
# Alle Tests
pytest

# Mit verbose Output
pytest -v

# Mit Coverage
pytest --cov

# Nur Unit Tests
pytest -m unit
```

## Alternative: Manuelle Installation

Falls die `environment.yml` nicht funktioniert:

```bash
# Environment erstellen
conda create -n stem-separator python=3.11

# Aktivieren
conda activate stem-separator

# Dependencies über pip installieren
pip install -r requirements.txt
```

## Environment verwalten

### Environment löschen
```bash
conda deactivate
conda env remove -n stem-separator
```

### Environment neu erstellen
```bash
conda env create -f environment.yml --force
```

### Installed packages anzeigen
```bash
conda activate stem-separator
conda list
```

### Environment exportieren (nach Updates)
```bash
conda env export > environment_backup.yml
```

## Troubleshooting

### "conda: command not found"
Stelle sicher, dass Conda installiert ist:
```bash
# Conda Version prüfen
conda --version

# Falls nicht installiert, Miniforge oder Anaconda installieren
# https://github.com/conda-forge/miniforge
```

### PyQt/PySide6 Import Fehler
```bash
# Manchmal hilft eine Neuinstallation
pip uninstall PySide6
pip install PySide6>=6.6.0
```

### PyTorch MPS Support (Apple Silicon)
```bash
# Prüfe ob MPS verfügbar ist
python -c "import torch; print(f'MPS available: {torch.backends.mps.is_available()}')"
```

### Dependency Conflicts
```bash
# Lösche das Environment und erstelle es neu
conda deactivate
conda env remove -n stem-separator
conda env create -f environment.yml
```

## Nach der Installation

1. **Modelle vorbereiten** (optional, werden automatisch beim ersten Gebrauch geladen):
   ```bash
   python -c "from core.model_manager import get_model_manager; get_model_manager().download_all_models()"
   ```

2. **BlackHole installieren** (für System Audio Recording):
   ```bash
   brew install blackhole-2ch
   ```

3. **App starten**:
   ```bash
   python main.py
   ```

## Development Setup

Für Entwicklung zusätzliche Tools installieren:

```bash
conda activate stem-separator

# Code Formatting
pip install black isort

# Linting
pip install flake8 mypy

# Pre-commit hooks
pip install pre-commit
pre-commit install
```

## Environment aktivieren bei jedem Terminal-Start

Füge dies zu deiner `~/.zshrc` oder `~/.bashrc` hinzu:

```bash
# Auto-activate stem-separator in diesem Verzeichnis
if [ -f "/Users/moritzbruder/Documents/04_Python/StemSeparator/environment.yml" ]; then
    conda activate stem-separator 2>/dev/null
fi
```
