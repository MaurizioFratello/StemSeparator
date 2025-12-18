# StemSeparator v1.0.0 - AI-Powered Audio Stem Separation für macOS

## 🎯 Vorstellung

Ich möchte euch **StemSeparator** vorstellen - eine professionelle macOS-Anwendung zur AI-gestützten Trennung von Audio-Stems (Vocals, Drums, Bass, Piano, Guitar, etc.) aus Musikdateien. Die App nutzt State-of-the-Art Deep Learning Modelle und bietet eine intuitive grafische Benutzeroberfläche.

**GitHub Repository:** https://github.com/MaurizioFratello/StemSeparator  
**Version:** 1.0.0 (erste stabile Version)  
**Plattform:** macOS (Apple Silicon M1/M2/M3)

---

## ✨ Hauptfunktionen

### 🎵 Multiple AI-Modelle
- **Mel-Band RoFormer** (~100 MB): Beste Qualität für Vocal-Trennung
- **BS-RoFormer** (~300 MB): Exzellente Qualität, SDX23 Challenge Gewinner
- **MDX-Net** (~110-120 MB): Starke Performance für Vocals & Leads
- **Demucs v4** (~240 MB): 6-Stem Trennung, Sony MDX Challenge Gewinner
- **Demucs v4 (4-stem)** (~160 MB): Schnelle 4-Stem Trennung

### 🎚️ Ensemble Separation (NEU in v1.0.0)
Kombiniert mehrere Modelle für maximale Qualität:
- **Balanced Ensemble**: Staged Approach - Mel-RoFormer + MDX Vocals + Demucs (Vocals), dann Demucs (Residual) - ~2x langsamer, +0.5-0.7 dB SDR Verbesserung
- **Quality Ensemble**: Staged Approach - Mel-RoFormer + MDX Vocals + Demucs (Vocals), dann Demucs + BS-RoFormer (Residual) - ~2.5x langsamer, +0.8 dB SDR Verbesserung
- **Ultra Ensemble**: Maximale Qualität - ~3.5x langsamer, +1.0 dB SDR Verbesserung

### 🎤 System Audio Recording
- **Native macOS Integration**: ScreenCaptureKit auf macOS 13+ (kein Treiber nötig!)
- **BlackHole Fallback**: Für macOS 12 und älter
- Direkte Aufnahme von System-Audio (Spotify, YouTube, etc.)

### 🎧 Stem Player
- Live Playback mit Echtzeit-Mixing
- Individuelle Lautstärke-Kontrolle pro Stem
- Mute/Solo Funktionen
- Master Volume Control
- Export von gemischten Stems

### ⚡ Weitere Features
- **GPU-Beschleunigung**: Apple Silicon (MPS) und NVIDIA (CUDA) Support
- **Automatisches Chunking**: Große Dateien (>30min) werden automatisch in 5-Minuten-Chunks aufgeteilt
- **Intelligente Fehlerbehandlung**: Automatischer CPU-Fallback bei GPU-Problemen
- **Queue-System**: Mehrere Dateien sequenziell verarbeiten
- **Modern Dark Theme**: Professionelle UI mit Purple-Blue Akzenten
- **Mehrsprachig**: Deutsch und Englisch

---

## 💡 Entwicklungsmotivation

Als Musiker und Entwickler war ich frustriert von den verfügbaren Lösungen für Audio-Stem-Trennung:
- **Kostenlose Tools** waren oft von schlechter Qualität oder schwer zu bedienen
- **Professionelle Software** war teuer und oft überladen mit Features, die ich nicht brauchte
- **Online-Dienste** hatten Datenschutz-Bedenken und Upload-Limits

**StemSeparator** wurde entwickelt, um:
- ✅ **Lokal und privat** zu arbeiten (keine Cloud-Uploads)
- ✅ **State-of-the-Art Qualität** mit Open-Source Modellen zu bieten
- ✅ **Einfach zu bedienen** sein, ohne Kompromisse bei der Qualität
- ✅ **Kostenlos und Open Source** zu sein (MIT License)

Die App nutzt die neuesten Open-Source Modelle (Mel-RoFormer, BS-RoFormer, Demucs v4) und kombiniert sie intelligent für maximale Qualität. Das Ensemble-Verfahren erreicht bis zu +1.0 dB SDR Verbesserung gegenüber einzelnen Modellen - ein deutlich hörbarer Qualitätsunterschied!

---

## 📖 How-To: Schnellstart-Anleitung

### Installation

**Option 1: Standalone App (Empfohlen)**
1. Download von [GitHub Releases](https://github.com/MaurizioFratello/StemSeparator/releases)
2. DMG-Datei öffnen und "Stem Separator" in den Applications-Ordner ziehen
3. App starten (erstes Mal: Rechtsklick → "Öffnen" wegen Gatekeeper)

**Option 2: Entwickler-Installation**
```bash
git clone https://github.com/MaurizioFratello/StemSeparator.git
cd StemSeparator
conda env create -f environment.yml
conda activate stem-separator
python main.py
```

### Basis-Nutzung: Stem-Trennung

1. **App starten** (`python main.py` oder App öffnen)
2. **"Upload" Tab** wählen
3. **Audio-Datei laden** (Drag & Drop oder Datei-Browser)
4. **Modell wählen**:
   - **Demucs v4 (6-stem)**: Standard, trennt Piano & Guitar
   - **Mel-RoFormer**: Beste Qualität für Vocals
   - **BS-RoFormer**: Exzellente Qualität für alle Stems
5. **"Separate" klicken**
6. **Stems werden automatisch gespeichert** im `temp/separated/` Ordner

### Ensemble Separation (Maximale Qualität)

1. **"Upload" Tab** → **"Ensemble Mode"** aktivieren
2. **Ensemble-Konfiguration wählen**:
   - **Balanced**: Empfohlen - Gute Qualität, akzeptable Verarbeitungszeit (~2x)
   - **Quality**: Professionelle Qualität - Bestes Verhältnis Qualität/Zeit (~2.5x)
   - **Ultra**: Maximale Qualität für kritische Anwendungen (~3.5x)
3. **Trennung starten**

**Hinweis:** Ensemble Separation nutzt einen "staged approach": Vocals werden zuerst mit mehreren Modellen getrennt, dann werden die Residual-Stems (Drums, Bass, Other) separat verarbeitet für optimale Qualität.

### System Audio Recording

**macOS 13+ (Ventura und später):**
1. **"Recording" Tab** wählen
2. **Screen Recording Berechtigung** erteilen (wird beim ersten Mal abgefragt)
3. **"Start Recording"** klicken
4. **Audio auf dem Mac abspielen** (Spotify, YouTube, etc.)
5. **"Stop & Save"** klicken
6. Die aufgenommene Datei kann direkt für Trennung verwendet werden

**macOS 12 und älter:**
1. **"Recording" Tab** wählen
2. **"In: BlackHole 2ch"** als Eingabegerät wählen (wird automatisch installiert falls nötig)
3. **"Start Recording"** klicken
4. Audio abspielen
5. **"Stop & Save"** klicken

### Stem Player (Mixing)

1. **"Player" Tab** wählen
2. **Getrennte Stems laden** (per Ordner oder einzelne Dateien)
3. **Mixer-Controls nutzen**:
   - **M**: Mute (Stem stummschalten)
   - **S**: Solo (nur diesen Stem hören)
   - **Volume Slider**: Lautstärke pro Stem
   - **Master Volume**: Gesamtlautstärke
4. **Playback-Controls**:
   - Play/Pause/Stop
   - Position Slider für Navigation
   - Export gemischtes Audio

---

## 🎓 Technische Details

### Systemanforderungen
- **Betriebssystem**: macOS 10.15 (Catalina) oder neuer
- **RAM**: 8 GB (16 GB empfohlen)
- **GPU**: Apple Silicon (M1/M2/M3) für MPS-Beschleunigung empfohlen
- **Speicher**: ~1.5 GB für Modelle

### Qualitäts-Metriken
- **Single Model (BS-RoFormer)**: SDR 12.98 dB (Baseline)
- **Balanced Ensemble**: SDR 13.5 dB (+0.5 dB)
- **Quality Ensemble**: SDR 13.8 dB (+0.8 dB)
- **1 dB Verbesserung = deutlich hörbarer Qualitätsunterschied!**

### Verarbeitungszeit (3-Minuten Song, GPU)
- **Single Model**: ~2-3 Minuten
- **Balanced Ensemble**: ~4-6 Minuten
- **Quality Ensemble**: ~6-9 Minuten

---

## 🚀 Roadmap

Geplante Features für zukünftige Versionen:
- Windows/Linux Support für System Audio Recording
- Zusätzliche Modelle (MDX-Net Variationen, VR Architecture)
- Batch Export Funktionalität
- Real-Time Preview während Verarbeitung
- VST/AU Plugin Version
- Cloud-basierte Verarbeitung (optional)

---

## 📚 Weitere Informationen

- **GitHub**: https://github.com/MaurizioFratello/StemSeparator
- **Issues & Feature Requests**: https://github.com/MaurizioFratello/StemSeparator/issues
- **Dokumentation**: Vollständige Dokumentation im Repository
- **License**: MIT (Open Source)

---

## 🙏 Credits

StemSeparator nutzt folgende Open-Source Projekte:
- **audio-separator**: Python Library für Stem Separation
- **Demucs**: Facebook Research (Meta AI)
- **BS-RoFormer**: ByteDance AI Lab
- **Mel-Band RoFormer**: Music Source Separation Community
- **PySide6**: Qt for Python
- **sounddevice**: Python Bindings für PortAudio

---

**Fazit:** StemSeparator ist ein leistungsstarkes, benutzerfreundliches Tool für Audio-Stem-Trennung, das State-of-the-Art Qualität mit lokaler Verarbeitung und Open-Source Transparenz kombiniert. Perfekt für Musiker, Producer und Audio-Enthusiasten, die ihre Musik analysieren, remixen oder karaoke-Versionen erstellen möchten.

**Probiert es aus und lasst mich wissen, was ihr denkt!** 🎵

---

*Version 1.0.0 - Dezember 2024*

