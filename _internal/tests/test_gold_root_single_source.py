"""Mọi script đo/dựng dữ liệu đọc thư mục đáp án qua scripts/model_eval/gold_root.py.

Bản `gold/` trong repo từng đi sau nguồn chuẩn riêng mà các builder vẫn đọc nó; một chỗ cấu hình duy nhất
(ABOOK_GOLD_ROOT) để chấm thẳng từ nguồn chuẩn, và test này chặn việc ghép lại đường `.../gold` riêng.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

INTERNAL = Path(__file__).resolve().parents[1]
MODEL_EVAL = INTERNAL / "scripts" / "model_eval"
OWN_ROOT = re.compile(r"""^\s*\w*GOLD\w*\s*=\s*[^#\n]*/\s*["']gold["']\s*(?:#.*)?$""", re.MULTILINE)


def test_no_script_builds_its_own_gold_root():
    stray = []
    for path in MODEL_EVAL.rglob("*.py"):
        if path.name == "gold_root.py" or "gold" in path.relative_to(MODEL_EVAL).parts[:1]:
            continue
        for match in OWN_ROOT.finditer(path.read_text(encoding="utf-8")):
            stray.append(f"{path.relative_to(INTERNAL).as_posix()}: {match.group(0).strip()}")
    assert not stray, "Dùng gold_root.gold_root():\n" + "\n".join(stray)


def test_environment_overrides_the_gold_root(tmp_path):
    code = "import sys; sys.path.insert(0, sys.argv[1]); import score_models; print(score_models.GOLD_ROOT)"
    env = {**os.environ, "ABOOK_GOLD_ROOT": str(tmp_path)}
    out = subprocess.run([sys.executable, "-c", code, str(MODEL_EVAL)], env=env, capture_output=True, text=True, check=True)
    assert Path(out.stdout.strip()) == tmp_path
