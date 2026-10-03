"""Đo độ to (BS.1770, LUFS tích hợp) của từng giọng VieNeu / Supertonic cho abook/readaloud/loudness.py (đích -20 LUFS, chỉnh lúc phát).

Đọc 30 câu cố định bằng mỗi giọng qua đúng đường của "Nghe ngay" (VieneuProvider / SupertonicProvider), nối lại, đo bằng
audio_io.integrated_loudness_lufs (pyloudnorm, venv dev). Model VieNeu lấy từ thư mục mô-đun đã tải (--module <dữ liệu app>/vieneu) hay bộ đệm
Hugging Face của máy dev (mặc định); giọng Supertonic: --supertonic <thư mục model> (<dữ liệu app>/supertonic/model hay ~/.cache/supertonic3).

    runtime/.venv/Scripts/python.exe scripts/measure_vieneu_loudness.py [--module DIR] [--tier turbo|nano] [--out file.json]
    runtime/.venv/Scripts/python.exe scripts/measure_vieneu_loudness.py --supertonic DIR [--out file.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SENTENCES = [
    "Trời hôm nay đẹp quá.",
    "Cô gái đứng bên cửa sổ, lặng lẽ nhìn mưa rơi.",
    "Chiếc thuyền nhỏ trôi chậm giữa dòng sông, mang theo những mùa hè đã xa.",
    "Anh ấy mở cuốn sổ cũ và đọc lại từng dòng chữ mẹ viết.",
    "Khi ánh đèn vụt tắt, cả ngôi nhà chìm vào bóng tối.",
    "Ngoài sân, con chó già nằm ngủ dưới gốc cây bàng.",
    "Sáng mai chúng ta sẽ lên đường từ lúc sáu giờ.",
    "Bà kể rằng ngày xưa làng này chỉ có ba mươi nóc nhà.",
    "Tiếng còi tàu vang lên từ phía xa, rồi tắt dần trong sương.",
    "Cậu bé chạy một mạch về nhà, tay vẫn nắm chặt con diều.",
    "Thầy giáo gõ nhẹ lên bàn và cả lớp im phăng phắc.",
    "Mùi cà phê mới pha lan khắp căn bếp nhỏ.",
    "Đêm ấy, gió thổi rất mạnh, cửa sổ cứ đập liên hồi.",
    "Cô mỉm cười, nhưng đôi mắt vẫn còn đỏ hoe.",
    "Con đường đất đỏ uốn quanh những đồi chè xanh mướt.",
    "Chợ phiên họp vào ngày rằm, người đến từ khắp các bản.",
    "Ông cụ chậm rãi rót trà, rồi mời khách một chén.",
    "Ánh trăng rọi qua kẽ lá, in bóng loang lổ trên mặt đất.",
    "Hai người bạn ngồi bên bờ hồ, chẳng ai nói câu nào.",
    "Bức thư đến muộn đúng một tuần so với dự tính.",
    "Trên chuyến xe cuối ngày, mọi người đều mệt mỏi.",
    "Chị lấy khăn lau vội những giọt nước trên trán.",
    "Mưa tạnh, cầu vồng hiện lên phía sau dãy núi.",
    "Đứa em út lúc nào cũng hỏi những câu thật lạ.",
    "Căn phòng trên gác mái chất đầy sách và tranh cũ.",
    "Anh nhìn đồng hồ, chỉ còn mười lăm phút nữa.",
    "Hoa sữa nở rộ, cả con phố thơm nồng mỗi tối.",
    "Người lái đò cất tiếng hát giữa dòng nước lặng.",
    "Cuối cùng thì cánh cửa cũng mở ra, chậm rãi và nặng nề.",
    "Mọi chuyện rồi sẽ ổn thôi, em đừng lo.",
]


def _cache_install():
    from huggingface_hub import snapshot_download

    from abook.readaloud.vieneu import Installed
    from abook.webui import vieneu_module as vm

    def snap(url: str, patterns: list[str]) -> Path:
        repo, revision = url.split("/resolve/")[0].removeprefix("https://huggingface.co/"), url.split("/resolve/")[1].split("/")[0]
        for cache in (os.environ.get("HF_HUB_CACHE"), str(Path.home() / ".cache" / "huggingface" / "hub")):  # của runtime, của người dùng
            try:
                return Path(snapshot_download(repo, revision=revision, allow_patterns=patterns, local_files_only=True, cache_dir=cache))
            except Exception:  # noqa: BLE001 - không có ở chỗ này: thử chỗ kế
                continue
        raise SystemExit(f"{repo}@{revision} chưa có trong bộ đệm Hugging Face")

    turbo = snap(vm._TURBO, ["onnx_int8/*"]) / "onnx_int8"
    codec = snap(vm._CODEC, ["moss_audio_tokenizer_decode_*"])
    nano = snap(vm._NANO, ["*"])
    import vieneu  # chỉ để lấy hai file giọng có sẵn

    return Installed(Path(vieneu.__file__).parent / "assets", (turbo, codec), nano, False)


def _measure_supertonic(folder: Path, out: str | None) -> int:
    import numpy as np

    from abook import audio_io
    from abook.readaloud.supertonic import NAMES, PREFIX, Installed, SupertonicProvider

    found = Installed(folder)
    provider = SupertonicProvider(lambda: found)
    results: dict[str, float] = {}
    for name in NAMES:
        began = time.perf_counter()
        pieces = [provider._speak(found, name, text) for text in SENTENCES]
        lufs = audio_io.integrated_loudness_lufs(np.concatenate([piece[0] for piece in pieces]), pieces[0][1])
        results[f"{PREFIX}:{name}"] = round(float(lufs), 1)
        print(f"{PREFIX}:{name}	{lufs:.1f} LUFS	{time.perf_counter() - began:.0f}s", flush=True)
    if out:
        Path(out).write_bytes(json.dumps(results, ensure_ascii=False, indent=1).encode("utf-8"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", help="thư mục mô-đun đã tải (<dữ liệu app>/vieneu)")
    parser.add_argument("--tier", choices=["turbo", "nano"])
    parser.add_argument("--supertonic", help="đo giọng Supertonic ở thư mục model này thay vì giọng VieNeu")
    parser.add_argument("--out")
    args = parser.parse_args()

    from abook import audio_io
    from abook.readaloud.vieneu import VieneuProvider
    from abook.webui import vieneu_module as vm

    if args.supertonic:
        return _measure_supertonic(Path(args.supertonic), args.out)
    if args.module:
        vm.configure(Path(args.module))
        found = vm.installed()
    else:
        found = _cache_install()
    provider = VieneuProvider(lambda: found)
    import numpy as np

    results: dict[str, float] = {}
    for tier in ("turbo", "nano"):
        if args.tier and tier != args.tier or getattr(found, tier) is None:
            continue
        for name, preset in provider.presets(tier, found).items():
            began = time.perf_counter()
            pieces = [provider._speak(tier, name, found, preset, text) for text in SENTENCES]
            rate = pieces[0][1]
            lufs = audio_io.integrated_loudness_lufs(np.concatenate([piece[0] for piece in pieces]), rate)
            results[f"vieneu:{tier}/{name}"] = round(float(lufs), 1)
            print(f"vieneu:{tier}/{name}\t{lufs:.1f} LUFS\t{time.perf_counter() - began:.0f}s", flush=True)
    if args.out:
        Path(args.out).write_bytes(json.dumps(results, ensure_ascii=False, indent=1).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
