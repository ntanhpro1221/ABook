"""Giọng VieNeu-TTS v3 (Turbo, Nano) chạy bằng onnxruntime + numpy, KHÔNG cần gói `vieneu` (docs/LISTEN_ANYTHING.md mục 3, "VieNeu module").

Viết lại đúng phần suy luận của VieNeu-TTS 3.8.1 (pnnbao97/VieNeu-TTS, Apache-2.0) mà "Nghe ngay" cần - đọc bằng giọng có sẵn, không nhân bản giọng:
- `_v3_turbo_engine/onnx_runtime_lite.py` (Turbo: prefill + decode_step + acoustic_cached + bộ giải mã MOSS, lấy mẫu top-k/top-p, phạt lặp
  cửa sổ trượt, chặn "nói thêm" của câu ngắn), `v3nano.py` (Nano: flow matching Euler + CFG, 24 kHz),
- `vieneu_utils/core_utils.py` (trần frame theo phoneme, đếm âm tiết, cắt mép, khoảng nghỉ giữa các khúc),
- bộ tách từ BPE mức byte của `tokenizer.json` (thư viện `tokenizers` viết bằng Rust; ở đây thuần Python, cùng kết quả - bài thử so cả hai).
Chữ -> phoneme vẫn là sea-g2p (Rust + từ điển 63 MB, Apache-2.0, không phụ thuộc gì): mô-đun tải wheel ghim của nó, không viết lại.

Cùng đầu vào thì ra cùng sóng âm như gói vieneu 3.8.1 (tests/test_readaloud_vieneu.py, chỉ chạy khi máy có vieneu): Turbo lấy mẫu bằng cùng
phép bốc của `np.random.choice` (RandomState), Nano cùng nhiễu `default_rng`. Khác có chủ ý: không đóng dấu nước (gói `perth` không cài thì
vieneu cũng không đóng), không nhân bản giọng, thiết bị chọn được (CPU hay DirectML).
"""
from __future__ import annotations

import json
import math
import os
import re
import threading
import unicodedata
from collections import Counter, deque
from pathlib import Path
from typing import Any, Sequence

import numpy as np

TURBO_RATE = 48_000
NANO_RATE = 24_000
DEFAULT_SAMPLING = {"temperature": 0.8, "top_k": 25, "top_p": 0.95, "repetition_penalty": 1.2, "repetition_window": 64}
MAX_NEW_FRAMES = 300
NANO_STEPS, NANO_CFG = 16, 3.0
NANO_MAX_SECONDS = 15.0
NANO_MIN_FRAMES = 2
BABBLE_RETRIES = 2

# ---- core_utils: trần frame, âm tiết, mép, khoảng nghỉ ------------------------------------------------------------------------
_MARKUP = re.compile(r"<\|emotion_\d+\|>|</?en>")
_IPA_VOWELS = set("aeiouyæɐɑɒɔəɘɛɜɤɯɵøœʉʊʌɪɨɚɝᵻᵿ")
GAP_SECONDS = {"para": 0.70, "sentence": 0.50, "minor": 0.30}
ENCODER_PAD_CODE = 455


def phoneme_syllables(phonemes: str) -> int:
    """Số tiếng của chuỗi phoneme sea-g2p (core_utils.syllable_count)."""
    total = 0
    for tok in _MARKUP.sub("", phonemes or "").split():
        groups, in_v, consonant_seen = 0, False, True
        for ch in tok:
            if ch in _IPA_VOWELS:
                if not in_v and consonant_seen:
                    groups += 1
                in_v, consonant_seen = True, False
            elif ch in "ːˈˌ" or ch.isdigit():
                if ch in "ˈˌ" and groups > 0:
                    in_v, consonant_seen = False, True
                else:
                    in_v = False
            else:
                in_v, consonant_seen = False, True
        if any(ch.isalpha() for ch in tok):
            total += max(1, groups)
    return total


def _cue_only(phonemes: str) -> bool:
    ph = phonemes or ""
    return "<|emotion_" in ph and not any(ch.isalpha() for ch in _MARKUP.sub("", ph))


def max_expected_frames(phonemes: str) -> int:
    """Trần frame hợp lý của một khúc (core_utils.max_expected_frames): 24 + 2 x số ký tự phoneme; khúc <= 4 tiếng còn 13 + 5 x (tiếng - 1)."""
    eff_len = len(_MARKUP.sub("", phonemes or ""))
    cap = 24 + int(np.ceil(2.0 * eff_len))
    if _cue_only(phonemes):
        return min(cap, 13)
    if "<|emotion_" not in (phonemes or ""):
        syl = max(1, phoneme_syllables(phonemes))
        if syl <= 4 and eff_len <= 24 * syl:
            cap = min(cap, 13 + 5 * (syl - 1))
    return cap


def edge_silence(wav: np.ndarray, sr: int, thresh_db: float = -45.0, win_s: float = 0.01) -> tuple[int, int]:
    """(im lặng đầu, im lặng cuối) tính bằng mẫu, theo bao mean|x| cửa sổ 10 ms."""
    n_samp = int(wav.size)
    win = max(1, int(win_s * sr))
    n_win = n_samp // win
    if n_win == 0:
        return n_samp, 0
    env = np.abs(wav[: n_win * win]).reshape(n_win, win).mean(1)
    above = np.flatnonzero(env > 10 ** (thresh_db / 20))
    if not above.size:
        return n_samp, 0
    return int(above[0]) * win, n_samp - (int(above[-1]) + 1) * win


def trim_and_fade(wav: np.ndarray, sr: int) -> np.ndarray:
    """Cắt im lặng hai đầu (giữ 40 ms) rồi fade cosine 15 ms ở hai mép (đầu ra của Nano)."""
    if wav.size == 0:
        return wav
    lead, tail = edge_silence(wav, sr)
    keep = int(0.04 * sr)
    out = np.array(wav[max(0, lead - keep): wav.size - max(0, tail - keep)], dtype=np.float32, copy=True)
    n = min(int(0.015 * sr), out.size // 2)
    if n > 0:
        ramp = (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n))).astype(np.float32)
        out[:n] *= ramp
        out[-n:] *= ramp[::-1]
    return out


def pause_pad_samples(prev_wav: np.ndarray, next_wav: np.ndarray, sr: int, pause_s: float) -> int:
    """Số mẫu im lặng phải chèn để khoảng nghỉ thật (đuôi trước + chèn + đầu sau) đạt `pause_s`."""
    lead_prev, tail = edge_silence(prev_wav, sr)
    if lead_prev == prev_wav.size:
        tail = prev_wav.size
    lead, _ = edge_silence(next_wav, sr)
    return max(0, int(pause_s * sr) - tail - lead)


def count_speech_bursts(wav: np.ndarray, sr: int) -> int:
    wav = np.asarray(wav, dtype=np.float32).reshape(-1)
    hop = max(1, int(sr * 0.010))
    n = len(wav) // hop
    if n == 0:
        return 0
    env = np.sqrt((wav[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    peak = float(env.max())
    if peak <= 1e-6:
        return 0
    on = env > peak * (10 ** (-18.0 / 20))
    bursts, start, last_on = [], None, None
    for i, o in enumerate(on):
        if o:
            if start is None:
                start = i
            elif i - last_on > 6:
                bursts.append((start, last_on))
                start = i
            last_on = i
    if start is not None:
        bursts.append((start, last_on))
    return sum(1 for a, b in bursts if (b - a + 1) >= 3)


def babble_suspect(wav: np.ndarray, sr: int, phonemes: str, cap_frames: int, n_frames: int) -> tuple[bool, int, int, int]:
    """Khúc <= 3 tiếng nghi "nói thêm": nhiều cụm âm hơn số tiếng, hay khúc <= 2 tiếng chạm trần frame (core_utils.babble_suspect)."""
    if _cue_only(phonemes):
        return n_frames >= cap_frames - 1, 0, 0, n_frames
    syl = phoneme_syllables(phonemes)
    if syl == 0 or syl > 3 or "<|emotion_" in (phonemes or ""):
        return False, syl, 0, 0
    bursts = count_speech_bursts(wav, sr)
    return (bursts > syl) or (syl <= 2 and n_frames >= cap_frames - 1), syl, bursts, n_frames


def babble_prefer(new: tuple, old: tuple) -> bool:
    (n_bad, _, n_b, n_len), (o_bad, _, o_b, o_len) = new, old
    if n_bad != o_bad:
        return not n_bad
    return n_b < o_b or (n_b == o_b and n_len < o_len)


def strip_encoder_pad_frame(codes: np.ndarray) -> np.ndarray:
    """Bỏ frame đuôi do bộ mã hoá đệm (codebook-0 = 455) khỏi mã tham chiếu đã lưu (core_utils.strip_encoder_pad_frame)."""
    if codes.ndim == 2 and codes.shape[0] > 1 and int(codes[-1, 0]) == ENCODER_PAD_CODE:
        return codes[:-1]
    return codes


class _Window:
    """Lịch sử phạt lặp của một codebook: chỉ các mã trong `window` frame gần nhất (rep_history._ChannelWindow)."""

    __slots__ = ("seen", "order", "window")

    def __init__(self, window: int) -> None:
        self.seen: Counter = Counter()
        self.order: deque = deque()
        self.window = int(window)

    def add(self, code: int) -> None:
        self.seen[code] += 1
        if self.window > 0:
            self.order.append(code)
            if len(self.order) > self.window:
                old = self.order.popleft()
                if self.seen[old] <= 1:
                    del self.seen[old]
                else:
                    self.seen[old] -= 1


# ---- bộ tách từ BPE mức byte (tokenizer.json của Turbo) -------------------------------------------------------------------------
def _bytes_to_unicode() -> dict[int, str]:
    keep = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    chars = keep[:]
    extra = 0
    for byte in range(256):
        if byte not in keep:
            keep.append(byte)
            chars.append(256 + extra)
            extra += 1
    return {byte: chr(char) for byte, char in zip(keep, chars)}


_WHITE = "\t\n\x0b\x0c\r \x85\xa0  -     　"  # thuộc tính Unicode White_Space
_classes: tuple[str, str] | None = None


def _letter_number_classes() -> tuple[str, str]:
    """Lớp ký tự \\p{L} và \\p{N} cho `re` (không có \\p{...}): dựng một lần từ unicodedata."""
    global _classes
    if _classes is None:
        ranges: dict[str, list[list[int]]] = {"L": [], "N": []}
        for code in range(0x110000):
            kind = unicodedata.category(chr(code))[0]
            if kind in ranges:
                spans = ranges[kind]
                if spans and spans[-1][1] == code - 1:
                    spans[-1][1] = code
                else:
                    spans.append([code, code])

        def render(spans: list[list[int]]) -> str:
            return "".join(re.escape(chr(a)) if a == b else f"{re.escape(chr(a))}-{re.escape(chr(b))}" for a, b in spans)

        _classes = (render(ranges["L"]), render(ranges["N"]))
    return _classes


class ByteBPE:
    """`tokenizers` ByteLevel-BPE đúng cấu hình tokenizer.json của Turbo: tách token đặc biệt, NFC, tách trước bằng regex kiểu GPT-2 (Split,
    Isolated), ánh xạ byte -> ký tự, ghép theo bảng merges (thứ hạng thấp ghép trước), không có trong từ điển -> unk."""

    def __init__(self, path: Path | str) -> None:
        spec = json.loads(Path(path).read_bytes().decode("utf-8"))
        model = spec["model"]
        if model.get("type") != "BPE" or (spec.get("normalizer") or {}).get("type") not in (None, "NFC"):
            raise ValueError("tokenizer.json không phải ByteLevel-BPE + NFC như VieNeu 3.8.1")
        self.vocab: dict[str, int] = dict(model["vocab"])
        merges = [tuple(item.split(" ", 1)) if isinstance(item, str) else tuple(item) for item in model.get("merges", [])]
        self.ranks = {pair: rank for rank, pair in enumerate(merges)}
        self.unk = self.vocab.get(model.get("unk_token") or "")
        self.nfc = (spec.get("normalizer") or {}).get("type") == "NFC"
        added = sorted((item["content"] for item in spec.get("added_tokens", [])), key=len, reverse=True)
        self.added = {item["content"]: item["id"] for item in spec.get("added_tokens", [])}
        self.special = re.compile("(" + "|".join(re.escape(text) for text in added) + ")") if added else None
        letters, numbers = _letter_number_classes()
        w = _WHITE
        self.split = re.compile(
            rf"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n{letters}{numbers}]?[{letters}]+|[{numbers}]| ?[^{w}{letters}{numbers}]+[\r\n]*"
            rf"|[{w}]*[\r\n]+|[{w}]+(?![^{w}])|[{w}]+")
        self.byte_map = _bytes_to_unicode()
        self._cache: dict[str, list[int]] = {}

    def _bpe(self, word: str) -> list[int]:
        hit = self._cache.get(word)
        if hit is not None:
            return hit
        parts = list(word)
        while len(parts) > 1:
            best = min(((self.ranks.get((parts[i], parts[i + 1]), math.inf), i) for i in range(len(parts) - 1)))
            if best[0] == math.inf:
                break
            i = best[1]
            parts[i:i + 2] = [parts[i] + parts[i + 1]]
        ids: list[int] = []
        for part in parts:
            token = self.vocab.get(part)
            if token is not None:
                ids.append(token)
            elif self.unk is not None:
                ids.append(self.unk)
        if len(self._cache) < 50_000:
            self._cache[word] = ids
        return ids

    def encode(self, text: str) -> list[int]:
        pieces = self.special.split(text) if self.special is not None else [text]
        out: list[int] = []
        for index, piece in enumerate(pieces):
            if not piece:
                continue
            if self.special is not None and index % 2 == 1:
                out.append(self.added[piece])
                continue
            if self.nfc:
                piece = unicodedata.normalize("NFC", piece)
            for match in self.split.finditer(piece):
                out += self._bpe("".join(self.byte_map[b] for b in match.group(0).encode("utf-8")))
        return out


# ---- chữ -> phoneme (sea-g2p) ----------------------------------------------------------------------------------------------------
_g2p_lock = threading.Lock()
_pipeline: Any = None


def _sea() -> Any:
    global _pipeline
    with _g2p_lock:
        if _pipeline is None:
            from sea_g2p import SEAPipeline  # wheel ghim của mô-đun (vieneu_module) hay gói cài sẵn trên máy dev
            _pipeline = SEAPipeline(lang="vi")
        return _pipeline


def normalize(sentences: Sequence[str]) -> str:
    """Chữ của MỘT khúc gồm các câu `sentences` sau chuẩn hoá của sea-g2p (số, ngày, giờ, đơn vị thành chữ; chữ thường), từng câu một và nối
    bằng dấu cách. Chưa chốt dấu cuối, chưa thành phoneme - phần chữ này cũng đem đọc cho giọng nhận chữ (Supertonic)."""
    pipeline = _sea()
    return " ".join(part for part in (pipeline.normalizer.normalize(text, punc_norm=False) for text in sentences) if part)


def phonemize(sentences: Sequence[str]) -> str:
    """Phoneme của MỘT khúc gồm các câu `sentences`, đúng chuỗi của vieneu 3.8.1 cho khúc ấy: chuẩn hoá từng câu (`normalize`), chốt dấu cuối
    của cả khúc (`punc_norm`), rồi sea-g2p (chuẩn hoá + G2P, punc_norm bật) như `phonemize_text_with_emotions`.
    Khác vieneu ở MỘT điểm: `punc_norm` ép dấu cuối của khúc dưới 5 từ về "." ("Thật sao?" thành "Thật sao.") nên câu hỏi / cảm thán ngắn mất giọng
    hỏi, giọng cảm (đo 10-10 trên Turbo của app: F0 cuối câu hỏi ngắn +0,1 đến +0,5 st tuỳ giọng khi giữ dấu - nhỏ nhưng đúng chiều, và phoneme đúng chữ). Khúc kết bằng "?" / "!" giữ dấu ấy; khúc thiếu dấu vẫn được thêm "."."""
    from sea_g2p import punc_norm

    text = normalize(sentences)
    chunk = punc_norm(text)
    if not chunk.strip():
        return ""
    phonemes = _sea().run(chunk, punc_norm=True)
    if phonemes.endswith(".") and ("?" in text or "!" in text):
        written = _sea().run(text, punc_norm=False).rstrip()  # dấu cuối thật của khúc, chưa bị ép
        if written.endswith(("?", "!")):
            phonemes = phonemes[:-1] + written[-1]
    return phonemes


# ---- phiên onnxruntime ----------------------------------------------------------------------------------------------------------
def default_threads() -> int:
    return min(max((os.cpu_count() or 8) // 2, 1), 8)


def _session_options(threads: int, device: str) -> Any:
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.inter_op_num_threads = 1
    options.add_session_config_entry("session.intra_op.allow_spinning", "0")
    options.intra_op_num_threads = int(threads) if threads and threads > 0 else default_threads()
    options.log_severity_level = 3
    if device == "dml":  # DirectML đòi tắt mem pattern và chạy tuần tự
        options.enable_mem_pattern = False
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return options


def providers(device: str) -> list[str]:
    return ["DmlExecutionProvider", "CPUExecutionProvider"] if device == "dml" else ["CPUExecutionProvider"]


def _session(path: Path, options: Any, device: str) -> Any:
    import onnxruntime as ort

    return ort.InferenceSession(str(path), options, providers=providers(device))


# ---- Turbo ---------------------------------------------------------------------------------------------------------------------
class TurboEngine:
    """VieNeu-TTS v3 Turbo int8 (48 kHz). `model_dir`: các file onnx_int8 của repo; `codec_dir`: bộ giải mã MOSS."""

    SAMPLE_RATE = TURBO_RATE

    def __init__(self, model_dir: Path | str, codec_dir: Path | str, *, threads: int = 0, device: str = "cpu",
                 sessions: dict[str, Any] | None = None) -> None:
        model_dir, codec_dir = Path(model_dir), Path(codec_dir)
        c = json.loads((model_dir / "config.json").read_bytes().decode("utf-8"))
        self.n_vq = int(c["n_vq"])
        self.hidden = int(c["hidden_size"])
        self.layers = int(c["num_hidden_layers"])
        self.local_layers = int(c.get("local_num_hidden_layers", 1))
        self.local_heads = int(c.get("local_num_attention_heads", 8))
        self.local_head_dim = self.hidden // self.local_heads
        self.audio_pad = int(c["audio_pad_token_id"])
        self.tps = int(c["text_prompt_start_token_id"])
        self.tpe = int(c["text_prompt_end_token_id"])
        self.sgs = int(c["speech_generation_start_token_id"])
        self.eos_speech = int(c["speech_generation_end_token_id"])
        self.ref_slot = int(c["audio_ref_slot_token_id"])
        self.style_id = int(c.get("default_style_token_id", 16))
        self.use_speaker = bool(c.get("use_speaker_embedding", False))
        z = np.load(model_dir / "vieneu_v3_heads.npz")
        self.text_emb = z["text_emb"].astype(np.float32)
        self.audio_emb = z["audio_emb"].astype(np.float32)
        if self.use_speaker:
            self.xvec_w = z["xvec_w"].astype(np.float32)
            self.xvec_b = z["xvec_b"].astype(np.float32)
            self.xvec_ln_w = z["xvec_ln_w"].astype(np.float32)
            self.xvec_ln_b = z["xvec_ln_b"].astype(np.float32)
            self.xvec_ln_eps = float(z["xvec_ln_eps"])
        self.tokenizer = ByteBPE(model_dir / "tokenizer.json")
        self.device = device
        self._lock = threading.RLock()
        if sessions is not None:  # bài thử: phiên giả
            self.pre, self.dec, self.ac, self.codec = sessions["pre"], sessions["dec"], sessions["ac"], sessions["codec"]
        else:
            options = _session_options(threads, device)
            self.pre = _session(model_dir / "vieneu_prefill.onnx", options, device)
            self.dec = _session(model_dir / "vieneu_decode_step.onnx", options, device)
            self.ac = _session(model_dir / "vieneu_acoustic_cached.onnx", options, device)
            self.codec = _session(codec_dir / "moss_audio_tokenizer_decode_full.onnx", options, device)

    def _anchor(self, speaker_emb: np.ndarray) -> np.ndarray | None:
        if not self.use_speaker:
            return None
        v = np.asarray(speaker_emb, dtype=np.float32).reshape(-1)
        v = v @ self.xvec_w.T + self.xvec_b
        v = (v - v.mean()) / np.sqrt(v.var() + self.xvec_ln_eps)
        return (v * self.xvec_ln_w + self.xvec_ln_b).astype(np.float32)

    def _embed(self, rows: np.ndarray, anchor: np.ndarray | None) -> np.ndarray:
        emb = self.text_emb[rows[:, 0]]
        for ch in range(self.n_vq):
            ids = rows[:, ch + 1]
            valid = ids != self.audio_pad
            emb = emb + self.audio_emb[ch][np.where(valid, ids, 0)] * valid[:, None]
        if anchor is not None:
            emb = emb + anchor[None]
        return emb[None].astype(np.float32)

    def _rows(self, phonemes: str, ref_codes: np.ndarray | None) -> np.ndarray:
        text_ids = [self.style_id, self.tps] + self.tokenizer.encode(phonemes) + [self.tpe]
        rows = np.full((len(text_ids), self.n_vq + 1), self.audio_pad, dtype=np.int64)
        rows[:, 0] = text_ids
        if ref_codes is None:
            return rows
        rc = np.asarray(ref_codes, dtype=np.int64)
        ref = np.full((rc.shape[0], self.n_vq + 1), self.audio_pad, dtype=np.int64)
        ref[:, 0] = self.ref_slot
        ref[:, 1:] = rc
        return np.concatenate([rows, ref], axis=0)

    @staticmethod
    def _sample(logits: np.ndarray, temperature: float, top_k: int, top_p: float, rep_pen: float, prev: _Window | None,
                rng: np.random.RandomState) -> int:
        """Cùng phép tính với OnnxV3LiteEngine._sample; bốc bằng `rng` như `np.random.choice(n, p=p)` (cdf chuẩn hoá, searchsorted phải)."""
        logits = logits.astype(np.float32)
        if not math.isclose(rep_pen, 1.0) and prev is not None and prev.seen:
            idx = np.fromiter(prev.seen, dtype=np.int64, count=len(prev.seen))
            sel = logits[idx]
            logits = logits.copy()
            logits[idx] = np.where(sel < 0, sel * rep_pen, sel / rep_pen)
        if not (temperature and temperature > 0):
            return int(logits.argmax())
        logits = logits / temperature
        size = logits.shape[-1]
        cand = np.argpartition(logits, -int(top_k))[-int(top_k):] if top_k and 0 < int(top_k) < size else np.arange(size)
        cs = logits[cand]
        order = np.argsort(cs)[::-1]
        cand = cand[order]
        x = cs[order] - np.max(cs[order])
        p = np.exp(x) / np.sum(np.exp(x))
        if top_p and top_p < 1.0:
            keep = (np.cumsum(p) - p) < top_p
            p = p * keep
            p = p / p.sum()
        cdf = np.asarray(p, dtype=np.float64).cumsum()
        cdf /= cdf[-1]
        return int(cand[int(cdf.searchsorted(rng.random_sample(), side="right"))])

    def _frame(self, h: np.ndarray, sampling: dict, hist: list[_Window] | None, rng: np.random.RandomState) -> tuple[list[int], bool]:
        empty = np.zeros((1, self.local_heads, 0, self.local_head_dim), dtype=np.float32)
        tok = np.stack([h[0].astype(np.float32), self.text_emb[self.sgs].astype(np.float32)])[None].astype(np.float32)
        feed = {"token_emb": tok, "position_ids": np.array([[0, 1]], np.int64)}
        for i in range(self.local_layers):
            feed[f"past_k_{i}"] = empty
            feed[f"past_v_{i}"] = empty
        out = self.ac.run(None, feed)
        hidden = out[0]
        pk, pv = out[1:1 + self.local_layers], out[1 + self.local_layers:1 + 2 * self.local_layers]
        slot0 = hidden[0, 0]

        def pick(ch: int, vec: np.ndarray) -> int:
            code = self._sample(vec.astype(np.float32) @ self.audio_emb[ch].T, sampling["temperature"], sampling["top_k"], sampling["top_p"],
                                sampling["repetition_penalty"], hist[ch] if hist is not None else None, rng)
            if hist is not None:
                hist[ch].add(code)
            return code

        codes = [pick(0, hidden[0, 1])]
        for ch in range(1, self.n_vq):
            emb = self.audio_emb[ch - 1][codes[-1]].astype(np.float32)
            feed = {"token_emb": emb.reshape(1, 1, self.hidden), "position_ids": np.array([[ch + 1]], np.int64)}
            for i in range(self.local_layers):
                feed[f"past_k_{i}"] = pk[i]
                feed[f"past_v_{i}"] = pv[i]
            out = self.ac.run(None, feed)
            hidden = out[0]
            pk, pv = out[1:1 + self.local_layers], out[1 + self.local_layers:1 + 2 * self.local_layers]
            codes.append(pick(ch, hidden[0, 0]))
        eos = int((slot0.astype(np.float32) @ self.text_emb.T).argmax()) == self.eos_speech
        return codes, eos

    def _generate(self, prompt: np.ndarray, anchor: np.ndarray | None, cap: int, sampling: dict, rng: np.random.RandomState) -> list[np.ndarray]:
        pre = self.pre.run(None, {"inputs_embeds": prompt})
        past_k = [pre[1 + i] for i in range(self.layers)]
        past_v = [pre[1 + self.layers + i] for i in range(self.layers)]
        h = pre[0][:, -1]
        start = prompt.shape[1]
        hist = [_Window(sampling["repetition_window"]) for _ in range(self.n_vq)] if not math.isclose(sampling["repetition_penalty"], 1.0) else None
        frames: list[np.ndarray] = []
        for t in range(cap):
            codes, eos = self._frame(h, sampling, hist, rng)
            frames.append(np.asarray(codes, dtype=np.int64))
            if eos:
                break
            slot = np.full((1, self.n_vq + 1), self.audio_pad, dtype=np.int64)
            slot[0, 0] = self.sgs
            slot[0, 1:] = codes
            feed = {"inputs_embeds": self._embed(slot, anchor), "position_ids": np.array([[start + t]], np.int64)}
            for i in range(self.layers):
                feed[f"past_k_{i}"] = past_k[i]
                feed[f"past_v_{i}"] = past_v[i]
            out = self.dec.run(None, feed)
            h = out[0][:, 0]
            past_k = [out[1 + i] for i in range(self.layers)]
            past_v = [out[1 + self.layers + i] for i in range(self.layers)]
        return frames

    def decode(self, frames: np.ndarray) -> np.ndarray:
        codes = np.asarray(frames, dtype=np.int32)[None]
        out = self.codec.run(None, {"audio_codes": codes, "audio_code_lengths": np.array([codes.shape[1]], dtype=np.int32)})
        return out[0][0].mean(0).astype(np.float32)

    def infer(self, phonemes: str, speaker_emb: np.ndarray, ref_codes: np.ndarray | None, *, rng: np.random.RandomState,
              sampling: dict | None = None, babble_retries: int = BABBLE_RETRIES) -> np.ndarray:
        """Một khúc phoneme -> sóng âm 48 kHz (OnnxV3LiteEngine.infer, frame_cap bật)."""
        sampling = {**DEFAULT_SAMPLING, **(sampling or {})}
        cap = min(MAX_NEW_FRAMES, max_expected_frames(phonemes))
        anchor = self._anchor(speaker_emb)
        prompt = self._embed(self._rows(phonemes, ref_codes), anchor)
        with self._lock:
            frames = self._generate(prompt, anchor, cap, sampling, rng)
            if not frames:
                return np.zeros(0, dtype=np.float32)
            wav = self.decode(np.stack(frames))
            best = babble_suspect(wav, self.SAMPLE_RATE, phonemes, cap, len(frames))
            tries = 0
            while best[0] and tries < babble_retries:
                again = self._generate(prompt, anchor, cap, sampling, rng)
                tries += 1
                if not again:
                    continue
                other = self.decode(np.stack(again))
                judged = babble_suspect(other, self.SAMPLE_RATE, phonemes, cap, len(again))
                if babble_prefer(judged, best):
                    wav, best = other, judged
        return wav


# ---- Nano ----------------------------------------------------------------------------------------------------------------------
class NanoEngine:
    """VieNeu-TTS v3 Nano (flow matching, 24 kHz). `model_dir`: các file của repo VieNeu-TTS-v3-Nano."""

    SAMPLE_RATE = NANO_RATE

    def __init__(self, model_dir: Path | str, *, threads: int = 0, device: str = "cpu", sessions: dict[str, Any] | None = None) -> None:
        model_dir = Path(model_dir)
        self.cfg = json.loads((model_dir / "config.json").read_bytes().decode("utf-8"))
        constants = np.load(model_dir / "constants.npz")
        self.null_spk = constants["null_spk"].astype(np.float32)[None]
        self.null_style = constants["null_style"].astype(np.float32)[None]
        self.vocab: dict[str, int] = self.cfg["vocab"]
        self.bos, self.eos, self.pad = int(self.cfg["bos_id"]), int(self.cfg["eos_id"]), int(self.cfg["pad_id"])
        self.fps = float(self.cfg.get("flow_fps", 24000 / 256 / 6))
        self.emotion_map: dict[str, str] = dict(self.cfg.get("emotion_tags", {}))
        self.device = device
        self._lock = threading.RLock()
        if sessions is not None:
            self.text, self.dur, self.ve, self.dec = sessions["text"], sessions["dur"], sessions["ve"], sessions["dec"]
        else:
            options = _session_options(threads, device)
            self.text = _session(model_dir / "text_encoder.onnx", options, device)
            self.dur = _session(model_dir / "duration_predictor.onnx", options, device)
            self.ve = _session(model_dir / "vector_estimator.onnx", options, device)
            self.dec = _session(model_dir / "codec_decoder.onnx", options, device)
        null_ids = np.array([[self.bos, self.eos]], dtype=np.int64)
        self.null_ctx = self.text.run(None, {"ids": null_ids, "style": self.null_style})[0]
        self.null_mask = null_ids != self.pad

    def encode(self, phonemes: str) -> np.ndarray:
        """Chuỗi phoneme -> mã [1, L]; ký tự ngoài từ điển bị bỏ (như vieneu)."""
        for tag, char in self.emotion_map.items():
            phonemes = phonemes.replace(tag, char)
        ids = [self.bos] + [self.vocab[ch] for ch in phonemes if ch in self.vocab] + [self.eos]
        return np.array([ids], dtype=np.int64)

    def infer(self, phonemes: str, speaker_emb: np.ndarray, style: np.ndarray, *, seed: int | None,
              steps: int = NANO_STEPS, cfg: float = NANO_CFG) -> np.ndarray:
        """Một khúc phoneme -> sóng âm 24 kHz (OnnxV3NanoEngine.infer, sway 0, tốc độ 1)."""
        with self._lock:
            spk = np.asarray(speaker_emb, dtype=np.float32).reshape(1, -1)
            style = np.asarray(style, dtype=np.float32)
            style = style.reshape(1, *style.shape[-2:])
            ids = self.encode(phonemes)
            mask = ids != self.pad
            ctx = self.text.run(None, {"ids": ids, "style": style})[0]
            log_s = float(self.dur.run(None, {"ctx": ctx, "ctx_mask": mask, "spk": spk})[0][0])
            frames = max(NANO_MIN_FRAMES, int(round(min(math.exp(log_s), NANO_MAX_SECONDS) * self.fps)))
            x = np.random.default_rng(seed).standard_normal((1, 144, frames)).astype(np.float32)
            n = max(1, int(steps))
            grid = np.linspace(0.0, 1.0, n + 1, dtype=np.float64)
            grid = grid + 0.0 * (np.cos(np.pi / 2 * grid) - 1 + grid)
            for i in range(n):
                t = np.array([grid[i]], dtype=np.float32)
                v = self.ve.run(None, {"x": x, "t": t, "ctx": ctx, "ctx_mask": mask, "spk": spk, "style": style})[0]
                if cfg > 0:
                    vu = self.ve.run(None, {"x": x, "t": t, "ctx": self.null_ctx, "ctx_mask": self.null_mask, "spk": self.null_spk,
                                            "style": self.null_style})[0]
                    v = vu + float(cfg) * (v - vu)
                x = x + np.float32(grid[i + 1] - grid[i]) * v
            wav = self.dec.run(None, {"x": x})[0][0, 0]
            return trim_and_fade(np.clip(wav, -1.0, 1.0).astype(np.float32), self.SAMPLE_RATE)


def join(chunks: Sequence[np.ndarray], sr: int, pauses: Sequence[float]) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Ghép các khúc với khoảng nghỉ tối thiểu `pauses[i]` giữa khúc i và i+1 (core_utils.join_audio_chunks). Trả (sóng âm, [đầu, cuối)
    của từng khúc theo mẫu)."""
    parts: list[np.ndarray] = []
    spans: list[tuple[int, int]] = []
    at = 0
    for index, chunk in enumerate(chunks):
        if index:
            pad = pause_pad_samples(chunks[index - 1], chunk, sr, pauses[index - 1] if index - 1 < len(pauses) else 0.0)
            if pad > 0:
                parts.append(np.zeros(pad, dtype=np.float32))
                at += pad
        parts.append(np.asarray(chunk, dtype=np.float32))
        spans.append((at, at + len(chunk)))
        at += len(chunk)
    return (np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)), spans
