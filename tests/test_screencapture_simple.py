#!/usr/bin/env python3
"""
Simple test to see what's available in ScreenCaptureKit
"""

import sys

# Check macOS version first
import platform
mac_version = platform.mac_ver()[0]
major = int(mac_version.split('.')[0])

if major < 13:
    print(f"ERROR: macOS {mac_version} - ScreenCaptureKit requires 13.0+")
    sys.exit(1)

print(f"macOS {mac_version} - OK")
print()

# Import
try:
    import ScreenCaptureKit as SCK
    print("✓ ScreenCaptureKit imported")
except ImportError as e:
    print(f"ERROR: {e}")
    sys.exit(1)

# Check what's available
print("\nSCShareableContent attributes:")
print("-" * 60)
for attr in dir(SCK.SCShareableContent):
    if not attr.startswith('_'):
        print(f"  {attr}")

print("\nTrying to get current process shareable content...")
print("-" * 60)

try:
    # This is the simpler method that doesn't need async
    content = SCK.SCShareableContent.currentProcessShareableContent()
    print(f"✓ Got current process content")
    print(f"  Type: {type(content)}")

    if content:
        print(f"  Displays: {len(content.displays()) if hasattr(content, 'displays') else 'N/A'}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\nTrying getCurrentProcessShareableContent...")
try:
    content = SCK.SCShareableContent.getCurrentProcessShareableContent()
    print(f"✓ Got content: {content}")
except Exception as e:
    print(f"Method doesn't exist or error: {e}")

# Check if we need permissions
print("\nChecking screen capture access...")
try:
    from Quartz import CGPreflightScreenCaptureAccess, CGRequestScreenCaptureAccess

    has_access = CGPreflightScreenCaptureAccess()
    print(f"Has screen capture access: {has_access}")

    if not has_access:
        print("\nRequesting permission...")
        granted = CGRequestScreenCaptureAccess()
        print(f"Permission granted: {granted}")
        if not granted:
            print("\n⚠️  Please grant Screen Recording permission in:")
            print("   System Settings → Privacy & Security → Screen Recording")
except ImportError:
    print("Quartz not available for permission check")
except Exception as e:
    print(f"Permission check error: {e}")

