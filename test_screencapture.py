#!/usr/bin/env python3
"""
Test script for ScreenCaptureKit via PyObjC

This tests if we can use ScreenCaptureKit from Python to record system audio
without requiring BlackHole or other virtual audio drivers.
"""

import sys
import platform
import asyncio
from pathlib import Path

print("=" * 60)
print("ScreenCaptureKit Test Script")
print("=" * 60)
print()

# Check macOS version
mac_version = platform.mac_ver()[0]
print(f"macOS Version: {mac_version}")

major, minor, patch = map(int, mac_version.split('.')[:3])
if major < 13:
    print("❌ ERROR: ScreenCaptureKit requires macOS 13.0 (Ventura) or later")
    print(f"   Your version: {mac_version}")
    sys.exit(1)
else:
    print(f"✓ macOS {mac_version} - ScreenCaptureKit should be available")

print()

# Try to import ScreenCaptureKit
print("Testing PyObjC ScreenCaptureKit import...")
try:
    import ScreenCaptureKit as SCK
    print("✓ ScreenCaptureKit imported successfully")
except ImportError as e:
    print(f"❌ Failed to import ScreenCaptureKit: {e}")
    print("\nInstall with:")
    print("  pip install pyobjc-framework-ScreenCaptureKit")
    sys.exit(1)

print()

# Test 1: Get shareable content (displays and apps)
print("Test 1: Getting shareable content...")
print("-" * 60)

async def test_shareable_content():
    """Test if we can access shareable content"""
    try:
        # Get shareable content - this will trigger permission prompt if needed
        # In PyObjC, we need to use the class method correctly
        from Foundation import NSError

        # Try synchronous version first (easier to debug)
        content, error = SCK.SCShareableContent.getShareableContentWithCompletionHandler_(None)

        if error is not None:
            raise Exception(f"Error: {error}")

        print(f"✓ Successfully accessed ScreenCaptureKit")
        print(f"  Found {len(content.displays())} display(s)")
        print(f"  Found {len(content.applications())} application(s)")

        print("\nDisplays:")
        for i, display in enumerate(content.displays()):
            print(f"  [{i}] Display ID: {display.displayID()}")
            print(f"      Resolution: {display.width()}x{display.height()}")

        return content

    except Exception as e:
        print(f"❌ Failed to get shareable content: {e}")
        print("\nNote: You may need to grant Screen Recording permission:")
        print("  System Settings → Privacy & Security → Screen Recording")
        print("  → Enable permission for Terminal/Python")
        return None

# Run the async test
try:
    content = asyncio.run(test_shareable_content())
except Exception as e:
    print(f"❌ Async operation failed: {e}")
    content = None

print()

if content is None:
    print("❌ Cannot proceed without shareable content access")
    sys.exit(1)

# Test 2: Create a simple stream configuration
print("Test 2: Creating stream configuration...")
print("-" * 60)

try:
    from ScreenCaptureKit import SCStreamConfiguration

    config = SCStreamConfiguration.alloc().init()

    # Audio settings
    config.setCapturesAudio_(True)
    config.setExcludesCurrentProcessAudio_(True)
    config.setSampleRate_(48000)
    config.setChannelCount_(2)

    # Minimal video settings (we don't need video, but we have to configure it)
    config.setWidth_(1)
    config.setHeight_(1)

    print("✓ Stream configuration created")
    print(f"  Captures audio: {config.capturesAudio()}")
    print(f"  Sample rate: {config.sampleRate()}")
    print(f"  Channels: {config.channelCount()}")

except Exception as e:
    print(f"❌ Failed to create stream configuration: {e}")
    sys.exit(1)

print()

# Test 3: Create content filter
print("Test 3: Creating content filter...")
print("-" * 60)

try:
    from ScreenCaptureKit import SCContentFilter

    # Get first display
    display = content.displays()[0]

    # Create filter for display (captures all audio from that display)
    content_filter = SCContentFilter.alloc().initWithDisplay_excludingApplications_exceptingWindows_(
        display,
        [],  # Don't exclude any applications
        []   # Don't except any windows
    )

    print("✓ Content filter created")
    print(f"  Capturing from display: {display.displayID()}")

except Exception as e:
    print(f"❌ Failed to create content filter: {e}")
    sys.exit(1)

print()

# Test 4: Try to create and start a stream (the critical test!)
print("Test 4: Creating and testing stream...")
print("-" * 60)
print("⚠️  This is the test from GitHub Issue #647")
print("   If audio callbacks don't fire, PyObjC has the known issue")
print()

from Foundation import NSObject
from ScreenCaptureKit import SCStream, SCStreamOutputType
import time

class AudioStreamOutput(NSObject):
    """Delegate to receive audio samples"""

    def init(self):
        self = super().init()
        if self is None:
            return None
        self.sample_count = 0
        self.audio_received = False
        return self

    def stream_didOutputSampleBuffer_ofType_(self, stream, sample_buffer, output_type):
        """Called when stream outputs a sample buffer"""
        if output_type == SCStreamOutputType.audio:
            self.sample_count += 1
            self.audio_received = True
            print(f"  ✓ Audio sample received! (count: {self.sample_count})")

try:
    # Create stream
    stream = SCStream.alloc().initWithFilter_configuration_delegate_(
        content_filter,
        config,
        None  # No delegate (we use output handler instead)
    )

    print("✓ Stream created")

    # Create output handler
    output_handler = AudioStreamOutput.alloc().init()

    # Add stream output for audio
    from dispatch import dispatch_get_global_queue, DISPATCH_QUEUE_PRIORITY_HIGH
    queue = dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_HIGH, 0)

    error = stream.addStreamOutput_type_sampleHandlerQueue_error_(
        output_handler,
        SCStreamOutputType.audio,
        queue,
        None
    )

    if error[1] is not None:
        print(f"❌ Failed to add stream output: {error[1]}")
        sys.exit(1)

    print("✓ Audio output handler added")
    print()
    print("Starting capture stream...")

    # Start capture (async)
    async def start_and_test_stream():
        try:
            await stream.startCaptureWithCompletionHandler_(None)
            print("✓ Stream started successfully")
            print()
            print("Waiting 3 seconds for audio samples...")
            print("(Play some audio on your Mac to test)")

            # Wait and check for samples
            await asyncio.sleep(3)

            if output_handler.audio_received:
                print()
                print("=" * 60)
                print("🎉 SUCCESS! ScreenCaptureKit works with PyObjC!")
                print("=" * 60)
                print(f"Received {output_handler.sample_count} audio samples")
                print()
                print("✓ We can use PyObjC without needing a Swift tool!")
            else:
                print()
                print("=" * 60)
                print("⚠️  WARNING: No audio samples received")
                print("=" * 60)
                print("This is the known PyObjC issue from GitHub #647")
                print("The stream starts but audio callbacks don't fire.")
                print()
                print("→ We need the Swift CLI tool approach")

            # Stop stream
            await stream.stopCaptureWithCompletionHandler_(None)
            print("\n✓ Stream stopped")

            return output_handler.audio_received

        except Exception as e:
            print(f"❌ Stream error: {e}")
            return False

    # Run the stream test
    success = asyncio.run(start_and_test_stream())

    print()
    print("=" * 60)
    print("Test Complete!")
    print("=" * 60)

    if success:
        print("✅ PyObjC approach works - we can proceed without Swift!")
        sys.exit(0)
    else:
        print("❌ PyObjC has the audio callback issue")
        print("📝 Next steps:")
        print("   1. Install full Xcode (or fix CommandLineTools)")
        print("   2. Build the Swift CLI tool")
        print("   3. Use subprocess approach")
        sys.exit(1)

except Exception as e:
    print(f"❌ Stream test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
