"""Giọng Supertonic 3 cho "Nghe ngay": giọng đọc ngay trên máy, không cần mạng, có khi người dùng đã tải mô-đun "Giọng Supertonic"
(webui/supertonic_module.py). Chỉ onnxruntime (CPU) + numpy, như vieneu_engine.py; máy chưa tải thì danh sách giọng rỗng.

Mã suy luận viết lại từ mã mẫu chính thức của hãng (gói pip `supertonic` 1.3.1, https://github.com/supertone-inc/supertonic, giấy phép MIT,
Copyright (c) 2025 Supertone Inc.): bộ xử lý chữ (`UnicodeProcessor`), chuỗi dự đoán độ dài -> mã hoá chữ -> khử nhiễu tiềm ẩn từng bước ->
vocoder (`Supertonic.__call__`), đọc file phong cách giọng (`loader.load_voice_style_from_json_file`). Khác bản mẫu: nhiễu khởi đầu bốc từ một
`RandomState` theo hạt giống (cùng đoạn cùng giọng ra cùng audio, như VieNeu), ký tự model không biết thì bỏ chứ không báo lỗi (sách có đủ
thứ ký tự), và đầu ra cắt im lặng hai mép. Trọng số: Supertone/supertonic-3, OpenRAIL-M (xem THIRD_PARTY.md), tải khi người dùng bấm.

Một clip = MỘT đoạn của chương, chia khúc / ghép khoảng nghỉ / mốc từng chữ y như VieNeu (`vieneu.units`, `vieneu_engine.join`,
`vieneu.timed_synthesis`) - model không cho mốc chữ nên mốc do bộ căn chữ (nếu máy có) hay chia theo âm tiết. Chữ đem đọc đi qua bộ chuẩn
hoá của sea-g2p (số, ngày, giờ thành chữ: Supertonic đọc số kém nhất, CER nhóm số ~9,8%) khi máy có sea-g2p; không có thì đọc nguyên chữ.
"""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from unicodedata import normalize as unicode_normalize

from .model import Synthesis, Voice, VoiceError
from .vieneu import Unit, reading_tag, seed_of, timed_synthesis, units

PREFIX = "supertonic"
TIER = "supertonic"  # khoá của kết quả tự đo (cùng hình với các tầng VieNeu)
SAMPLE_RATE = 44_100  # onnx/tts.json (ae.sample_rate); SupertonicEngine đọc lại từ file khi nạp
LANGUAGE = "vi"
STEPS = 8  # số bước khử nhiễu (bản đo: 8; mặc định của hãng 5)
SPEED = 1.54  # hãng cho 0,7 - 2,0 (mặc định 1,05); 1,54 khớp tốc độ nói của VieNeu - tốc độ nghe của người dùng vẫn do trình phát chỉnh
# Câu ngắn ở 1,54 bị nuốt gần hết ("Về rồi?", "Sao cô biết?" còn 0-0,2 s có tiếng; đo trên 40 câu thoại thật, luồng Model 03-10), ở 1,05 thì đủ:
# tốc độ tăng dần theo số tiếng của khúc - <= SHORT_SYLLABLES tiếng đọc ở SHORT_SPEED, >= LONG_SYLLABLES tiếng đọc ở SPEED.
SHORT_SPEED = 1.05
SHORT_SYLLABLES = 3
LONG_SYLLABLES = 12


def speed_for(text: str) -> float:
    """Tốc độ cho một khúc chữ (đã chuẩn hoá): đếm tiếng theo khoảng trắng."""
    syllables = len(re.findall(r"\w+", text))
    share = min(1.0, max(0.0, (syllables - SHORT_SYLLABLES) / (LONG_SYLLABLES - SHORT_SYLLABLES)))
    return round(SHORT_SPEED + (SPEED - SHORT_SPEED) * share, 3)
MAX_CHARS = 300  # như hãng (DEFAULT_MAX_CHUNK_LENGTH)
# Thứ tự hiện: bốn giọng chủ sách nghe thấy tốt trước (trang chấm 03-10), rồi các giọng còn lại. F = nữ, M = nam.
NAMES = ("F1", "F3", "M4", "M5", "F2", "F4", "F5", "M1", "M2", "M3")
ONNX = ("duration_predictor", "text_encoder", "vector_estimator", "vocoder")
CONFIG_FILE = "onnx/tts.json"
INDEXER_FILE = "onnx/unicode_indexer.json"
STYLE_DIR = "voice_styles"
BENCH_TEXT = "Chiếc thuyền nhỏ trôi chậm giữa dòng sông, mang theo những mùa hè đã xa. Trời hôm nay đẹp quá."

# ---- chữ -> mã ký tự của model (UnicodeProcessor của hãng) --------------------------------------------------------------------------
_EMOJI = re.compile("[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f700-\U0001f77f\U0001f780-\U0001f7ff\U0001f800-\U0001f8ff"
                    "\U0001f900-\U0001f9ff\U0001fa00-\U0001fa6f\U0001fa70-\U0001faff☀-⛿✀-➿\U0001f1e6-\U0001f1ff]+")
_SYMBOLS = {"–": "-", "‑": "-", "—": "-", "¯": " ", "_": " ", "“": '"', "”": '"', "‘": "'", "’": "'",
            "´": "'", "`": "'", "[": " ", "]": " ", "|": " ", "/": " ", "#": " ", "→": " ", "←": " "}
_DECORATION = re.compile(r"[♥☆♡©\\]")
_SPACE_BEFORE = re.compile(r" ([,.!?;:'])")
_DOUBLED_QUOTE = re.compile(r"([\"'`])\1+")
_WHITESPACE = re.compile(r"\s+")
_ENDS_WITH_MARK = re.compile(r"[.!?;:,'\"')\]}…。」』】〉》›»]$")
_TAG = re.compile(r"</?[a-z]{2,3}>")  # sea-g2p đánh dấu chữ nước ngoài bằng <en>…</en>: model chỉ cần chữ


# Mười giọng Supertonic ra -24,1..-25,6 LUFS (đo 03-10, scripts/measure_vieneu_loudness.py --supertonic), dưới đích -20 của mọi giọng
# (loudness.TARGET_LUFS) 4-5 dB; trình phát chỉ GIẢM được âm lượng (loudness.gain_db <= 0), nên nâng ngay lúc tạo clip: +4 dB, đỉnh không
# quá -1 dBFS (đoạn nào đỉnh cao thì nâng ít hơn - không bao giờ méo).
GAIN_DB = 4.0
PEAK_CEILING = 10 ** (-1 / 20)


def louder(wave: Any) -> Any:
    """`wave` (float, -1..1) nâng GAIN_DB, hạ bớt nếu đỉnh vượt PEAK_CEILING."""
    import numpy as np

    peak = float(np.max(np.abs(wave))) if wave.size else 0.0
    gain = 10 ** (GAIN_DB / 20)
    if peak > 0 and peak * gain > PEAK_CEILING:
        gain = max(1.0, PEAK_CEILING / peak)
    return wave * gain


def clean(text: str) -> str:
    """Chữ như model muốn nhận (trước thẻ ngôn ngữ): tách dấu (NFKD, như hãng), bỏ emoji / ký hiệu trang trí, chuẩn dấu câu và khoảng trắng, có dấu
    chấm cuối. Không bao giờ rỗng nếu `text` còn chữ."""
    text = unicode_normalize("NFKD", _TAG.sub("", text))
    text = _EMOJI.sub("", text)
    for old, new in _SYMBOLS.items():
        text = text.replace(old, new)
    text = _DECORATION.sub("", text).replace("@", " at ")
    text = _DOUBLED_QUOTE.sub(r"\1", _SPACE_BEFORE.sub(r"\1", text))
    text = _WHITESPACE.sub(" ", text).strip()
    return text if not text or _ENDS_WITH_MARK.search(text) else text + "."


def normalize_pieces(pieces: list[str]) -> str:
    """Chữ của một khúc đem đọc: qua bộ chuẩn hoá tiếng Việt của sea-g2p (số, ngày, giờ, đơn vị thành chữ) nếu máy có, không thì nguyên chữ."""
    try:
        from . import vieneu_engine as ve

        return ve.normalize(pieces)
    except ImportError:
        return " ".join(pieces)


# ---- engine ---------------------------------------------------------------------------------------------------------------------
class SupertonicEngine:
    """Bốn đồ thị onnxruntime của Supertonic 3 trên CPU. `folder`: thư mục mô-đun (có onnx/, voice_styles/)."""

    def __init__(self, folder: Path, threads: int | None = None) -> None:
        import numpy as np

        from . import vieneu_engine as ve

        config = json.loads((folder / CONFIG_FILE).read_bytes().decode("utf-8"))
        self.SAMPLE_RATE = int(config["ae"]["sample_rate"])  # cùng tên với engine VieNeu (vieneu_engine.join, benchmark)
        self.chunk = int(config["ae"]["base_chunk_size"]) * int(config["ttl"]["chunk_compress_factor"])
        self.latent_dim = int(config["ttl"]["latent_dim"]) * int(config["ttl"]["chunk_compress_factor"])
        self.folder = folder
        self.indexer = np.asarray(json.loads((folder / INDEXER_FILE).read_bytes().decode("utf-8")), dtype=np.int64)
        options = ve._session_options(threads or ve.default_threads(), "cpu")
        self.sessions = {name: ve._session(folder / "onnx" / f"{name}.onnx", options, "cpu") for name in ONNX}
        self._styles: dict[str, tuple[Any, Any]] = {}
        self._lock = threading.Lock()

    def style(self, name: str) -> tuple[Any, Any]:
        """(style_ttl, style_dp) của giọng `name` - đọc một lần."""
        import numpy as np

        with self._lock:
            hit = self._styles.get(name)
            if hit is None:
                data = json.loads((self.folder / STYLE_DIR / f"{name}.json").read_bytes().decode("utf-8"))
                hit = tuple(np.asarray(data[key]["data"], dtype=np.float32).reshape(*data[key]["dims"]) for key in ("style_ttl", "style_dp"))
                self._styles[name] = hit  # type: ignore[assignment]
            return hit  # type: ignore[return-value]

    def ids(self, text: str) -> Any:
        """Mã ký tự của `text` (đã `clean`) trong thẻ ngôn ngữ; ký tự model không có thì bỏ."""
        import numpy as np

        coded = np.asarray([ord(char) for char in f"<{LANGUAGE}>{text}</{LANGUAGE}>"], dtype=np.int64)
        coded = coded[coded < self.indexer.size]
        mapped = self.indexer[coded]
        return mapped[mapped >= 0]

    def infer(self, text: str, name: str, rng: Any, speed: float = SPEED, steps: int = STEPS) -> Any:
        """Một khúc chữ -> sóng âm đơn kênh float32 ở `sample_rate`. `rng`: np.random.RandomState (nhiễu khởi đầu)."""
        import numpy as np

        from . import vieneu_engine as ve

        text = clean(text)
        ids = self.ids(text)
        if not text or not ids.size:
            return np.zeros(0, dtype=np.float32)
        style_ttl, style_dp = self.style(name)
        text_ids = ids.reshape(1, -1)
        text_mask = np.ones((1, 1, ids.size), dtype=np.float32)
        duration = self.sessions["duration_predictor"].run(None, {"text_ids": text_ids, "style_dp": style_dp, "text_mask": text_mask})[0] / speed
        embedding = self.sessions["text_encoder"].run(None, {"text_ids": text_ids, "style_ttl": style_ttl, "text_mask": text_mask})[0]
        samples = int(float(duration[0]) * self.SAMPLE_RATE)
        frames = max(1, (samples + self.chunk - 1) // self.chunk)
        latent_mask = np.ones((1, 1, frames), dtype=np.float32)
        latent = rng.standard_normal((1, self.latent_dim, frames)).astype(np.float32)
        total = np.array([steps], dtype=np.float32)
        for step in range(steps):
            latent = self.sessions["vector_estimator"].run(None, {
                "noisy_latent": latent, "text_emb": embedding, "style_ttl": style_ttl, "text_mask": text_mask, "latent_mask": latent_mask,
                "current_step": np.array([step], dtype=np.float32), "total_step": total})[0]
        wave = self.sessions["vocoder"].run(None, {"latent": latent})[0].reshape(-1)[:samples]
        return ve.trim_and_fade(np.clip(wave, -1.0, 1.0).astype(np.float32), self.SAMPLE_RATE)


# ---- nhà cung cấp ---------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Installed:
    """Nơi mô-đun đặt model (supertonic_module.installed) và có dùng bộ căn chữ không."""

    folder: Path
    aligner: bool = False


def gender_of(name: str) -> str:
    return "female" if name.startswith("F") else "male" if name.startswith("M") else ""


class SupertonicProvider:
    """`locate()`: nơi mô-đun đặt model (None = chưa tải). `engines`: bộ dựng engine (bài thử thay bằng engine giả); `normalize`: chuẩn hoá chữ
    của một khúc (bài thử thay)."""

    id = PREFIX
    speaks_english = True  # CHƯA quyết: 1 hạt giống nuốt "Rose", 4 hạt giống thì không (04-10); chờ phép đo 60 từ x 3 hạt giống. Tên Nhật / Hàn vẫn theo gốc cuốn

    def __init__(self, locate: Callable[[], Installed | None], *, engines: Callable[[Installed], Any] | None = None,
                 aligner: Callable[[], Any] | None = None, normalize: Callable[[list[str]], str] | None = None) -> None:
        self.locate = locate
        self._make = engines or (lambda found: SupertonicEngine(found.folder))
        self._aligner = aligner or _real_aligner
        self._normalize = normalize or normalize_pieces
        self._engine_lock = threading.Lock()  # nạp engine mất vài giây: danh sách giọng không phải chờ
        self._engine: tuple[Path, Any] | None = None

    def voices(self) -> list[Voice]:
        if self.locate() is None:
            return []
        return [Voice(f"{PREFIX}:{name}", f"Supertonic {name}", PREFIX, False, gender=gender_of(name)) for name in NAMES]

    def engine(self, installed: Installed) -> Any:
        with self._engine_lock:
            if self._engine is None or self._engine[0] != installed.folder:
                try:
                    self._engine = (installed.folder, self._make(installed))
                except (OSError, ValueError, KeyError, ImportError) as error:
                    raise VoiceError(f"Giọng Supertonic chưa sẵn sàng ({error}) - hãy tải lại Giọng Supertonic trong Cài đặt.", "voice") from error
            return self._engine[1]

    def forget(self) -> None:
        """Mô-đun vừa cập nhật / gỡ: nạp lại engine ở lần dùng sau."""
        with self._engine_lock:
            self._engine = None

    def _speak(self, installed: Installed, name: str, text: str, origin: str | None = None, readings: Mapping[str, str] | None = None,
               ) -> tuple[Any, int, list[str], list[Unit], list[tuple[int, int]]]:
        """Đọc cả đoạn: (sóng âm, tần số mẫu, chữ hiện, các khúc, [đầu, cuối) của từng khúc theo mẫu). `origin`, `readings`: gốc và cách đọc
        riêng của cuốn, xem `vieneu.spoken_tokens`."""
        import numpy as np

        from . import vieneu_engine as ve

        engine = self.engine(installed)
        toks, parts = units(text, MAX_CHARS, origin, self.speaks_english, readings)
        waves, pauses = [], []
        for unit in parts:
            spoken = self._normalize(unit.pieces)
            waves.append(louder(engine.infer(spoken, name, np.random.RandomState(seed_of(PREFIX, name, " ".join(unit.pieces))), speed_for(spoken))))
            pauses.append(ve.GAP_SECONDS["sentence" if spoken.rstrip()[-1:] in ".!?" else "minor"])
        joined, spans = ve.join(waves, engine.SAMPLE_RATE, pauses[:-1])
        if not joined.size:
            raise VoiceError("Đoạn này không có chữ nào đọc được.", "empty")
        return joined, engine.SAMPLE_RATE, toks, parts, spans

    def _installed(self, name: str) -> Installed:
        installed = self.locate()
        if installed is None:
            raise VoiceError("Giọng Supertonic này chưa tải trên máy.", "voice")
        if name not in NAMES:
            raise VoiceError("Không có giọng Supertonic này.", "voice")
        return installed

    def reading_tag(self, text: str, origin: str | None) -> str:
        return reading_tag(text, origin, self.speaks_english)

    def synthesize(self, text: str, native_voice: str, origin: str | None = None, readings: Mapping[str, str] | None = None) -> Synthesis:
        installed = self._installed(native_voice)
        audio, rate, toks, parts, spans = self._speak(installed, native_voice, text, origin, readings)
        return timed_synthesis(audio, rate, toks, parts, spans, self._aligner() if installed.aligner else None)

    def benchmark(self, tier: str = TIER) -> dict[str, Any]:
        """Tự đo vài giây sau khi tải (cùng hình với VieneuProvider.benchmark): nạp engine, đọc một đoạn mẫu ngắn bằng giọng đầu tiên. RTF = giây
        máy làm / giây nghe được (dưới 1 là kịp nghe)."""
        installed = self._installed(NAMES[0])
        began = time.perf_counter()
        self.engine(installed)
        self._speak(installed, NAMES[0], "Xin chào.")  # lần chạy đầu của onnxruntime chậm hơn hẳn: không tính
        loaded = time.perf_counter()
        audio, rate, *_ = self._speak(installed, NAMES[0], BENCH_TEXT)
        done = time.perf_counter()
        seconds = len(audio) / rate
        return {"rtf": round((done - loaded) / seconds, 3), "firstAudioMs": round((done - loaded) * 1000),
                "loadMs": round((loaded - began) * 1000), "audioSeconds": round(seconds, 2)}


def _real_aligner() -> Any:
    from ..webui import word_timing

    return word_timing.get_aligner()

