#!/usr/bin/env python3
"""
Test script for Loop Export Dialog

Run this to see the loop export dialog with chunk settings (2/4/8 bars).
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from ui.dialogs.loop_export_dialog import LoopExportDialog


def main():
    """Test the loop export dialog"""
    app = QApplication(sys.argv)

    # Create dialog with sample parameters
    # - Detected BPM: 128.5 (will be rounded to 129)
    # - Audio duration: 180 seconds (3 minutes)
    # - Number of stems: 4 (for testing individual export preview)
    dialog = LoopExportDialog(detected_bpm=128.5, duration_seconds=180.0, num_stems=4)

    # Show dialog
    result = dialog.exec()

    if result == LoopExportDialog.Accepted:
        # User clicked "Export Loops"
        settings = dialog.get_settings()

        print("\n" + "=" * 60)
        print("LOOP EXPORT SETTINGS")
        print("=" * 60)
        print(f"BPM:          {settings.bpm}")
        print(f"Bars:         {settings.bars} bars")
        print(f"Sample Rate:  {settings.sample_rate} Hz")
        print(f"Bit Depth:    {settings.bit_depth} bit")
        print(f"Channels:     {'Stereo' if settings.channels == 2 else 'Mono'}")
        print(f"Format:       {settings.file_format}")
        print(f"Export Mode:  {settings.export_mode}")
        print("=" * 60)

        # Calculate preview info
        from utils.loop_math import compute_chunk_duration_seconds

        chunk_duration = compute_chunk_duration_seconds(settings.bpm, settings.bars)
        num_chunks = max(1, int(180.0 / chunk_duration))

        print(f"\nPreview:")
        print(f"  • Each chunk: ~{chunk_duration:.2f} seconds")
        print(f"  • Total chunks: ~{num_chunks}")
        print(
            f"  • Example filename: MyLoop_{settings.bpm}_{settings.bars}t_part01.{settings.file_format.lower()}"
        )
        print()
    else:
        # User clicked "Cancel"
        print("\nExport cancelled")

    return 0


if __name__ == "__main__":
    sys.exit(main())
