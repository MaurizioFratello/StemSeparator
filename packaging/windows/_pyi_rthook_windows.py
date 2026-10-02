"""
PyInstaller runtime hook for the Windows build (PKG-03 / PKG-04).

Executed by the bootloader *before* `main.py` and before any first-party module
is imported, which is the only moment where it reliably matters: Python 3.8+
stopped searching `PATH` for DLLs, so a bundled CUDA-enabled `torch` raises
`ImportError: DLL load failed while importing _C` unless every directory that
holds its dependencies is registered with `os.add_dll_directory` first. The app
itself runs the same calls in `main.py`; doing it here as well makes the bundle
correct for any code path that imports torch before that bootstrap runs, and
both helpers are idempotent.
"""

import sys

if sys.platform == "win32" and getattr(sys, "frozen", False):
    try:
        from utils.platform_utils import (
            configure_native_library_dirs,
            ensure_binaries_on_path,
            torch_library_dirs,
        )

        configure_native_library_dirs(torch_library_dirs())
        ensure_binaries_on_path()
    except Exception as exc:  # pragma: no cover - windowed process has no stderr
        # A windowed build has no console, so a hook failure would be invisible.
        import pathlib
        import traceback

        try:
            report = pathlib.Path(sys._MEIPASS) / "rthook-error.log"  # noqa: SLF001
            report.write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
