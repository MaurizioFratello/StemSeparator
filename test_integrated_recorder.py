#!/usr/bin/env python3
"""
Test the integrated recorder with ScreenCaptureKit support
"""
import sys
sys.path.insert(0, '.')

from core.recorder import Recorder, RecordingBackend

print("=== Integrated Recorder Test ===\n")

# Create recorder with auto backend selection
recorder = Recorder(backend=RecordingBackend.AUTO)

# Get backend info
backend_info = recorder.get_backend_info()
print(f"Backend Info:")
print(f"  Selected: {backend_info['backend']}")
print(f"  ScreenCaptureKit available: {backend_info['screencapture_available']}")
print(f"  BlackHole available: {backend_info['blackhole_available']}")
print()

# List available devices
print("Available devices:")
devices = recorder.get_available_devices()
for device in devices:
    print(f"  - {device}")
print()

# Check if we can record
if backend_info['backend'] is None:
    print("❌ No recording backend available")
    print("\nPlease either:")
    print("  1. Grant Screen Recording permission for ScreenCaptureKit (macOS 13+)")
    print("  2. Or install BlackHole: brew install blackhole-2ch")
    sys.exit(1)

print(f"✓ Ready to record using: {backend_info['backend']}")
print()
print("NOTE: To actually test recording, you would need to:")
print("  1. Grant Screen Recording permission if using ScreenCaptureKit")
print("  2. Play some audio while recording")
print("  3. Call recorder.start_recording() and recorder.stop_recording()")
