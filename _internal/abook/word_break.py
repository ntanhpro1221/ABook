"""Measure pauses inside words on the balanced take; never modify TTS input."""
from __future__ import annotations

import gc
import gzip
import json
import math
import re
import string
import time
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ASSETS = Path(__file__).resolve().parent / "assets"
FIELD = "word_break_gate"
VERSION = 1
ALIGNER_MISSING = "word aligner model is unavailable"
# A syllable has voice, so one lying whole inside a silence means CTC misplaced it.
SWALLOWED_SPAN_TOLERANCE_SECONDS = .005
# Somebody else's memory comes back; a shortage must not decide which take the book keeps.
MEASURE_MEMORY_ATTEMPTS = 3
MEASURE_MEMORY_WAIT_SECONDS = 5.


@lru_cache(maxsize=1)
def _tokenizer() -> tuple[Any, ...]:
    # PyVi 0.1.1 MIT CRF, exported to data-only weights. No runtime pickle.
    with gzip.open(ASSETS / "word_break_tokenizer.json.gz", "rt", encoding="utf8") as handle:
        data = json.load(handle)
    labels = data["labels"]
    state: dict[str, np.ndarray] = {}
    for attr, label, value in data["state"]:
        state.setdefault(attr, np.zeros(len(labels)))[labels.index(label)] = value
    transitions = np.zeros((len(labels), len(labels)))
    for left, right, value in data["transitions"]:
        transitions[labels.index(left), labels.index(right)] = value
    return labels, set(data["bi"]), set(data["tri"]), state, transitions


def tokenize(text: str) -> str:
    """Frozen PyVi segmentation, using only deterministic linear-chain inference."""
    text = unicodedata.normalize("NFC", text)
    pattern = r"([A-ZĐ]+\.|Tp\.|Mr\.|Mrs\.|Ms\.|Dr\.|ThS\.|==>|->|\.\.\.|>>|\n|\w+://[^\s]+|[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z0-9-]+|\d+(?:[\.,_]\d+)+|[^\w\s]|\w+)"
    words = re.findall(pattern, text, re.UNICODE)
    if not words:
        return text
    labels, bi, tri, state, transitions = _tokenizer()
    scores = []
    for i, word in enumerate(words):
        features: dict[str, Any] = {"bias": 1., "word.lower()": word.lower(), "word.isupper()": word.isupper(),
                                    "word.istitle()": word.istitle(), "word.isdigit()": word.isdigit()}
        for direction in (-1, 1):
            j = i + direction
            if not 0 <= j < len(words):
                continue
            neighbour = words[j]
            prefix = f"{direction:+d}:"
            features.update({prefix+"word.lower()": neighbour.lower(), prefix+"word.istitle()": neighbour.istitle(),
                             prefix+"word.isupper()": neighbour.isupper(),
                             prefix+"word.bi_gram()": " ".join(words[min(i,j):max(i,j)+1]).lower() in bi})
            k = i + 2 * direction
            if 0 <= k < len(words):
                features[f"{2*direction:+d}:word.tri_gram()"] = " ".join(words[min(i,k):max(i,k)+1]).lower() in tri
        emission = np.zeros(len(labels))
        for key, value in features.items():
            attr = key+":"+value if isinstance(value, str) else key
            if attr in state:
                emission += state[attr] * (1. if isinstance(value, str) else float(value))
        scores.append(emission)
    best = scores[0]
    back = []
    for emission in scores[1:]:
        matrix = best[:, None] + transitions
        previous = matrix.argmax(axis=0)
        back.append(previous)
        best = matrix[previous, np.arange(len(labels))] + emission
    path = [int(best.argmax())]
    for previous in reversed(back):
        path.append(int(previous[path[-1]]))
    path.reverse()
    output = words[0]
    for i in range(1, len(words)):
        join = (labels[path[i]] == "I_W" and words[i] not in string.punctuation and words[i-1] not in string.punctuation
                and not words[i][0].isdigit() and not words[i-1][0].isdigit()
                and not (words[i][0].istitle() and not words[i-1][0].istitle()))
        output += ("_" if join else " ") + words[i]
    return output


def norm(text: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", text.casefold()))


def _has_internal_punctuation(text: str) -> bool:
    core = text.strip()
    while core and unicodedata.category(core[0]).startswith("P"):
        core = core[1:]
    while core and unicodedata.category(core[-1]).startswith("P"):
        core = core[:-1]
    return any(unicodedata.category(c).startswith("P") or c in "\r\n" for c in core)


def plan(source: str, spoken: str, read_unit: Callable[[str], str]) -> tuple[str, list[dict[str, Any]]]:
    from .analysis import is_vietnamese_syllable
    from vieneu_utils.phonemize_text import normalize_to_chunks_v3, _get_normalizer

    reference = norm(re.sub(r"</?en>", "", " ".join(normalize_to_chunks_v3(spoken))))
    words: list[str] = []
    units = []
    for match in re.finditer(r"\S+", source):
        said = str(_get_normalizer().normalize(read_unit(match[0]), punc_norm=False))
        ref = norm(re.sub(r"</?en>", "", said))
        lo = len(words)
        words += ref.split()
        units.append(dict(source=match[0], start=match.start(), end=match.end(), lo=lo, hi=len(words)))
    if " ".join(words) != reference:
        raise ValueError("source-to-spoken token mapping differs from engine normalization")
    groups = []
    covered: set[int] = set()
    cursor = 0
    for word in tokenize(source).split():
        parts = word.split("_")
        found = re.search(r"\s+".join(re.escape(p) for p in parts), source[cursor:], re.I)
        if found is None:
            continue
        start, end = cursor+found.start(), cursor+found.end()
        cursor = end
        ids = [i for i, u in enumerate(units) if u["start"] < end and u["end"] > start]
        if (len(parts) >= 2 and len(ids) == len(parts) and not _has_internal_punctuation(source[start:end])
                and all(is_vietnamese_syllable(units[i]["source"].strip("“”\"'‘’.,!?;:()[]…—–")) for i in ids)
                and not covered.intersection(ids)):
            covered.update(ids)
            groups.append(dict(source=source[start:end], lo=units[ids[0]]["lo"], hi=units[ids[-1]]["hi"]))
    for i, unit in enumerate(units):
        if i not in covered and unit["hi"]-unit["lo"] >= 2 and not _has_internal_punctuation(unit["source"]):
            groups.append(dict(source=unit["source"], lo=unit["lo"], hi=unit["hi"]))
    return reference, sorted(groups, key=lambda g:g["lo"])


def energy_runs(wave: Any, sr: int) -> list[tuple[float, float]]:
    hop, win = round(sr*.005), round(sr*.010)
    squares = np.r_[0., np.cumsum(np.asarray(wave, dtype=float)**2)]
    starts = np.arange(0, max(0, len(wave)-win+1), hop)
    if not len(starts):
        return []
    db = 10*np.log10(np.maximum((squares[starts+win]-squares[starts])/win, 1e-16))
    low = db < max(-60., float(db.max())-45.)
    edges = np.diff(np.r_[False, low, False].astype(int))
    return [(float(starts[a]/sr), float((starts[b-1]+win)/sr))
            for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))]


def span_inside_silence(wave: Any, sr: int, spans: list[Any], boundary: int) -> bool:
    offset, end = spans[0][0], spans[-1][1]
    runs = [(a+offset, b+offset) for a, b in energy_runs(wave[round(offset*sr):round(end*sr)], sr)]
    lo, hi = np.mean(spans[boundary]), np.mean(spans[boundary+1])
    best = max([(a, b) for a, b in runs if lo < (a+b)/2 < hi], key=lambda ab:ab[1]-ab[0], default=None)
    if best is None:
        return False
    return any(best[0]-SWALLOWED_SPAN_TOLERANCE_SECONDS <= span[0] and span[1] <= best[1]+SWALLOWED_SPAN_TOLERANCE_SECONDS
               for span in (spans[boundary], spans[boundary+1]))


def gaps(wave: Any, sr: int, spans: list[Any]) -> list[float]:
    offset, end = spans[0][0], spans[-1][1]
    runs = [(a+offset, b+offset) for a, b in energy_runs(wave[round(offset*sr):round(end*sr)], sr)]
    result = []
    for left, right in zip(spans, spans[1:]):
        lo, hi = np.mean(left), np.mean(right)
        result.append(max([1000*(b-a) for a,b in runs if lo < (a+b)/2 < hi]+[0.]))
    return result


@lru_cache(maxsize=1)
def _aligner(folder: str) -> Any:
    from .webui.word_timing import Aligner
    return Aligner(Path(folder), threads=2)


def measure(output: Path, voice_key: str, source: str, spoken: str,
            read_unit: Callable[[str], str]) -> dict[str, Any]:
    from . import voice_balance
    from .webui import word_timing

    started = time.perf_counter()
    gate = voice_balance.constants_for_key(voice_key).word_break_gate
    result: dict[str, Any] = dict(version=VERSION, voice_key=voice_key, status="off", fired=False, retry_count=0)
    if gate is None:
        return result
    result.update(metric=gate["metric"], threshold=gate["threshold"])
    attempt = 0
    while True:
        attempt += 1
        try:
            _measure_take(result, gate, word_timing, output, source, spoken, read_unit)
            break
        except Exception as exc:  # noqa: BLE001 - the ruler only advises; it must never fail a take
            if attempt < MEASURE_MEMORY_ATTEMPTS and _is_memory_error(exc):
                gc.collect()
                time.sleep(MEASURE_MEMORY_WAIT_SECONDS)
                continue
            result.update(status="inconclusive", reason=str(exc) or type(exc).__name__)
            break
    result["seconds"] = time.perf_counter()-started
    return result


def _is_memory_error(error: Exception) -> bool:
    from .tts import is_transient_tts_memory_error
    return isinstance(error, MemoryError) or is_transient_tts_memory_error(error)


def _measure_take(result: dict[str, Any], gate: dict[str, Any], word_timing: Any, output: Path, source: str,
                  spoken: str, read_unit: Callable[[str], str]) -> None:
    reference, groups = plan(source, spoken, read_unit)
    result["word_count"] = len(groups)
    if not groups:
        result["status"] = "no_groups"
        return
    folder = word_timing.model_dir()
    if folder is None:
        raise ValueError(ALIGNER_MISSING)
    wave, sr = sf.read(output, dtype="float32", always_2d=True)
    wave = wave.mean(axis=1)
    if len(wave)/sr > word_timing.MAX_LINE_SECONDS:
        raise ValueError("audio exceeds alignment length limit")
    divisor = math.gcd(sr, word_timing.SAMPLE_RATE)
    aligned = _aligner(str(folder)).align(resample_poly(wave, word_timing.SAMPLE_RATE//divisor, sr//divisor).astype("float32"), reference)
    if aligned is None or aligned[1] < .7 or any(s is None for s in aligned[0]):
        raise ValueError("low-confidence or incomplete CTC alignment")
    spans, confidence = aligned
    gg = gaps(wave, sr, spans)
    tokens = reference.split()
    evidence = []
    for group in groups:
        for i in range(group["lo"], group["hi"]-1):
            score = gg[i]
            if gate["metric"] != "silence_ms":
                score = closure_score(wave, sr, spans, i, tokens, gate["model"])
            item = dict(source=group["source"], boundary=i, gap_ms=round(gg[i], 6), score=score,
                        flagged=bool(score >= gate["threshold"]))
            if item["flagged"] and span_inside_silence(wave, sr, spans, i):
                item.update(flagged=False, status="inconclusive", reason="aligned syllable inside silence")
            evidence.append(item)
    result.update(status="measured", confidence=float(confidence), boundaries=evidence,
                  fired=any(e["flagged"] for e in evidence), max_gap_ms=max([e["gap_ms"] for e in evidence]+[0.]),
                  flagged_words=len({(g["lo"],g["hi"]) for g in groups if any(e["flagged"] and g["lo"] <= e["boundary"] < g["hi"]-1 for e in evidence)}))


def closure_score(wave: Any, sr: int, spans: list[Any], boundary: int, tokens: list[str], model_name: str) -> float:
    model = _closure_model(model_name)
    features = closure_features(wave, sr, spans, boundary)
    left, right = (_fold(tokens[j]) for j in (boundary,boundary+1))
    coda = re.search(r"(ch|nh|ng|p|t|c|m|n)$", left)
    vowel = re.search("[aeiouy]", right)
    coda_name, vowel_name = (coda[1] if coda else "open"), (vowel[0] if vowel else "?")
    p95 = model["natural_p95"][coda_name+"|"+vowel_name]
    features += [features[0]-p95[0], features[1]-p95[1]]
    features += [float(coda_name == s) for s in ("p","t","c","ch","m","n","ng","nh","open")]
    return predict_closure(features, model)


@lru_cache(maxsize=1)
def _closure_model(name: str) -> dict[str, Any]:
    if name != "word_break_duc_tri.json":
        raise ValueError("unknown closure classifier")
    return json.loads((ASSETS / name).read_text(encoding="utf8"))


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if unicodedata.category(c) != "Mn").replace("đ","d")


def predict_closure(features: list[float], model: dict[str, Any]) -> float:
    score = float(model["baseline"])
    for tree in model["trees"]:
        index = 0
        while not tree[index]["leaf"]:
            node = tree[index]
            index = node["left"] if features[node["feature"]] <= node["threshold"] else node["right"]
        score += tree[index]["value"]
    return 1./(1.+math.exp(-score))


def _spectral(wave: Any, sr: int) -> list[float]:
    if len(wave) < 4:
        return [0.,0.,0.]
    power = np.abs(np.fft.rfft(wave*np.hanning(len(wave))))**2+1e-18
    hz = np.fft.rfftfreq(len(wave),1/sr)
    return [float(np.sum(hz*power)/power.sum()/sr), float(np.exp(np.mean(np.log(power)))/np.mean(power)),
            float(power[hz>3000].sum()/power.sum())]


def closure_features(wave: Any, sr: int, spans: list[Any], boundary: int) -> list[float]:
    offset, end = spans[0][0], spans[-1][1]
    runs = [(a+offset,b+offset) for a,b in energy_runs(wave[round(offset*sr):round(end*sr)],sr)]
    lo, hi = np.mean(spans[boundary]), np.mean(spans[boundary+1])
    best = max([(a,b) for a,b in runs if lo < (a+b)/2 < hi], key=lambda ab:ab[1]-ab[0], default=None)
    if best is None:
        return [0.]*10
    t0,t1 = best
    gap = (t1-t0)*1000
    previous = max([b for a,b in runs if b<=t0]+[offset])
    following = min([a for a,b in runs if a>=t1]+[end])
    active = max(.02,(t0-previous)+(following-t1))
    pre = wave[max(0,round((t0-.04)*sr)):round(t0*sr)]
    post = wave[round(t1*sr):min(len(wave),round((t1+.04)*sr))]
    rms = lambda x: math.sqrt(float(np.mean(x.astype("float64")**2))) if len(x) else 0.
    contrast = float(np.clip(20*math.log10((rms(pre)+1e-8)/(rms(post)+1e-8)),-40,40))
    return [float(gap),float(gap/(active*1000)),float(active*1000),contrast,*_spectral(pre,sr),*_spectral(post,sr)]
