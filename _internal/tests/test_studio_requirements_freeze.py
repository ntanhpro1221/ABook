"""`freeze_studio_requirements.py` đóng băng runtime dev thành danh sách cài của Studio - phải đúng ghim của pyproject.

11-10: runtime/.venv đã trôi khỏi ghim (huggingface-hub 1.29 dù pyproject ghim 1.33, transformers 5.16.1 thay vì
5.18.0...). Đóng băng lại lúc ấy là bộ cài Studio lùi bản mà không ai hay. Và PySide6 6.12 tách WebEngine/Pdf thành
wheel riêng: không có tên trong EXCLUDED thì Qt lọt vào bộ cài Studio (vỏ Tauri, không chạy Qt).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import freeze_studio_requirements as freeze

PYPROJECT = """
dependencies = [
  "PySide6==6.12.0",
  "torch==2.11.0",
  "huggingface-hub==1.33.0",
  "utmosv2 @ git+https://github.com/sarulab-speech/UTMOSv2.git@cc2700db57bb83ee13dc31ebe1b868c254e15d09",
]
[project.optional-dependencies]
dev = ["pytest==9.1.1", "ruff==0.16.10"]
"""


def test_every_qt_wheel_of_pyside6_6_12_stays_out_of_the_studio_list():
    frozen = """PySide6==6.12.0
PySide6_Addons==6.12.0
PySide6_Essentials==6.12.0
PySide6_WebEngine==6.12.0.140
PySide6_Pdf==6.12.0.140
shiboken6==6.12.0
torch==2.11.0+cu128
"""
    assert freeze.kept_lines(frozen) == ["torch==2.11.0+cu128"]


def test_a_runtime_that_drifted_from_the_pins_is_named():
    kept = ["huggingface-hub==1.29.0", "torch==2.11.0+cu128", "utmosv2 @ git+https://github.com/x/y.git@abc"]
    assert freeze.drift_from_pins(kept, PYPROJECT) == ["huggingface-hub: runtime 1.29.0, pyproject 1.33.0"]


def test_the_cuda_build_tag_and_excluded_pins_are_not_drift():
    kept = ["huggingface_hub==1.33.0", "torch==2.11.0+cu128"]
    assert freeze.drift_from_pins(kept, PYPROJECT) == []


def test_a_pinned_package_missing_from_the_runtime_is_drift():
    assert freeze.drift_from_pins(["torch==2.11.0+cu128"], PYPROJECT) == ["huggingface-hub: runtime không có, pyproject 1.33.0"]


def test_a_dev_only_pin_is_not_drift_when_only_the_app_closure_is_frozen():
    pyproject = PYPROJECT + 'dev2 = ["cryptography==50.0.0"]\n'
    kept = ["huggingface-hub==1.33.0", "torch==2.11.0+cu128"]
    assert freeze.drift_from_pins(kept, pyproject, {"huggingface-hub", "torch"}) == []
    assert freeze.drift_from_pins(kept, pyproject) == ["cryptography: runtime không có, pyproject 50.0.0"]


def test_the_runtime_must_match_the_lock_including_the_cuda_tag_and_git_commits():
    locked = {"torch": "2.11.0+cu128", "utmosv2": "cc27", "timm": "1.0.30"}
    kept = ["torch==2.11.0", "utmosv2 @ git+https://github.com/x/UTMOSv2.git@cc27", "timm==1.0.30"]
    assert freeze.drift_from_lock(kept, locked) == ["torch: runtime 2.11.0, uv.lock 2.11.0+cu128"]
