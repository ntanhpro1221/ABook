"""A removed Visual Studio installation must not poison later CMake configures."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "desktop_qt/tools/drop_stale_cmake_cache.py"
spec = importlib.util.spec_from_file_location("drop_stale_cmake_cache", HELPER)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def _cache(build, entries):
    build.mkdir()
    cache = build / "CMakeCache.txt"
    cache.write_text("// CMake cache\n" + "\n".join(f"{k}:FILEPATH={v}" for k, v in entries.items()), encoding="utf-8")
    files = build / "CMakeFiles"
    files.mkdir()
    (files / "compiler-check.txt").write_text("cached compiler", encoding="utf-8")
    (build / "keep.ninja").write_text("keep build products", encoding="utf-8")
    return cache, files


@pytest.mark.parametrize("key", ["CMAKE_CXX_COMPILER", "CMAKE_C_COMPILER", "CMAKE_LINKER"])
def test_missing_cached_tool_clears_configuration_only(tmp_path, key, capsys):
    build = tmp_path / "build (x86)"
    cache, files = _cache(build, {key: tmp_path / "removed (x86)" / "tool.exe"})
    assert helper.drop_stale_cmake_cache(build)
    assert not cache.exists()
    assert not files.exists()
    assert (build / "keep.ninja").read_text() == "keep build products"
    assert key in capsys.readouterr().out
    assert not helper.drop_stale_cmake_cache(build)


def test_existing_tools_keep_cache_byte_for_byte(tmp_path, capsys):
    tool = tmp_path / "tool (x86).exe"
    tool.touch()
    cache, files = _cache(tmp_path / "build", {key: tool for key in
                          ("CMAKE_CXX_COMPILER", "CMAKE_C_COMPILER", "CMAKE_LINKER")})
    before = cache.read_bytes()
    assert not helper.drop_stale_cmake_cache(cache.parent)
    assert cache.read_bytes() == before
    assert (files / "compiler-check.txt").is_file()
    assert capsys.readouterr().out == ""


def test_missing_linker_invalidates_cache_with_existing_compiler(tmp_path):
    tool = tmp_path / "cl.exe"
    tool.touch()
    cache, files = _cache(tmp_path / "build", {"CMAKE_CXX_COMPILER": tool,
                                             "CMAKE_LINKER": tmp_path / "removed-link.exe"})
    assert helper.drop_stale_cmake_cache(cache.parent)
    assert not cache.exists() and not files.exists()


def test_no_cache_keeps_cmakefiles(tmp_path):
    files = tmp_path / "CMakeFiles"
    files.mkdir()
    assert not helper.drop_stale_cmake_cache(tmp_path)
    assert files.is_dir()


def test_unset_optional_tool_is_not_a_missing_path(tmp_path):
    cache, files = _cache(tmp_path / "build", {"CMAKE_LINKER": ""})
    assert not helper.drop_stale_cmake_cache(cache.parent)
    assert cache.exists() and files.exists()


def test_outside_target_is_rejected_before_any_deletion(tmp_path, monkeypatch):
    cache, files = _cache(tmp_path / "build", {"CMAKE_C_COMPILER": tmp_path / "removed.exe"})
    resolve = Path.resolve

    def redirected(path, *args, **kwargs):
        return tmp_path / "outside" if path == files else resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", redirected)
    with pytest.raises(ValueError, match="outside"):
        helper.drop_stale_cmake_cache(cache.parent)
    assert cache.exists() and (files / "compiler-check.txt").exists()


def test_helper_cli_handles_spaces_and_parentheses(tmp_path):
    cache, files = _cache(tmp_path / "build (x86)", {"CMAKE_CXX_COMPILER": tmp_path / "removed.exe"})
    result = subprocess.run([sys.executable, "-X", "utf8", str(HELPER), str(cache.parent)],
                            capture_output=True, text=True, check=False,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert result.returncode == 0, result.stderr
    assert "cached tool missing" in result.stdout
    assert not cache.exists() and not files.exists()
