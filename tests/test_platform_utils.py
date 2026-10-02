"""Behavioural tests for the platform-specific utility authority.

WHY this file exists: platform branches are cheap to regress on the developer's
host OS.  Every platform identity and filesystem location below is simulated
without touching the real user profile.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import platform_utils as platform  # noqa: E402


@pytest.fixture
def fake_home(monkeypatch, tmp_path):
    """Point every home-variable spelling at a scratch directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


@pytest.fixture
def set_platform(monkeypatch):
    """Select a target platform through the module's supported seam."""

    def select(value):
        monkeypatch.setattr(platform, "_platform_string", lambda: value)

    return select


class TestOperatingSystemIdentity:
    @pytest.mark.parametrize(
        ("value", "macos", "windows", "linux", "name"),
        [
            ("darwin", True, False, False, "macOS"),
            ("win32", False, True, False, "Windows"),
            ("linux", False, False, True, "Linux"),
            ("freebsd13", False, False, True, "Linux"),
            ("plan9", False, False, False, "plan9"),
            ("", False, False, False, "unknown"),
        ],
    )
    def test_predicates_and_label_match_platform(self, set_platform, value, macos, windows, linux, name):
        set_platform(value)

        assert platform.is_macos() is macos
        assert platform.is_windows() is windows
        assert platform.is_linux() is linux
        assert platform.os_name() == name


class TestUserDirectories:
    def test_linux_data_and_cache_honor_absolute_xdg_locations(self, monkeypatch, fake_home, set_platform, tmp_path):
        set_platform("linux")
        data = tmp_path / "xdg-data"
        cache = tmp_path / "xdg-cache"
        monkeypatch.setenv("XDG_DATA_HOME", str(data))
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))

        assert platform.user_data_dir() == data / platform.APP_DIR_NAME
        assert platform.user_cache_dir() == cache / platform.APP_DIR_NAME

    def test_linux_data_and_cache_ignore_relative_xdg_locations(self, monkeypatch, fake_home, set_platform):
        set_platform("linux")
        monkeypatch.setenv("XDG_DATA_HOME", "relative-data")
        monkeypatch.setenv("XDG_CACHE_HOME", "relative-cache")

        assert platform.user_data_dir() == fake_home / ".local" / "share" / platform.APP_DIR_NAME
        assert platform.user_cache_dir() == fake_home / ".cache" / platform.APP_DIR_NAME

    def test_windows_data_and_cache_prefer_local_app_data(self, monkeypatch, fake_home, set_platform, tmp_path):
        set_platform("win32")
        local = tmp_path / "local"
        appdata = tmp_path / "roaming"
        monkeypatch.setenv("LOCALAPPDATA", str(local))
        monkeypatch.setenv("APPDATA", str(appdata))

        assert platform.user_data_dir() == local / platform.APP_DIR_NAME
        assert platform.user_cache_dir() == local / platform.APP_DIR_NAME / "Cache"

    def test_windows_data_and_cache_fall_back_to_app_data(self, monkeypatch, fake_home, set_platform, tmp_path):
        set_platform("win32")
        appdata = tmp_path / "roaming"
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.setenv("APPDATA", str(appdata))

        assert platform.user_data_dir() == appdata / platform.APP_DIR_NAME
        assert platform.user_cache_dir() == appdata / platform.APP_DIR_NAME / "Cache"

    def test_windows_data_and_cache_fall_back_to_expanded_home(self, monkeypatch, fake_home, set_platform):
        set_platform("win32")
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.delenv("APPDATA", raising=False)

        assert platform.user_data_dir() == fake_home / platform.APP_DIR_NAME
        assert platform.user_cache_dir() == fake_home / platform.APP_DIR_NAME / "Cache"

    def test_macos_data_and_cache_use_library_locations(self, fake_home, set_platform):
        set_platform("darwin")

        assert platform.user_data_dir() == fake_home / "Library" / "Application Support" / platform.APP_DIR_NAME
        assert platform.user_cache_dir() == fake_home / "Library" / "Caches" / platform.APP_DIR_NAME

    @pytest.mark.parametrize("value", ["darwin", "linux", "win32"])
    def test_returned_user_directories_never_contain_literal_tilde(self, monkeypatch, fake_home, set_platform, value):
        set_platform(value)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.delenv("APPDATA", raising=False)

        assert "~" not in str(platform.user_data_dir())
        assert "~" not in str(platform.user_cache_dir())

    def test_windows_music_falls_back_to_existing_documents(self, monkeypatch, fake_home, set_platform, tmp_path):
        set_platform("win32")
        profile = tmp_path / "profile"
        documents = profile / "Documents"
        documents.mkdir(parents=True)
        monkeypatch.setenv("USERPROFILE", str(profile))

        assert platform.music_dir() == documents

    def test_windows_music_falls_back_to_profile_without_documents(self, monkeypatch, fake_home, set_platform, tmp_path):
        set_platform("win32")
        profile = tmp_path / "profile"
        profile.mkdir()
        monkeypatch.setenv("USERPROFILE", str(profile))

        assert platform.music_dir() == profile

    def test_windows_music_prefers_existing_music_directory(self, monkeypatch, fake_home, set_platform, tmp_path):
        set_platform("win32")
        profile = tmp_path / "profile"
        music = profile / "Music"
        music.mkdir(parents=True)
        monkeypatch.setenv("USERPROFILE", str(profile))

        assert platform.music_dir() == music

    def test_macos_and_linux_music_fall_back_to_documents(self, fake_home, set_platform):
        documents = fake_home / "Documents"
        documents.mkdir()

        for value in ("darwin", "linux"):
            set_platform(value)
            assert platform.music_dir() == documents

    def test_linux_music_uses_existing_xdg_directory_after_home_music(self, monkeypatch, fake_home, set_platform, tmp_path):
        set_platform("linux")
        xdg_music = tmp_path / "xdg-music"
        xdg_music.mkdir()
        monkeypatch.setenv("XDG_MUSIC_DIR", str(xdg_music))

        assert platform.music_dir() == xdg_music


class TestExecutables:
    @pytest.mark.parametrize(("value", "expected"), [("win32", "ffmpeg.exe"), ("darwin", "ffmpeg"), ("linux", "ffmpeg")])
    def test_executable_name_only_adds_exe_on_windows(self, set_platform, value, expected):
        set_platform(value)

        assert platform.executable_name("ffmpeg") == expected

    def test_find_binary_prefers_bundled_file_over_path(self, monkeypatch, set_platform, tmp_path):
        set_platform("linux")
        bundled = tmp_path / "bundled"
        bundled.mkdir()
        bundled_binary = bundled / "ffmpeg"
        bundled_binary.touch()
        monkeypatch.setattr(platform, "bundled_binary_dirs", lambda: [bundled])
        monkeypatch.setattr(platform.shutil, "which", lambda name: "/system/ffmpeg")

        assert platform.find_binary("ffmpeg") == bundled_binary
        assert platform.has_binary("ffmpeg") is True

    def test_find_binary_returns_none_when_no_candidate_exists(self, monkeypatch, set_platform):
        set_platform("linux")
        monkeypatch.setattr(platform, "bundled_binary_dirs", lambda: [])
        monkeypatch.setattr(platform, "system_binary_dirs", lambda: [])
        monkeypatch.setattr(platform.shutil, "which", lambda name: None)

        assert platform.find_binary("missing-tool") is None
        assert platform.has_binary("missing-tool") is False

    def test_find_binary_checks_executable_name_on_windows_path(self, monkeypatch, set_platform):
        set_platform("win32")
        seen = []
        monkeypatch.setattr(platform, "bundled_binary_dirs", lambda: [])
        monkeypatch.setattr(platform, "system_binary_dirs", lambda: [])

        def which(name):
            seen.append(name)
            return "C:/tools/ffmpeg.exe" if name == "ffmpeg.exe" else None

        monkeypatch.setattr(platform.shutil, "which", which)

        assert platform.find_binary("ffmpeg") == Path("C:/tools/ffmpeg.exe")
        assert seen == ["ffmpeg", "ffmpeg.exe"]


    def test_ensure_binaries_on_path_prepends_existing_dirs_once(self, monkeypatch, set_platform, tmp_path):
        set_platform("linux")
        extra = tmp_path / "extra"
        bundled = tmp_path / "bundled"
        system = tmp_path / "system"
        for directory in (extra, bundled, system):
            directory.mkdir()
        monkeypatch.setattr(platform, "bundled_binary_dirs", lambda: [bundled])
        monkeypatch.setattr(platform, "system_binary_dirs", lambda: [system])
        monkeypatch.setenv("PATH", f"{system}{os.pathsep}/original")

        expected = [extra, bundled, system]
        assert platform.ensure_binaries_on_path([extra]) == expected
        assert os.environ["PATH"] == os.pathsep.join([str(extra), str(bundled), str(system), "/original"])
        assert platform.ensure_binaries_on_path([extra]) == expected
        assert os.environ["PATH"] == os.pathsep.join([str(extra), str(bundled), str(system), "/original"])


class TestBundledBinaryDirs:
    """WHY: fetch_vendor.py installs into `packaging/vendor/<platform>/bin`;
    source-mode separation silently died when discovery probed only the flat
    `packaging/vendor/bin` (the live bug this pins)."""

    @staticmethod
    def _fake_repo(monkeypatch, tmp_path):
        monkeypatch.setattr(platform, "__file__", str(tmp_path / "utils" / "platform_utils.py"))
        monkeypatch.setattr(platform, "is_frozen", lambda: False)
        vendor = tmp_path / "packaging" / "vendor"
        for sub in ("bin", "linux/bin", "windows/bin"):
            (vendor / sub).mkdir(parents=True)
        return vendor

    @pytest.mark.parametrize(("value", "own", "foreign"), [("linux", "linux/bin", "windows/bin"), ("win32", "windows/bin", "linux/bin")])
    def test_probes_flat_and_own_platform_dir_only(self, monkeypatch, set_platform, tmp_path, value, own, foreign):
        set_platform(value)
        vendor = self._fake_repo(monkeypatch, tmp_path)

        dirs = platform.bundled_binary_dirs()

        assert vendor / "bin" in dirs
        assert vendor / own in dirs
        assert vendor / foreign not in dirs

    def test_macos_source_checkout_probes_only_the_flat_dir(self, monkeypatch, set_platform, tmp_path):
        set_platform("darwin")
        vendor = self._fake_repo(monkeypatch, tmp_path)

        assert platform.bundled_binary_dirs() == [vendor / "bin"]

    def test_nonexistent_vendor_dirs_are_filtered(self, monkeypatch, set_platform, tmp_path):
        set_platform("linux")
        monkeypatch.setattr(platform, "__file__", str(tmp_path / "utils" / "platform_utils.py"))
        monkeypatch.setattr(platform, "is_frozen", lambda: False)

        assert platform.bundled_binary_dirs() == []


@pytest.fixture
def worker_precheck_logger():
    class _Logger:
        def __init__(self):
            self.errors = []

        def error(self, message):
            self.errors.append(message)

    return _Logger()


class TestWorkerFFmpegPrecheck:
    """WHY: audio-separator's bare `ffmpeg -version` probe produced three
    opaque FileNotFoundError retries; the worker must fail once with the
    fetch_vendor remediation."""

    def test_passes_silently_when_ffmpeg_is_resolvable(self, monkeypatch, worker_precheck_logger):
        from core import separation_subprocess as worker
        monkeypatch.setattr(worker.shutil, "which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)

        worker._require_ffmpeg(worker_precheck_logger)

        assert worker_precheck_logger.errors == []

    def test_missing_ffmpeg_raises_with_fetch_vendor_remediation(self, monkeypatch, worker_precheck_logger):
        from core import separation_subprocess as worker
        monkeypatch.setattr(worker.shutil, "which", lambda name: None)

        with pytest.raises(FileNotFoundError, match="fetch_vendor"):
            worker._require_ffmpeg(worker_precheck_logger)

        assert worker_precheck_logger.errors and "FFmpeg" in worker_precheck_logger.errors[0]

    def test_windows_probes_the_exe_name(self, monkeypatch, worker_precheck_logger):
        from core import separation_subprocess as worker
        monkeypatch.setattr(sys, "platform", "win32")
        seen = []

        def which(name):
            seen.append(name)
            return "C:/tools/ffmpeg.exe" if name == "ffmpeg.exe" else None

        monkeypatch.setattr(worker.shutil, "which", which)

        worker._require_ffmpeg(worker_precheck_logger)

        assert seen == ["ffmpeg.exe"]
        assert worker_precheck_logger.errors == []


class TestRuntimeFlags:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [("win32", {"creationflags": platform.CREATE_NO_WINDOW}), ("darwin", {"start_new_session": True}), ("linux", {"start_new_session": True})],
    )
    def test_popen_kwargs_match_platform_process_semantics(self, set_platform, value, expected):
        set_platform(value)

        assert platform.popen_kwargs() == expected

    def test_bundle_dir_returns_none_without_meipass(self, monkeypatch):
        monkeypatch.delattr(platform.sys, "_MEIPASS", raising=False)

        assert platform.bundle_dir() is None

    def test_bundle_dir_returns_meipass_path(self, monkeypatch, tmp_path):
        bundle = tmp_path / "bundle"
        monkeypatch.setattr(platform.sys, "_MEIPASS", str(bundle), raising=False)

        assert platform.bundle_dir() == bundle

    @pytest.mark.parametrize("value", ["darwin", "linux"])
    def test_torch_library_dirs_are_empty_outside_frozen_windows(self, monkeypatch, set_platform, value):
        set_platform(value)
        monkeypatch.setattr(platform, "is_frozen", lambda: True)

        assert platform.torch_library_dirs() == []

    def test_torch_library_dirs_are_empty_for_unfrozen_windows(self, monkeypatch, set_platform):
        set_platform("win32")
        monkeypatch.setattr(platform, "is_frozen", lambda: False)

        assert platform.torch_library_dirs() == []

    @pytest.mark.parametrize("value", ["darwin", "linux"])
    def test_configure_native_library_dirs_is_noop_outside_windows(self, monkeypatch, set_platform, tmp_path, value):
        set_platform(value)
        directory = tmp_path / "native"
        directory.mkdir()
        calls = []
        monkeypatch.setattr(platform.os, "add_dll_directory", lambda path: calls.append(path), raising=False)

        assert platform.configure_native_library_dirs([directory]) == []
        assert calls == []
