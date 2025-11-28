# ScreenCapture Audio Recorder

Swift CLI tool for recording system audio on macOS 13.0+ using ScreenCaptureKit.

## Why This Tool?

This tool allows recording system audio **without requiring BlackHole** or other virtual audio drivers. It uses macOS's native ScreenCaptureKit framework (available since macOS Ventura 13.0).

## Requirements

- macOS 13.0 (Ventura) or later
- Xcode with Command Line Tools
- Screen Recording permission

## Building

### With Xcode:

```bash
# Open in Xcode
open screencapture-recorder.xcodeproj

# Build (Cmd+B)
```

### With xcodebuild (Command Line):

```bash
# Build for arm64 (Apple Silicon)
xcodebuild -project screencapture-recorder.xcodeproj \
    -scheme screencapture-recorder \
    -configuration Release \
    -arch arm64 \
    ONLY_ACTIVE_ARCH=NO

# Binary will be in:
# build/Release/screencapture-recorder
```

### With swift build (if using Package.swift):

```bash
swift build -c release
# Binary: .build/release/screencapture-recorder
```

## Usage

```bash
# Test if ScreenCaptureKit is available
./screencapture-recorder test

# List available displays
./screencapture-recorder list-devices

# Record 10 seconds of system audio
./screencapture-recorder record --output recording.wav --duration 10

# Record 30 seconds
./screencapture-recorder record --output recording.wav --duration 30
```

## Permissions

The first time you run the tool, macOS will prompt for **Screen Recording** permission:

1. System Settings → Privacy & Security → Screen Recording
2. Enable permission for Terminal (or your app)
3. Restart the tool

## Integration with Python

The Python wrapper is in `core/screencapture_recorder.py`:

```python
from core.screencapture_recorder import ScreenCaptureRecorder

recorder = ScreenCaptureRecorder()

if recorder.is_available():
    # Use ScreenCaptureKit
    recorder.start_recording()
else:
    # Fall back to BlackHole
    from core.recorder import get_recorder
    recorder = get_recorder()
```

## Output Format

- **Format**: WAV (PCM Float32)
- **Sample Rate**: 48kHz
- **Channels**: Stereo (2 channels)

## Known Limitations

- **macOS 13.0+ only** - older versions need BlackHole
- **No per-app filtering yet** - records all system audio
- **Screen Recording permission required** - even though we only record audio

## Troubleshooting

### "Operation not permitted"
→ Grant Screen Recording permission in System Settings

### "ScreenCaptureKit not available"
→ Check macOS version: `sw_vers`

### Build fails
→ Make sure Xcode Command Line Tools point to Xcode:
```bash
sudo xcode-select -s /Applications/Xcode.app
```
