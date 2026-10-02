"""
Behavioural tests for `utils.path_utils` output-path resolution.

WHY this file exists: the settings layer hands `resolve_output_path` a `Path`
built from the string stored in `user_settings.json` (e.g.
`"~/Music/StemSeparator/separated"`). Only the *string* branch of the resolver
expanded `~`, so `Path.resolve()` anchored the literal `~` component to the
current working directory and the application created a `~` folder inside the
installation on every platform. These tests pin the expansion for both input
types, in every branch that can be reached.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.path_utils import ensure_directory_exists, resolve_output_path  # noqa: E402


@pytest.fixture
def home(monkeypatch, tmp_path):
    """Point `~` at a scratch directory so tests never touch the real home."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))  # Windows spelling
    monkeypatch.chdir(tmp_path)
    return fake_home


@pytest.fixture
def default_dir(tmp_path):
    return tmp_path / "default-output"


class TestResolveOutputPath:
    @pytest.mark.parametrize("value", [Path("~/Music/out"), "~/Music/out"])
    def test_tilde_expands_for_both_input_types(self, home, default_dir, value):
        resolved = resolve_output_path(value, default_dir)
        assert resolved == home / "Music" / "out"
        assert resolved.is_dir(), "the resolver must create the directory"

    def test_no_literal_tilde_component_survives(self, home, default_dir):
        resolved = resolve_output_path(Path("~/deep/nested/out"), default_dir)
        assert "~" not in resolved.parts

    def test_none_uses_default(self, home, default_dir):
        resolved = resolve_output_path(None, default_dir)
        assert resolved == default_dir.resolve()
        assert resolved.is_dir()

    def test_empty_string_uses_default(self, home, default_dir):
        assert resolve_output_path("   ", default_dir) == default_dir.resolve()

    def test_relative_resolves_against_cwd(self, home, default_dir, tmp_path):
        resolved = resolve_output_path(Path("relative/out"), default_dir)
        assert resolved == tmp_path / "relative" / "out"
        assert resolved.is_dir()

    def test_absolute_is_returned_unchanged(self, home, default_dir, tmp_path):
        target = tmp_path / "already" / "absolute"
        resolved = resolve_output_path(target, default_dir)
        assert resolved == target
        assert resolved.is_dir()

    def test_unknown_user_is_not_mangled_into_a_crash(self, home, default_dir):
        """`~nosuchuser` cannot be expanded; it must stay a usable relative name."""
        resolved = resolve_output_path(Path("~nosuchuserabc/x"), default_dir)
        assert resolved.is_dir()
        assert resolved.parent.name.startswith("~nosuchuserabc")


class TestEnsureDirectoryExists:
    def test_tilde_path_expands(self, home, tmp_path):
        resolved = ensure_directory_exists(Path("~/created"))
        assert resolved == home / "created"
        assert resolved.is_dir()

    def test_relative_resolves_against_cwd(self, home, tmp_path):
        resolved = ensure_directory_exists(Path("rel/dir"))
        assert resolved == tmp_path / "rel" / "dir"
        assert resolved.is_dir()

    def test_existing_directory_is_idempotent(self, home, tmp_path):
        first = ensure_directory_exists(tmp_path / "twice")
        second = ensure_directory_exists(tmp_path / "twice")
        assert first == second == tmp_path / "twice"

    def test_nested_directories_are_created(self, home, tmp_path):
        resolved = ensure_directory_exists(tmp_path / "a" / "b" / "c")
        assert resolved.is_dir()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
