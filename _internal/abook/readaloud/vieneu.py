"""Giọng VieNeu cho "Nghe ngay" (docs/LISTEN_ANYTHING.md mục 3): giọng đọc ngay trên máy, không cần mạng, có khi người dùng đã tải mô-đun
"Giọng VieNeu" (webui/vieneu_module.py). Máy chưa tải thì danh sách giọng rỗng; gói đóng sẵn không có numpy nên engine chỉ nạp khi cần.

Một clip = MỘT đoạn của chương. Đoạn được chia thành các "khúc" theo câu như vieneu (`units`: gói câu tới `max_chars` ký tự, câu quá dài cắt ở
dấu phẩy rồi ở khoảng trắng, khúc dưới 20 ký tự gộp vào khúc kề - khúc 1-2 chữ đứng riêng làm model "nói thêm"), đọc từng khúc, ghép với khoảng
nghỉ tối thiểu như vieneu (0,5 giây sau câu, 0,3 giây sau dấu phẩy). Không đọc riêng từng cụm giữa hai dấu phẩy: bộ chuẩn hoá của sea-g2p bỏ dấu
phẩy cuối cụm và chốt dấu chấm, nên mỗi dấu phẩy sẽ thành giọng xuống của cuối câu.

Mốc từng chữ hiện: mỗi khúc biết chính xác chỗ của nó trong clip, rồi căn chữ của khúc ấy vào audio của nó bằng `word_timing.line_words` -
bộ căn CTC (122 MB, phần tuỳ chọn của mô-đun, mặc định có trên máy tính) nếu có, không thì chia thời gian theo âm tiết neo vào các khoảng lặng
dò bằng năng lượng ở chỗ dấu câu.
"""
from __future__ import annotations

import hashlib
import io
import json
import threading
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .model import Synthesis, Voice, VoiceError

PREFIX = "vieneu"
TIERS = ("turbo", "nano")
TIER_LABEL = {"turbo": "VieNeu", "nano": "VieNeu Nano"}
VOICE_FILES = {"turbo": "voices_v3_turbo.json", "nano": "voices_v3_nano.json"}
MAX_CHARS = {"turbo": 256, "nano": 140}  # như vieneu: Nano học trên đoạn <= 15 giây nên khúc ngắn hơn
MIN_UNIT_CHARS = 20
SENTENCE_END = ".!?…"
PHRASE_END = ",;:"
CLOSERS = "\"'”’)]»"
ALIGN_RATE = 16_000
BENCH_TEXT = "Chiếc thuyền nhỏ trôi chậm giữa dòng sông, mang theo những mùa hè đã xa. Trời hôm nay đẹp quá."


@dataclass(frozen=True)
class Installed:
    """Những gì mô-đun đã đặt trên máy (vieneu_module.installed): thư mục từng giọng, file giọng có sẵn, có dùng bộ căn chữ không."""

    voices: Path
    turbo: tuple[Path, Path] | None = None  # (thư mục model, thư mục bộ giải mã)
    nano: Path | None = None
    aligner: bool = False


@dataclass
class Unit:
    """Một khúc: chữ hiện từ `first` tới `last` (kể cả), đem đọc như các câu `pieces`."""

    first: int
    last: int
    pieces: list[str] = field(default_factory=list)

    def text(self, toks: list[str]) -> str:
        return " ".join(toks[self.first:self.last + 1])


def _ends(token: str, marks: str) -> bool:
    core = token.rstrip(CLOSERS)
    return bool(core) and core[-1] in marks


def _groups(toks: list[str], first: int, last: int, marks: str) -> list[tuple[int, int]]:
    out, start = [], first
    for index in range(first, last + 1):
        if _ends(toks[index], marks) or index == last:
            out.append((start, index))
            start = index + 1
    return out


def _length(toks: list[str], first: int, last: int) -> int:
    return sum(len(token) for token in toks[first:last + 1]) + (last - first)


def _pack(toks: list[str], spans: list[tuple[int, int]], max_chars: int) -> list[tuple[int, int]]:
    """Gộp các khoảng liền nhau thành khoảng dài nhất không quá `max_chars` ký tự."""
    out: list[tuple[int, int]] = []
    for first, last in spans:
        if out and _length(toks, out[-1][0], last) <= max_chars:
            out[-1] = (out[-1][0], last)
        else:
            out.append((first, last))
    return out


def units(text: str, max_chars: int) -> tuple[list[str], list[Unit]]:
    """Chữ hiện của đoạn + các khúc đem đọc (mọi chữ hiện thuộc đúng một khúc, theo thứ tự)."""
    from ..webui.word_timing import tokens

    toks = tokens(text)
    if not toks:
        return toks, []
    pieces: list[tuple[int, int]] = []
    for first, last in _groups(toks, 0, len(toks) - 1, SENTENCE_END):
        if _length(toks, first, last) <= max_chars:
            pieces.append((first, last))
            continue
        for p_first, p_last in _pack(toks, _groups(toks, first, last, PHRASE_END), max_chars):  # câu dài: cắt ở dấu phẩy, rồi ở khoảng trắng
            if _length(toks, p_first, p_last) <= max_chars:
                pieces.append((p_first, p_last))
            else:
                pieces += _pack(toks, [(i, i) for i in range(p_first, p_last + 1)], max_chars)
    result: list[Unit] = []
    for first, last in pieces:  # gói câu vào khúc như vieneu (pack_sentences_into_chunks)
        if result and _length(toks, result[-1].first, last) <= max_chars:
            result[-1].last = last
            result[-1].pieces.append(" ".join(toks[first:last + 1]))
        else:
            result.append(Unit(first, last, [" ".join(toks[first:last + 1])]))
    while len(result) > 1:  # khúc quá ngắn gộp vào khúc kề ngắn hơn (bằng nhau: khúc sau)
        short = [i for i, unit in enumerate(result) if _length(toks, unit.first, unit.last) < MIN_UNIT_CHARS]
        if not short:
            break
        i = min(short, key=lambda k: _length(toks, result[k].first, result[k].last))
        right = i + 1 < len(result)
        if right and i > 0:
            right = _length(toks, result[i + 1].first, result[i + 1].last) <= _length(toks, result[i - 1].first, result[i - 1].last)
        a, b = (i, i + 1) if right else (i - 1, i)
        result[a] = Unit(result[a].first, result[b].last, result[a].pieces + result[b].pieces)
        del result[b]
    return toks, result


def resample(wave_data: Any, rate: int, target: int = ALIGN_RATE) -> Any:
    """Đổi tần số mẫu bằng FFT (cắt phổ = lọc thông thấp lý tưởng) - đủ cho bộ căn chữ 16 kHz."""
    import numpy as np

    data = np.asarray(wave_data, dtype=np.float32)
    if rate == target or data.size == 0:
        return data
    count = max(1, int(round(data.size * target / rate)))
    spectrum = np.fft.rfft(data)
    keep = count // 2 + 1
    trimmed = np.zeros(keep, dtype=spectrum.dtype)
    trimmed[:min(keep, spectrum.size)] = spectrum[:min(keep, spectrum.size)]
    return (np.fft.irfft(trimmed, count) * (count / data.size)).astype(np.float32)


def wav_bytes(samples: Any, rate: int) -> bytes:
    import numpy as np

    pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0) * 32767.0).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


def seed_of(*parts: str) -> int:
    """Hạt giống cố định theo giọng + chữ: cùng đoạn cùng giọng luôn ra cùng audio (bộ đệm, đọc lại)."""
    return int(hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:8], 16)


class VieneuProvider:
    """`locate()`: nơi mô-đun đặt các phần (None = chưa tải gì). `engines`: bộ dựng engine theo tầng (bài thử thay bằng engine giả)."""

    id = PREFIX

    def __init__(self, locate: Callable[[], Installed | None], *, engines: Callable[[str, Installed], Any] | None = None,
                 aligner: Callable[[], Any] | None = None) -> None:
        self.locate = locate
        self._make = engines or _real_engine
        self._aligner = aligner or _real_aligner
        self._lock = threading.Lock()
        self._engine_lock = threading.Lock()  # nạp engine mất vài giây: danh sách giọng không phải chờ
        self._engines: dict[tuple[str, str], Any] = {}
        self._presets: dict[tuple[str, str, float], dict[str, dict[str, Any]]] = {}

    # ---- giọng ------------------------------------------------------------------------------------------------------------------
    def _tiers(self, installed: Installed | None) -> list[str]:
        if installed is None:
            return []
        return [tier for tier in TIERS if getattr(installed, tier) is not None and (installed.voices / VOICE_FILES[tier]).is_file()]

    def presets(self, tier: str, installed: Installed) -> dict[str, dict[str, Any]]:
        """Giọng có sẵn của một tầng, theo thứ tự hiện (Turbo: giọng chọn lọc trước theo `featured`, rồi theo file), đọc một lần cho mỗi file."""
        path = installed.voices / VOICE_FILES[tier]
        try:
            stamp = path.stat().st_mtime
        except OSError:
            return {}
        key = (tier, str(path), stamp)
        with self._lock:
            hit = self._presets.get(key)
            if hit is None:
                data = json.loads(path.read_bytes().decode("utf-8")).get("presets") or {}
                order = sorted(enumerate(data.items()), key=lambda item: (item[1][1].get("featured") is None,
                                                                          item[1][1].get("featured") or 0, item[0]))
                hit = {name: value for _, (name, value) in order}
                self._presets = {k: v for k, v in self._presets.items() if k[:2] != key[:2]}
                self._presets[key] = hit
            return hit

    def voices(self) -> list[Voice]:
        installed = self.locate()
        out: list[Voice] = []
        for tier in self._tiers(installed):
            assert installed is not None
            for name, preset in self.presets(tier, installed).items():
                gender = str(preset.get("gender") or "")  # danh sách giọng ghi sẵn nam / nữ (bản Kotlin: VieneuPreset.gender)
                out.append(Voice(f"{PREFIX}:{tier}/{name}", f"{name} ({TIER_LABEL[tier]})", PREFIX, False,
                                 gender=gender if gender in ("female", "male") else ""))
        return out

    # ---- engine -----------------------------------------------------------------------------------------------------------------
    def engine(self, tier: str, installed: Installed) -> Any:
        where = str(installed.turbo if tier == "turbo" else installed.nano)
        with self._engine_lock:
            hit = self._engines.get((tier, where))
            if hit is None:
                try:
                    hit = self._make(tier, installed)
                except (OSError, ValueError, KeyError, ImportError) as error:
                    raise VoiceError(f"Giọng VieNeu chưa sẵn sàng ({error}) - hãy tải lại Giọng VieNeu trong Cài đặt.", "voice") from error
                self._engines = {k: v for k, v in self._engines.items() if k[0] != tier}
                self._engines[(tier, where)] = hit
            return hit

    def forget(self) -> None:
        """Mô-đun vừa cập nhật: nạp lại engine và danh sách giọng ở lần dùng sau."""
        with self._engine_lock:
            self._engines.clear()
        with self._lock:
            self._presets.clear()

    def _voice(self, native: str) -> tuple[str, str, Installed, dict[str, Any]]:
        tier, _, name = native.partition("/")
        installed = self.locate()
        if tier not in self._tiers(installed):
            raise VoiceError("Giọng VieNeu này chưa tải trên máy.", "voice")
        assert installed is not None
        preset = self.presets(tier, installed).get(name)
        if preset is None:
            raise VoiceError("Không có giọng VieNeu này.", "voice")
        return tier, name, installed, preset

    def _speak(self, tier: str, name: str, installed: Installed, preset: dict[str, Any],
               text: str) -> tuple[Any, int, list[str], list[Unit], list[tuple[int, int]]]:
        """Đọc cả đoạn: (sóng âm, tần số mẫu, chữ hiện, các khúc, [đầu, cuối) của từng khúc theo mẫu)."""
        import numpy as np

        from . import vieneu_engine as ve

        engine = self.engine(tier, installed)
        toks, parts = units(text, MAX_CHARS[tier])
        speaker = np.asarray(preset["speaker_emb"], dtype=np.float32)
        waves, pauses = [], []
        for unit in parts:
            phonemes = ve.phonemize(unit.pieces)
            seed = seed_of(tier, name, " ".join(unit.pieces))
            if not phonemes:
                audio = np.zeros(0, dtype=np.float32)
            elif tier == "turbo":
                codes = ve.strip_encoder_pad_frame(np.asarray(preset["codes"], dtype=np.int64)) if preset.get("codes") is not None else None
                audio = engine.infer(phonemes, speaker, codes, rng=np.random.RandomState(seed))
            else:
                audio = engine.infer(phonemes, speaker, np.asarray(preset["style"], dtype=np.float32), seed=seed)
            waves.append(audio)
            pauses.append(ve.GAP_SECONDS["sentence" if phonemes.rstrip()[-1:] in ".!?" else "minor"])
        joined, spans = ve.join(waves, engine.SAMPLE_RATE, pauses[:-1])
        if not joined.size:
            raise VoiceError("Đoạn này không có chữ nào đọc được.", "empty")
        return joined, engine.SAMPLE_RATE, toks, parts, spans

    def synthesize(self, text: str, native_voice: str) -> Synthesis:
        from ..webui import word_timing

        tier, name, installed, preset = self._voice(native_voice)
        audio, rate, toks, parts, spans = self._speak(tier, name, installed, preset, text)
        duration = len(audio) * 1000 // rate
        aligner = self._aligner() if installed.aligner else None
        words: list[list[int]] = []
        for unit, (start, stop) in zip(parts, spans):
            if stop <= start:  # khúc không ra tiếng: các chữ đứng ở chỗ khúc ấy
                words += [[start * 1000 // rate, start * 1000 // rate] for _ in range(unit.last - unit.first + 1)]
                continue
            found, _how, _confidence = word_timing.line_words(resample(audio[start:stop], rate), unit.text(toks), start / rate, aligner)
            words += found
        previous = 0
        for pair in words:  # không lùi, không quá cuối clip
            pair[0] = min(max(pair[0], previous), duration)
            pair[1] = min(max(pair[1], pair[0]), duration)
            previous = pair[0]
        return Synthesis(wav_bytes(audio, rate), [], duration, "wav", "audio/wav", words=words)

    def benchmark(self, tier: str) -> dict[str, Any]:
        """Tự đo vài giây sau khi tải: nạp engine, đọc một đoạn mẫu ngắn bằng giọng đầu tiên. RTF = giây máy làm / giây nghe được (dưới 1 là
        kịp nghe); `firstAudioMs` = thời gian làm cả đoạn mẫu (~5 giây nghe) - clip là cả đoạn, nên đoạn đầu chương phát được sau chừng ấy."""
        installed = self.locate()
        if tier not in self._tiers(installed):
            raise VoiceError("Giọng VieNeu này chưa tải trên máy.", "voice")
        assert installed is not None
        name, preset = next(iter(self.presets(tier, installed).items()))
        began = time.perf_counter()
        self.engine(tier, installed)
        self._speak(tier, name, installed, preset, "Xin chào.")  # lần chạy đầu của onnxruntime chậm hơn hẳn: không tính
        loaded = time.perf_counter()
        audio, rate, *_ = self._speak(tier, name, installed, preset, BENCH_TEXT)
        done = time.perf_counter()
        seconds = len(audio) / rate
        return {"rtf": round((done - loaded) / seconds, 3), "firstAudioMs": round((done - loaded) * 1000),
                "loadMs": round((loaded - began) * 1000), "audioSeconds": round(seconds, 2)}


def _real_engine(tier: str, installed: Installed) -> Any:
    from . import vieneu_engine as ve

    if tier == "turbo":
        assert installed.turbo is not None
        return ve.TurboEngine(installed.turbo[0], installed.turbo[1])
    assert installed.nano is not None
    return ve.NanoEngine(installed.nano)


def _real_aligner() -> Any:
    from ..webui import word_timing

    return word_timing.get_aligner()
