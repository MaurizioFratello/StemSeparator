# Xcode Setup für ScreenCaptureKit Tool

Dieser Guide hilft dir, Xcode zu installieren und das Swift CLI Tool zu bauen.

## 🎯 Schritt-für-Schritt Anleitung

### 1️⃣ Xcode installieren

**Via App Store** (empfohlen):
1. App Store öffnen
2. "Xcode" suchen
3. "Installieren" klicken
4. ☕ Kaffee holen (dauert 20-30 Minuten, ~15 GB)

**Oder via Apple Developer**:
- [developer.apple.com/download](https://developer.apple.com/download)
- Xcode .xip herunterladen
- Entpacken und nach `/Applications` verschieben

### 2️⃣ Xcode das erste Mal öffnen

Nach der Installation:
1. Xcode öffnen (in `/Applications`)
2. License Agreement akzeptieren
3. Warten bis "Installing Components" fertig ist
4. Xcode schließen (wir brauchen nur Command Line Tools)

### 3️⃣ Command Line Tools auf Xcode umstellen

```bash
# Aktuellen Pfad prüfen
xcode-select -p
# Sollte zeigen: /Library/Developer/CommandLineTools (alt)

# Auf Xcode umstellen
sudo xcode-select -s /Applications/Xcode.app

# Verifizieren
xcode-select -p
# Sollte jetzt zeigen: /Applications/Xcode.app/Contents/Developer

# Swift Version prüfen
swift --version
# Sollte "Apple Swift version 6.x" zeigen
```

### 4️⃣ Swift Tool bauen

```bash
cd packaging/screencapture_tool

# Clean build
./build.sh clean

# Build
./build.sh
```

**Erwartete Ausgabe**:
```
==========================================
Building ScreenCapture Audio Recorder
==========================================

Swift version:
Apple Swift version 6.1.2...

Building in release mode...
[Kompilierung...]

✓ Build successful!

Binary: .build/release/screencapture-recorder
Size: ~500KB
```

### 5️⃣ Testen

```bash
# Test 1: Ist ScreenCaptureKit verfügbar?
.build/release/screencapture-recorder test

# Test 2: Displays listen
.build/release/screencapture-recorder list-devices

# Test 3: 5 Sekunden Audio aufnehmen
.build/release/screencapture-recorder record --output test.wav --duration 5
```

Beim ersten `test` oder `record` Befehl wird macOS nach **Screen Recording Permission** fragen!

### 6️⃣ Permission erteilen

Wenn die Permission-Anfrage kommt:
1. System Settings öffnet sich automatisch
2. Privacy & Security → Screen Recording
3. Terminal (oder deine IDE) aktivieren
4. Terminal/IDE neu starten
5. Nochmal versuchen

---

## ✅ Erfolg-Checklist

- [ ] Xcode installiert
- [ ] `xcode-select -p` zeigt `/Applications/Xcode.app/...`
- [ ] `swift --version` funktioniert
- [ ] `./build.sh` kompiliert erfolgreich
- [ ] `test` command funktioniert
- [ ] Screen Recording Permission erteilt
- [ ] `record` command erstellt WAV-Datei

---

## 🐛 Troubleshooting

### "xcrun: error: unable to find utility"
→ Xcode Command Line Tools noch nicht installiert
```bash
xcode-select --install
```

### "Invalid manifest" Fehler (wie vorher)
→ Command Line Tools zeigen noch auf alte Installation
```bash
sudo xcode-select -s /Applications/Xcode.app
```

### Build funktioniert, aber keine Permission
→ Permission in System Settings manuell setzen:
- System Settings → Privacy & Security → Screen Recording
- Terminal oder deine IDE hinzufügen

---

## 📝 Nächste Schritte

Nach erfolgreichem Build:
1. Python-Wrapper erstellen (`core/screencapture_recorder.py`)
2. Integration in `core/recorder.py`
3. UI Update in `ui/widgets/recording_widget.py`
4. Testing
5. PyInstaller Integration

Claude hilft dir bei jedem Schritt! 🤖

---

## ⏱️ Geschätzter Zeitaufwand

- Xcode Download + Installation: 30-60 Minuten
- Setup + erster Build: 10 Minuten
- Testing + Debugging: 20 Minuten
- **Total für heute**: ~1-2 Stunden

Dann ist das Swift-Tool lauffähig und wir können mit der Python-Integration weitermachen.
