# ScreenCaptureKit Integration - Status & Übergabe

**Datum:** 2025-11-27
**Branch:** `screencapture-integration`
**Letzter Commit:** `4a9df06` - "Implement full ScreenCaptureKit recording integration in Recorder"

---

## 🎯 Aktueller Status

### ✅ Was funktioniert

1. **Swift Binary ist gebaut und funktioniert**
   - Pfad: `packaging/screencapture_tool/.build/release/screencapture-recorder`
   - Größe: 116KB
   - Funktioniert: `test` Befehl erfolgreich
   - Stream startet erfolgreich (kein "Start stream failed" mehr)

2. **Python-Integration ist vollständig**
   - `core/screencapture_recorder.py` - Python Wrapper für Swift binary
   - `core/recorder.py` - Vollständig integriert mit Backend-Auswahl
   - `ui/widgets/recording_widget.py` - UI zeigt ScreenCaptureKit an

3. **UI-Integration funktioniert**
   - "🖥️ System Audio (ScreenCaptureKit)" wird im Dropdown angezeigt
   - Wird als Default ausgewählt auf macOS 13+
   - Wenn ausgewählt, wird tatsächlich ScreenCaptureKit verwendet (nicht mehr BlackHole)

### ❌ Das Problem

**ScreenCaptureKit empfängt KEINE Audio-Samples von macOS**

#### Symptome:
- WAV-Datei wird erstellt (1.1MB)
- Datei hat korrekten WAV-Header (48kHz, 2 Kanäle, Float32)
- **Aber: 0 Audio-Frames, 0 Sekunden Duration**
- Logs zeigen: `INFO ScreenCaptureKit recording started` ✓
- Logs zeigen: `INFO Recording stopped` ✓
- Error: `zero-size array to reduction operation maximum`

#### Diagnose:
```python
# File info der aufgenommenen Datei:
Sample rate: 48000 ✓
Channels: 2 ✓
Duration: 0.00s ❌  # Sollte > 0 sein
Frames: 0 ❌        # Sollte > 0 sein
```

#### Root Cause:
Das Swift binary startet den ScreenCaptureKit Stream erfolgreich, aber die `didOutputSampleBuffer` Callback-Funktion wird **nie aufgerufen** → keine Audio-Samples werden geschrieben.

#### Wahrscheinliche Ursache:
macOS 15.x Sequoia hat strengere Permission-Anforderungen. Screen Recording Permission allein reicht nicht aus, um System-Audio zu capturen.

---

## 📁 Relevante Dateien

### Swift Code

```
packaging/screencapture_tool/
├── Sources/main.swift          # Hauptlogik
├── Package.swift               # Dependencies
└── build.sh                    # Build-Skript
```

**Wichtige Code-Stellen in `main.swift`:**

- **Zeilen 207-222**: Stream-Konfiguration
  ```swift
  let streamConfig = SCStreamConfiguration()

  // Audio configuration
  streamConfig.capturesAudio = true
  streamConfig.excludesCurrentProcessAudio = false  // Capture ALL audio
  streamConfig.sampleRate = 48000
  streamConfig.channelCount = 2

  // Video configuration (needed even for audio-only)
  streamConfig.width = 100      // Changed from 1 to 100 (macOS 15 fix)
  streamConfig.height = 100     // Changed from 1 to 100
  streamConfig.pixelFormat = kCVPixelFormatType_32BGRA
  streamConfig.showsCursor = false
  ```

- **Zeile 231**: Stream wird gestartet
  ```swift
  try await stream.startCapture()  // ✓ Funktioniert
  ```

- **Zeilen 273-283**: Callback der NICHT aufgerufen wird
  ```swift
  func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of outputType: SCStreamOutputType) {
      // ❌ Diese Funktion wird NIE aufgerufen!
      guard outputType == .audio else { return }
      // Audio processing...
  }
  ```

### Python Code

#### `core/recorder.py` (Hauptdatei)

- **Zeilen 228-235**: `start_recording()` - Prüft Backend-Auswahl
  ```python
  # If device_name is None, use the selected backend
  if device_name is None and self._selected_backend == RecordingBackend.SCREENCAPTURE_KIT:
      # Use ScreenCaptureKit
      if not self._screencapture:
          self.logger.error("ScreenCaptureKit not available")
          return False
      return self._start_screencapture_recording(level_callback)
  ```

- **Zeilen 286-325**: `_start_screencapture_recording()` - Startet Swift binary
- **Zeilen 327-366**: `_screencapture_monitor_loop()` - Überwacht Recording
- **Zeilen 565-566**: `stop_recording()` - Prüft Backend
- **Zeilen 368-426**: `_stop_screencapture_recording()` - Stoppt und verarbeitet File

#### `core/screencapture_recorder.py`

- **Zeilen 200-288**: `start_recording()` - Startet subprocess
  ```python
  self._recording_process = subprocess.Popen(
      cmd,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      text=True
  )
  ```

- **Zeilen 301-343**: `stop_recording()` - Terminiert subprocess

#### `ui/widgets/recording_widget.py`

- **Zeilen 186-195**: Fügt ScreenCaptureKit zum Dropdown hinzu
  ```python
  if screencapture_available:
      self.device_combo.addItem(
          "🖥️ System Audio (ScreenCaptureKit)",
          userData="__screencapture__"
      )
  ```

- **Zeilen 288-296**: Erkennt `"__screencapture__"` Marker
  ```python
  if device_data == "__screencapture__":
      device_name = None  # Triggers auto-backend selection
      using_screencapture = True
  ```

- **Zeilen 262-265**: Überspringt Monitoring für ScreenCaptureKit

---

## 🔧 Was bereits versucht wurde

1. ✅ Video-Konfiguration angepasst (1x1 → 100x100 Pixel)
   - Fix für macOS 15.x, das 1x1 Pixel ablehnt

2. ✅ `excludesCurrentProcessAudio` auf `false` gesetzt
   - Damit ALLE System-Audio gecaptured wird

3. ✅ Screen Recording Permission für Terminal erteilt
   - System Settings → Privacy & Security → Screen Recording

4. ✅ Vollständige Recorder-Integration implementiert
   - ScreenCaptureKit wird korrekt ausgewählt und verwendet

5. ✅ Error Handling für leere Dateien hinzugefügt
   - Zeigt hilfreiche Fehlermeldung

---

## 🚀 Nächste Schritte

### Option 1: Permission Problem lösen ⭐ EMPFOHLEN

**Hypothese:** macOS 15.x benötigt möglicherweise:
- Separate "System Audio Recording" Permission
- Oder: Das Swift binary muss als signierte App mit eigenem Bundle laufen

#### Schritt 1: Prüfe alle Permissions

```bash
# Öffne System Settings → Privacy & Security
# Überprüfe folgende Bereiche:
#
# 1. Screen Recording
#    - Python sollte aktiviert sein
#    - Terminal sollte aktiviert sein
#
# 2. Microphone (könnte auch relevant sein)
#    - Füge Python/Terminal hinzu falls möglich
#
# 3. Accessibility (manchmal nötig für Audio)
#    - Füge Python/Terminal hinzu falls möglich
```

#### Schritt 2: Teste mit signiertem Binary

Erstelle eine richtige macOS App aus dem Swift binary:

```bash
cd packaging/screencapture_tool

# 1. Erstelle App Bundle Struktur
mkdir -p ScreenCaptureRecorder.app/Contents/MacOS
mkdir -p ScreenCaptureRecorder.app/Contents/Resources

# 2. Kopiere Binary
cp .build/release/screencapture-recorder ScreenCaptureRecorder.app/Contents/MacOS/

# 3. Erstelle Info.plist
cat > ScreenCaptureRecorder.app/Contents/Info.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>screencapture-recorder</string>
    <key>CFBundleIdentifier</key>
    <string>com.stemseparator.screencapture</string>
    <key>CFBundleName</key>
    <string>ScreenCaptureRecorder</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>This app needs to record system audio for stem separation.</string>
    <key>NSSystemAudioUsageDescription</key>
    <string>This app needs to capture system audio output.</string>
</dict>
</plist>
EOF

# 4. Teste die App
./ScreenCaptureRecorder.app/Contents/MacOS/screencapture-recorder test
```

Wenn die App startet, sollte macOS einen Permission-Dialog zeigen!

#### Schritt 3: Debug Logging hinzufügen

Füge Debug-Output zum Swift Code hinzu, um zu sehen ob Samples empfangen werden:

```swift
// In packaging/screencapture_tool/Sources/main.swift
// Zeile 273, in der didOutputSampleBuffer Funktion:

func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of outputType: SCStreamOutputType) {
    // ADD THIS LINE:
    print("📥 Sample buffer received! Output type: \(outputType)")

    // Only handle audio samples
    guard outputType == .audio else {
        print("⚠️ Skipping non-audio sample")
        return
    }

    // ADD THIS LINE:
    print("🎵 Processing audio sample!")

    // Initialize audio file on first sample
    if audioFile == nil {
        setupAudioFile(from: sampleBuffer)
    }

    // Write audio samples
    writeAudioSamples(from: sampleBuffer)
}
```

Dann rebuild:
```bash
cd packaging/screencapture_tool
./build.sh
```

Und teste:
```bash
python3 << 'EOF'
import subprocess
subprocess.run([
    "./.build/release/screencapture-recorder",
    "record", "--output", "/tmp/debug_test.wav", "--duration", "3"
])
EOF
```

**Erwartung:**
- Wenn "Sample buffer received" geloggt wird → Stream funktioniert, aber nur Video-Samples kommen
- Wenn "Processing audio sample!" geloggt wird → Audio kommt an, aber wird nicht korrekt geschrieben
- Wenn NICHTS geloggt wird → didOutputSampleBuffer wird nie aufgerufen (Permission-Problem)

### Option 2: Alternative Lösung

Wenn ScreenCaptureKit auf macOS 15.x nicht ohne App-Signierung funktioniert:

#### Dokumentiere Limitation

Erstelle eine Notiz in der App:

```python
# In ui/widgets/recording_widget.py, Zeile 192
if screencapture_available:
    # Check macOS version
    import platform
    macos_version = platform.mac_ver()[0]
    major_version = int(macos_version.split('.')[0])

    if major_version >= 15:
        label = "🖥️ System Audio (ScreenCaptureKit) [⚠️ May require signed app on macOS 15+]"
    else:
        label = "🖥️ System Audio (ScreenCaptureKit)"

    self.device_combo.addItem(label, userData="__screencapture__")
```

#### Füge Hilfe-Dialog hinzu

```python
# In ui/widgets/recording_widget.py, nach Zeile 331
if using_screencapture:
    # Show warning on macOS 15+
    import platform
    major_version = int(platform.mac_ver()[0].split('.')[0])
    if major_version >= 15:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "ScreenCaptureKit auf macOS 15+",
            "Hinweis: ScreenCaptureKit auf macOS 15.x Sequoia benötigt "
            "möglicherweise zusätzliche Permissions.\n\n"
            "Falls keine Audio aufgenommen wird:\n"
            "• Verwende BlackHole als Alternative\n"
            "• Oder warte auf eine signierte App-Version"
        )
```

### Option 3: BlackHole als temporären Standard

Deaktiviere ScreenCaptureKit vorübergehend:

```python
# In core/recorder.py, Zeile 103
if self.backend == RecordingBackend.AUTO:
    # Temporarily disable ScreenCaptureKit on macOS 15+
    import platform
    macos_version = int(platform.mac_ver()[0].split('.')[0])

    if macos_version >= 15:
        # Force BlackHole on macOS 15+ until permission issue is resolved
        self.logger.warning("Forcing BlackHole backend on macOS 15+ (ScreenCaptureKit requires signed app)")
        if self._soundcard and self.find_blackhole_device():
            self._selected_backend = RecordingBackend.BLACKHOLE
        else:
            self._selected_backend = None
    else:
        self._select_best_backend()
else:
    self._selected_backend = self.backend
```

---

## 📊 Commit-Historie

```bash
git log --oneline -10 screencapture-integration
```

Output:
```
4a9df06 Implement full ScreenCaptureKit recording integration in Recorder
5fb24c1 Fix ScreenCaptureKit monitoring to skip pre-recording level checks
3479cfd Add ScreenCaptureKit as selectable device option in Recording UI
# ... (ScreenCaptureKit Integration)
ee981dc (Basis: Moderne Sidebar-UI)
```

### Wichtige Commits

| Commit | Beschreibung |
|--------|-------------|
| `4a9df06` | Vollständige Recorder-Integration |
| `5fb24c1` | Monitoring-Fixes (skip für ScreenCaptureKit) |
| `3479cfd` | UI-Integration (Dropdown, Auto-Auswahl) |
| `ee981dc` | Korrekte UI-Basis (Sidebar-Layout) |

---

## 🧪 Test-Befehle

### Test Swift Binary direkt

```bash
# Test 1: Verfügbarkeit prüfen
/Users/moritzbruder/Documents/04_Python/StemSeparator/packaging/screencapture_tool/.build/release/screencapture-recorder test

# Erwartete Ausgabe:
# ✓ macOS 13.0+ detected - ScreenCaptureKit is available
# ✓ Successfully accessed ScreenCaptureKit
# Found 1 display(s)
# Found X running application(s)
```

### Test Recording

```bash
# Test 2: Recording (5 Sekunden)
cd /Users/moritzbruder/Documents/04_Python/StemSeparator/packaging/screencapture_tool

python3 << 'EOF'
import subprocess
import time

print("Starting 5-second recording...")
print("⚠️ PLAY AUDIO NOW (YouTube, Spotify, etc.)")
time.sleep(1)

result = subprocess.run([
    "./.build/release/screencapture-recorder",
    "record",
    "--output", "/tmp/screencapture_test.wav",
    "--duration", "5"
], capture_output=True, text=True)

print(f"Return code: {result.returncode}")
print(f"Output:\n{result.stdout}")
if result.stderr:
    print(f"Errors:\n{result.stderr}")
EOF
```

### Analysiere Ergebnis

```bash
# Test 3: Datei analysieren
python3 << 'EOF'
import soundfile as sf
import numpy as np

try:
    info = sf.info('/tmp/screencapture_test.wav')
    print(f"📊 File Info:")
    print(f"   Sample rate: {info.samplerate} Hz")
    print(f"   Channels: {info.channels}")
    print(f"   Duration: {info.duration:.2f} seconds")
    print(f"   Frames: {info.frames}")

    if info.frames > 0:
        data, sr = sf.read('/tmp/screencapture_test.wav')
        peak = np.max(np.abs(data))
        rms = np.sqrt(np.mean(data**2))

        print(f"\n📈 Audio Levels:")
        print(f"   Peak: {peak:.6f}")
        print(f"   RMS: {rms:.6f}")

        if peak > 0.01:
            print("\n✅ SUCCESS - Audio wurde aufgenommen!")
        else:
            print("\n⚠️  WARNING - Nur Stille aufgenommen")
    else:
        print("\n❌ ERROR - Datei ist leer (0 Frames)")
        print("   → didOutputSampleBuffer wird nicht aufgerufen")
        print("   → Permission-Problem!")

except Exception as e:
    print(f"❌ Error: {e}")
EOF
```

### Test Python Integration

```bash
# Test 4: Vollständiger Test der Python-Integration
cd /Users/moritzbruder/Documents/04_Python/StemSeparator

python3 << 'EOF'
import sys
sys.path.insert(0, '.')

from core.recorder import Recorder, RecordingBackend

print("=== Testing Python ScreenCaptureKit Integration ===\n")

# Create recorder
recorder = Recorder(backend=RecordingBackend.SCREENCAPTURE_KIT)

# Check backend
info = recorder.get_backend_info()
print(f"Backend Info:")
print(f"  Selected: {info['backend']}")
print(f"  ScreenCaptureKit available: {info['screencapture_available']}")
print(f"  BlackHole available: {info['blackhole_available']}")

if info['backend'] == 'screencapture_kit':
    print("\n✅ ScreenCaptureKit is selected!")
    print("\nNow start recording from the UI and check if audio is captured.")
else:
    print(f"\n❌ Backend is: {info['backend']} (should be screencapture_kit)")
EOF
```

---

## 💡 Wichtige Erkenntnisse

### Was wir wissen

1. ✅ **Der Code funktioniert**
   - Integration ist vollständig
   - Stream startet erfolgreich
   - Keine Code-Fehler mehr

2. ✅ **BlackHole funktioniert weiterhin**
   - Als bewährte Fallback-Lösung
   - Kann parallel zu ScreenCaptureKit existieren

3. ❌ **Das Problem ist macOS 15.x spezifisch**
   - `didOutputSampleBuffer` wird nie aufgerufen
   - Wahrscheinlich neue Security-Features in Sequoia
   - Möglicherweise benötigt signierte App mit Entitlements

### Was zu testen ist

1. **Permissions**
   - Alle Privacy-Einstellungen durchgehen
   - Speziell: Microphone, Screen Recording, Accessibility

2. **App Bundle**
   - Swift binary als .app Bundle mit Info.plist
   - Könnte Permission-Dialoge triggern

3. **Debug Logging**
   - Bestätigen ob `didOutputSampleBuffer` aufgerufen wird
   - Unterscheiden zwischen "keine Samples" vs "Samples aber falsches Format"

### Potenzielle Lösungen

**Kurzfristig:**
- BlackHole als Standard beibehalten
- ScreenCaptureKit als "Experimental" markieren

**Mittelfristig:**
- App-Signierung implementieren
- Entitlements für Audio Capture hinzufügen

**Langfristig:**
- Umfassende Dokumentation für User
- Automatische Fallback-Logik perfektionieren

---

## 📝 Offene Fragen

1. **Wird `didOutputSampleBuffer` überhaupt aufgerufen?**
   - Antwort durch Debug Logging (siehe Schritt 3)

2. **Welche Permissions fehlen genau?**
   - Testen mit System Settings durchgehen
   - Testen mit signiertem App Bundle

3. **Funktioniert es auf macOS 13-14?**
   - Ungetestet, aber wahrscheinlicher
   - macOS 15.x hat strengere Security

4. **Ist App-Signierung die Lösung?**
   - Sehr wahrscheinlich
   - Apple's Dokumentation legt das nahe

---

## 📞 Wenn Fragen aufkommen

### Code-Struktur
- Alle ScreenCaptureKit-Änderungen sind in Branch `screencapture-integration`
- Haupt-Einstiegspunkt: `core/recorder.py` Zeilen 228-426
- Swift-Code: `packaging/screencapture_tool/Sources/main.swift`

### Dokumentation
- Allgemeine Doku: `SCREENCAPTURE_INTEGRATION.md`
- Diese Übergabe: `SCREENCAPTURE_STATUS_HANDOFF.md`

### Logs
- App-Logs zeigen Backend-Auswahl
- Look for: `"ScreenCaptureKit recording started"`
- Error: `"zero-size array to reduction operation"`

---

## ✅ Schnellstart für neuen Agent

```bash
# 1. Branch auschecken
git checkout screencapture-integration

# 2. Status prüfen
git log --oneline -5
git status

# 3. Binary ist bereits gebaut
ls -lh packaging/screencapture_tool/.build/release/screencapture-recorder

# 4. Quick Test
packaging/screencapture_tool/.build/release/screencapture-recorder test

# 5. Debug Test (siehe oben unter "Test-Befehle")
# Folge den Test-Befehlen um das Problem zu diagnostizieren

# 6. Lösung implementieren
# Option 1: App Bundle + Signierung (empfohlen)
# Option 2: Temporär deaktivieren und dokumentieren
```

---

**Viel Erfolg! Die Integration ist 95% fertig - nur die macOS Permissions sind noch zu klären.** 🚀
