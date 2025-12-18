#!/usr/bin/env python3
"""
Diagnose script for ScreenCaptureKit availability

PURPOSE: Check why System Audio option is not available in Recording Tab
CONTEXT: Helps identify if issue is binary missing, permissions, or code bug
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.screencapture_recorder import ScreenCaptureRecorder, ScreenCaptureInfo
from core.recorder import Recorder
from utils.logger import get_logger

logger = get_logger()

def main():
    print("=" * 70)
    print("ScreenCaptureKit Diagnostic Tool")
    print("=" * 70)
    print()
    
    # 1. Check ScreenCaptureRecorder directly
    print("1. Checking ScreenCaptureRecorder...")
    screencapture = ScreenCaptureRecorder()
    info: ScreenCaptureInfo = screencapture.is_available()
    
    print(f"   Available: {info.available}")
    print(f"   macOS Version: {info.version}")
    if info.error:
        print(f"   Error: {info.error}")
    else:
        print("   ✓ ScreenCaptureKit is available!")
    print()
    
    # 2. Check binary path
    print("2. Binary Path Check...")
    if screencapture._binary_path:
        print(f"   ✓ Binary found: {screencapture._binary_path}")
        print(f"   Exists: {screencapture._binary_path.exists()}")
        print(f"   Executable: {screencapture._binary_path.is_file()}")
        import os
        print(f"   Has execute permission: {os.access(screencapture._binary_path, os.X_OK)}")
    else:
        print("   ✗ Binary not found")
        print("   Searched paths:")
        possible_paths = [
            Path(__file__).parent / "packaging/screencapture_tool/.build/release/screencapture-recorder",
            Path(__file__).parent / "packaging/screencapture_tool/.build/arm64-apple-macosx/release/screencapture-recorder",
            Path(__file__).parent / "packaging/screencapture_tool/.build/x86_64-apple-macosx/release/screencapture-recorder",
        ]
        for path in possible_paths:
            exists = "✓" if path.exists() else "✗"
            print(f"     {exists} {path}")
    print()
    
    # 3. Check Recorder backend info
    print("3. Checking Recorder Backend Info...")
    recorder = Recorder()
    backend_info = recorder.get_backend_info()
    print(f"   Backend: {backend_info.get('backend')}")
    print(f"   ScreenCapture Available: {backend_info.get('screencapture_available')}")
    print(f"   BlackHole Available: {backend_info.get('blackhole_available')}")
    print()
    
    # 4. Check permissions via Quartz (if available)
    print("4. Permission Check (via Quartz)...")
    try:
        from Quartz import CGPreflightScreenCaptureAccess
        has_permission = CGPreflightScreenCaptureAccess()
        if has_permission:
            print("   ✓ Screen Recording permission granted")
        else:
            print("   ✗ Screen Recording permission NOT granted")
            print("   → Grant permission in: System Settings → Privacy & Security → Screen Recording")
    except ImportError:
        print("   ⚠ Quartz not available (cannot check permissions directly)")
    except Exception as e:
        print(f"   ⚠ Permission check failed: {e}")
    print()
    
    # 5. Test binary directly (if found)
    if screencapture._binary_path and screencapture._binary_path.exists():
        print("5. Testing Binary...")
        import subprocess
        try:
            result = subprocess.run(
                [str(screencapture._binary_path), "test"],
                capture_output=True,
                text=True,
                timeout=10
            )
            print(f"   Return code: {result.returncode}")
            if result.stdout:
                print(f"   stdout: {result.stdout[:200]}")
            if result.stderr:
                print(f"   stderr: {result.stderr[:200]}")
            if result.returncode == 0:
                print("   ✓ Binary test passed")
            else:
                print("   ✗ Binary test failed")
        except subprocess.TimeoutExpired:
            print("   ✗ Binary test timed out (likely permission issue)")
        except Exception as e:
            print(f"   ✗ Binary test error: {e}")
    else:
        print("5. Skipping binary test (binary not found)")
    print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if info.available:
        print("✓ ScreenCaptureKit should be available in Recording Tab")
        print("  If it's not showing, check UI initialization code")
    else:
        print("✗ ScreenCaptureKit is NOT available")
        print(f"  Reason: {info.error}")
        print()
        print("SOLUTION:")
        if "binary not found" in info.error.lower():
            print("  1. Build the screencapture-recorder binary:")
            print("     cd packaging/screencapture_tool && ./build.sh")
        elif "permission" in info.error.lower():
            print("  1. Grant Screen Recording permission:")
            print("     System Settings → Privacy & Security → Screen Recording")
            print("  2. Enable permission for Terminal (or Python)")
            print("  3. Restart the application")
        elif "macOS" in info.error:
            print("  1. ScreenCaptureKit requires macOS 13.0+ (Ventura)")
            print(f"  2. Your version: {info.version}")
        else:
            print(f"  Fix the issue: {info.error}")
    
    print()

if __name__ == "__main__":
    main()

