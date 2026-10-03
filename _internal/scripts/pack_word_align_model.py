"""Dựng gói model căn từng chữ (wav2vec2 CTC tiếng Việt, ONNX int8) để đăng và ghim.

    runtime/.venv/Scripts/python.exe scripts/pack_word_align_model.py --onnx <file int8.onnx> --hf <thư mục model gốc> [--out thư_mục]

Model gốc: `dragonSwing/wav2vec2-base-vietnamese` (Apache-2.0). `--onnx` là bản xuất int8 của nó (LLM_Train/word_align/export_onnx.py
dragon -> onnx/dragon_int8.onnx, 122 MB, đã đo: không kém bản fp32); `--hf` là thư mục tải của model gốc, lấy `vocab.json` và
`preprocessor_config.json` y nguyên byte. Chép ba file vào `--out` đúng tên studio_setup.WORD_ALIGN_FILES, kiểm đầu vào/ra của ONNX
và từ điển, rồi in băm + cỡ để so với (hay dán vào) studio_setup.py. Không đăng gì: chủ sách đăng lên Hugging Face
(NGDtuanh/abook-analyzer, thư mục word-align/) rồi đưa mã commit để thay PIN_REVISION.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from abook.webui import studio_setup  # noqa: E402


def pack(onnx: Path, hf: Path, out: Path) -> list[Path]:
    sources = {studio_setup.WORD_ALIGN_MODEL: onnx, "vocab.json": hf / "vocab.json",
               "preprocessor_config.json": hf / "preprocessor_config.json"}
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for item in studio_setup.WORD_ALIGN_FILES:
        source = sources[item.name]
        if not source.is_file():
            raise SystemExit(f"Thiếu {source}")
        target = out / item.name
        shutil.copyfile(source, target)
        written.append(target)
    vocab = json.loads((out / "vocab.json").read_text(encoding="utf-8"))
    config = json.loads((out / "preprocessor_config.json").read_text(encoding="utf-8"))
    if vocab.get("<pad>") != 0 or "|" not in vocab or not config.get("do_normalize") or config.get("sampling_rate") != 16000:
        raise SystemExit("Từ điển / cấu hình không phải loại word_timing đã chép cứng (blank = <pad> = 0, dấu cách |, chuẩn hoá, 16 kHz)")
    import onnxruntime

    session = onnxruntime.InferenceSession(str(out / studio_setup.WORD_ALIGN_MODEL), providers=["CPUExecutionProvider"])
    if [i.name for i in session.get_inputs()] != ["audio"] or [o.name for o in session.get_outputs()] != ["logits"]:
        raise SystemExit("ONNX không có đầu vào `audio` / đầu ra `logits`")
    if session.get_outputs()[0].shape[-1] != len(vocab):
        raise SystemExit("Số lớp đầu ra của ONNX không khớp từ điển")
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--onnx", type=Path, required=True)
    parser.add_argument("--hf", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path.cwd() / "word-align")
    args = parser.parse_args(argv)
    ok = True
    for path in pack(args.onnx, args.hf, args.out):
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        item = next(item for item in studio_setup.WORD_ALIGN_FILES if item.name == path.name)
        match = digest == item.sha256 and len(data) == item.size
        ok = ok and match
        print(f"{path.name}  {len(data):,} byte  sha256 {digest}  {'khớp studio_setup' if match else 'KHÁC studio_setup - cập nhật WORD_ALIGN_FILES'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
