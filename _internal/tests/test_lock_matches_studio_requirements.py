"""`uv.lock` và `shell/python/studio-requirements.txt` là một môi trường, phải khớp từng gói.

11-10: hai nguồn lệch nhau. Lock lấy torch/torchvision/torchaudio bản PyPI (CPU trên Windows) còn bộ cài Studio
lấy +cu128; gradio 6.20 vs 6.16, setuptools 81 vs 78.1...; và Studio cài thêm 64 gói ngoài bao đóng phụ thuộc
của app (voxcpm, funasr, modelscope, datasets... - đồ thí nghiệm cài tay vào runtime, 258 MiB) mà lock không có.
Gói nào Studio cài thì lock khoá đúng bản ấy, và ngược lại (trừ Qt + công cụ dev).
"""

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

INTERNAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERNAL / "scripts"))

import freeze_studio_requirements as freeze

LOCK = tomllib.loads((INTERNAL / "uv.lock").read_text(encoding="utf-8"))
STUDIO = (INTERNAL / "shell" / "python" / "studio-requirements.txt").read_text(encoding="utf-8")


def _studio() -> dict[str, str]:
    """Tên -> bản (hay commit, với gói git) của danh sách Studio."""
    found = {}
    for line in STUDIO.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-")):
            continue
        if " @ git+" in line:
            name, url = line.split(" @ ", 1)
            found[freeze.normalize(name)] = url.rsplit("@", 1)[1]
        else:
            name, version = line.split("==", 1)
            found[freeze.normalize(name)] = version
    return found


def test_the_lock_and_the_studio_list_hold_the_same_packages():
    locked = freeze.lock_closure(LOCK)
    studio = _studio()
    assert sorted(set(studio) - set(locked)) == [], "Studio cài mà lock không khoá"
    assert sorted(set(locked) - set(studio)) == [], "lock khoá mà Studio không cài"


def test_every_package_has_the_same_version_in_both():
    locked = freeze.lock_closure(LOCK)
    studio = _studio()
    assert {n: (locked[n], v) for n, v in studio.items() if n in locked and locked[n] != v} == {}


def test_torch_is_locked_as_the_cuda_build_from_the_cu128_index():
    torch = {p["name"]: p for p in LOCK["package"] if p["name"] in {"torch", "torchvision", "torchaudio"}}
    assert sorted(torch) == ["torch", "torchaudio", "torchvision"]
    for package in torch.values():
        assert package["version"].endswith("+cu128"), package["version"]
        assert package["source"]["registry"] == freeze.TORCH_INDEX


def test_the_lock_closure_follows_dependencies_not_the_whole_lock():
    lock = {
        "package": [
            {"name": "abook", "source": {"editable": "."},
             "dependencies": [{"name": "a"}], "optional-dependencies": {"dev": [{"name": "pytest"}]}},
            {"name": "a", "version": "1.0", "dependencies": [{"name": "b"}, {"name": "pyside6"}]},
            {"name": "b", "version": "2.0+cu128"},
            {"name": "pyside6", "version": "6.11.2"},
            {"name": "pytest", "version": "9.1.1"},
        ]
    }
    assert freeze.lock_closure(lock) == {"a": "1.0", "b": "2.0+cu128"}


def test_the_lock_is_current_with_pyproject():
    """Lock cũ (11-10 còn ghi abook 0.4.25) thì so khớp với nó chẳng chứng minh gì."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("không có uv trên máy này")
    checked = subprocess.run([uv, "lock", "--check", "--offline"], cwd=INTERNAL, capture_output=True, text=True, check=False)
    assert checked.returncode == 0, checked.stderr[-2000:]
