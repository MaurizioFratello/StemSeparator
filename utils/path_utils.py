"""
Path Resolution Utilities

PURPOSE: Provide utilities for resolving and ensuring output paths are absolute
         and directories exist, preventing issues with relative paths in packaged apps.
CONTEXT: Packaged macOS apps have unpredictable working directories, so all paths
         must be resolved to absolute paths before use.
"""

from pathlib import Path
from typing import Optional
import os

from utils.logger import get_logger

logger = get_logger()


def _expand_home(path: Path) -> Path:
    """
    Expand a leading `~` / `~user` in a path-like value.

    WHY: `Path.resolve()` has no concept of a home directory. Settings arrive
    as `Path("~/Music/...")` (the string branch of `resolve_output_path` is not
    taken by the settings layer), so the literal `~` component was anchored to
    the current working directory and the app created a stray `~` folder inside
    the installation.
    """
    text = str(path).strip()
    if text.startswith("~"):
        return Path(os.path.expanduser(text))
    return path


def resolve_output_path(path: Optional[Path], default: Path) -> Path:
    """
    Resolve output path to absolute, ensuring directory exists.

    WHY: Packaged apps have unpredictable working directories. Relative paths
         must be resolved to absolute paths to ensure files are saved correctly.
         This function handles None/empty paths, relative paths, and ensures
         directories are created.

    Args:
        path: Optional path (may be None, relative, or absolute)
        default: Default path to use if path is None or empty

    Returns:
        Absolute Path object with directory created if needed

    Examples:
        >>> default = Path.home() / "Music" / "StemSeparator" / "separated"
        >>> resolve_output_path(None, default)
        Path('/Users/name/Music/StemSeparator/separated')
        >>> resolve_output_path(Path("output"), default)
        Path('/Users/name/output')  # Resolved relative to current working directory
        >>> resolve_output_path(Path("/absolute/path"), default)
        Path('/absolute/path')  # Already absolute, returned as-is
    """
    # If path is None or empty, use default
    if path is None:
        resolved = default.resolve()
        logger.debug(f"Using default output path: {resolved}")
    elif isinstance(path, str):
        # Handle string paths (e.g., from UI input)
        path_str = path.strip()
        if not path_str:
            resolved = default.resolve()
            logger.debug(f"Empty path string, using default: {resolved}")
        else:
            # WHY shared helper: `~` must expand identically for str and Path
            # input; the Path branch below is the one settings actually use.
            path_str = str(_expand_home(Path(path_str)))
            resolved = Path(path_str).resolve()
            logger.debug(f"Resolved string path '{path}' to: {resolved}")
    else:
        # Path object
        try:
            # WHY: expand `~` before resolve(); see `_expand_home`.
            resolved = _expand_home(path).resolve()
            logger.debug(f"Resolved path '{path}' to: {resolved}")
        except (OSError, RuntimeError) as e:
            # If resolution fails (e.g., path doesn't exist yet), try to construct absolute
            logger.warning(f"Could not resolve path '{path}': {e}. Using default.")
            resolved = default.resolve()

    # Ensure directory exists
    resolved.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured directory exists: {resolved}")

    return resolved


def ensure_directory_exists(path: Path) -> Path:
    """
    Ensure directory exists, creating it if necessary.

    WHY: Directory creation is needed before file operations. This function
         ensures the directory structure exists and returns the absolute path.

    Args:
        path: Path to directory (may be relative or absolute)

    Returns:
        Absolute Path object with directory created

    Examples:
        >>> ensure_directory_exists(Path("output"))
        Path('/Users/name/output')  # Created and returned as absolute
    """
    try:
        # WHY: same `~` handling as `resolve_output_path`; a home-relative path
        # would otherwise be anchored to the current working directory.
        resolved = _expand_home(path).resolve()
    except (OSError, RuntimeError):
        # If path doesn't exist yet, convert to absolute based on current working directory
        if path.is_absolute():
            resolved = path
        else:
            resolved = Path.cwd() / _expand_home(path)

    # Create directory if it doesn't exist
    resolved.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured directory exists: {resolved}")

    return resolved

