#!/usr/bin/env python3
"""
Find the right method to call ScreenCaptureKit
"""

import ScreenCaptureKit as SCK

print("Class methods on SCShareableContent:")
print("=" * 60)

# Get the class object
cls = SCK.SCShareableContent

# Look for class methods (start with uppercase or 'get', 'new', 'init')
for attr_name in dir(cls):
    if not attr_name.startswith("_"):
        try:
            attr = getattr(cls, attr_name)
            # Check if it looks like a class method
            if (
                "get" in attr_name.lower()
                or "new" in attr_name.lower()
                or "shareable" in attr_name.lower()
            ):
                print(f"  {attr_name}: {type(attr)}")
        except:
            pass

print("\n" + "=" * 60)
print("Looking for async completion methods...")
print("=" * 60)

for attr_name in dir(cls):
    if "completion" in attr_name.lower() or "handler" in attr_name.lower():
        print(f"  {attr_name}")

# Try to use PyObjC metadata
print("\n" + "=" * 60)
print("Checking PyObjC metadata...")
print("=" * 60)

try:
    import objc

    # Get class methods
    print("\nClass methods:")
    for sel in objc.class_getMethodList(cls.__class__):
        print(f"  {sel}")
except Exception as e:
    print(f"Error: {e}")

# Check documentation
print("\n" + "=" * 60)
print("Help on SCShareableContent:")
print("=" * 60)
try:
    import pydoc

    help_text = pydoc.render_doc(cls, "Help on %s")
    # Print first 2000 chars
    print(help_text[:2000])
except Exception as e:
    print(f"Error: {e}")
