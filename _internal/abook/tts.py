from __future__ import annotations

import gc
import hashlib
import math
import os
import random
import re
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pyworld

from .audio_io import (
    VIENEU_V3_FRAME_SECONDS,
    VOICE_BALANCE_FIELD,
    AudioQualityError,
    SegmentDurationPolicy,
    atomic_write_wav,
    is_short_utterance,
    resample_audio,
    segment_duration_policy,
    vieneu_generation_reached_frame_ceiling,
)
from .database import (
    GENERATION_DELIVERY_CLARITY as DELIVERY_CLARITY,
    GENERATION_DELIVERY_MODES as DELIVERY_MODES,
    GENERATION_DELIVERY_PRIMARY as DELIVERY_PRIMARY,
    PRONUNCIATION_DELIVERY_LOCKED,
    PRONUNCIATION_DELIVERY_SOURCE,
    PRONUNCIATION_DELIVERY_VARIANTS,
    ProjectDB,
    thought_reads_as_narrator,
)
from .io_utils import stable_int
from .models import (
    CONTEXTUAL_ENGLISH_NAME_PRONUNCIATION_SOURCE,
    ENGLISH_NAME_PRONUNCIATION_SOURCE,
    KEEP_ENGLISH_PRONUNCIATION_SOURCE,
)
from .resource_manager import trim_process_working_set
from .text_processing import (
    is_standalone_ha_gasp,
    normalize_vocalizations_for_tts,
    spoken_symbols_to_words,
)
from . import voice_balance
from .readaloud.studio_tn import studio_tn_tagged
from .voice_catalog import (
    FORMANT_RATIO_MAX,
    FORMANT_RATIO_MIN,
    SPEED_FACTOR_MAX,
    SPEED_FACTOR_MIN,
)
from .tts_contract import (
    HA_VOCALIZATION_DELIVERY_PROFILE,
    HA_VOCALIZATION_FINAL_SAMPLES_FIELD,
    HA_VOCALIZATION_MAX_NEW_FRAMES,
    HA_VOCALIZATION_MAX_NEW_FRAMES_FIELD,
    HA_VOCALIZATION_MAX_TEMPERATURE,
    HA_VOCALIZATION_MAX_TOP_P,
    HA_VOCALIZATION_ORIGINAL_SAMPLES_FIELD,
    HA_VOCALIZATION_PADDING_SAMPLES_FIELD,
    HA_VOCALIZATION_PROFILE_FIELD,
    HA_VOCALIZATION_SAMPLE_RATE_FIELD,
    HA_VOCALIZATION_TARGET_SAMPLES_FIELD,
    HA_VOCALIZATION_TEMPERATURE_FIELD,
    HA_VOCALIZATION_TOP_P_FIELD,
)


# Running out of memory is not the same kind of event as a missing module, and treating it
# as one killed runs. The owner reported it directly: opening Unity, Rider or Photoshop
# mid-run made the book fail "for no reason". What actually happened is that another program
# took the memory, VieNeu raised an out-of-memory error, and this list classified that as
# fatal - so the run stopped instead of waiting for the memory to come back.
#
# The pipeline already knows how to wait: _wait_for_foreign_ram idles up to half an hour for
# memory somebody else is holding, on the reasoning that stopping throws away every hour the
# run has already spent while waiting costs nothing. An OOM raised inside the engine simply
# never reached it.
FATAL_TTS_MARKERS = (
    "cuda driver",
    "cublas",
    "cudnn",
    "no module named",
    "thiếu vieneu",
    "thiếu máy đọc",
    "locked vieneu preset",
    "locked zerotts preset",
    "locked supertonic preset",
    "unknown tts engine",
)
# Somebody else's memory pressure, which ends when they end. Release what this process
# holds, wait, and try the attempt again.
TRANSIENT_TTS_MEMORY_MARKERS = (
    "out of memory",
    "not enough memory",
    "defaultcpuallocator",
    "alloc_cpu.cpp",
    "cuda_error_out_of_memory",
)

# Delivery metadata no longer touches sampling, and this is why.
#
# VieNeu's infer() takes text, voice, style and sampling parameters. It has no emotion
# input at all. Emotion used to be looked up in a table of temperatures, so a line marked
# angry and the same line marked surprised shared a temperature and came out as literally
# the same file - verified by hash: angry and surprised, sad and tender, happy and afraid
# each produced byte-identical audio. The label carried no meaning; it selected one of
# eight randomness levels.
#
# That was not merely useless, it was harmful. intensity added 0.015 per step to both
# temperature and top_p, and a Vietnamese listener identified the higher settings as
# sounding broken rather than intense - one take at intensity 1 ran 1.60s against 1.12s
# for the same line, which is degenerate sampling, not emphasis. Neutral, the lowest
# common setting, was repeatedly preferred.
#
# So generation now uses one stable temperature for every segment. 0.74 is what neutral
# already used, which is most of the book and the setting the listener has approved by
# ear. The purposeful caps below it stay: clarity repair, short utterances and
# vocalisations still lower it further, because those lower it for a reason that exists.
#
# The emotion field is still analysed and stored. It costs no extra model call, and an
# engine that can genuinely act on it would need the data already there.
GENERATION_TEMPERATURE = 0.74
GENERATION_TOP_P = 0.92
# Measured, not assumed: this parameter does nothing. The same line generated at
# silence_p 0.05, 0.15, 0.30 and 0.50 - a tenfold range - came back identical in duration
# and in every internal gap. VieNeu accepts the argument and ignores it.
#
# It is left in place because the engine's signature takes it and a future version may
# honour it, but nothing may be built on the belief that it works. Pause length between
# segments is controlled where it can be: at chapter assembly, in expression.py. Pause
# length *inside* a segment is currently not controllable at all.
#
# This is the fourth parameter this project set carefully while it did nothing - after
# emotion, which only chose a sampling temperature; pace, which nudged that temperature;
# and the clarity cap, which sat above the value it was meant to clamp. A number that is
# read and discarded looks exactly like a number that works.
PACE_SILENCE_PROPORTIONS = {"slow": 0.20, "normal": 0.15, "fast": 0.08}
WORLD_FRAME_PERIOD_MS = 5.0
WORLD_F0_FLOOR_HZ = 55.0
WORLD_F0_CEIL_HZ = 600.0
WORLD_MIN_VOICED_FRAMES = 3
# pyworld.harvest trên vài mẫu làm hỏng heap native và GIẾT cả tiến trình (Windows 0xc0000374), không ném lỗi: đo 04-10, 2 mẫu
# sập, 50 mẫu chạy. Không câu nói thật nào ngắn hơn 10 ms; bản ngắn thế để nguyên cho cổng "audio too short" loại.
WORLD_MIN_SECONDS = 0.010
WSOLA_FRAME_SECONDS = 0.040
VOICE_VARIANT_PITCH_FLOOR_HZ = 60.0
VOICE_VARIANT_PITCH_CEILING_HZ = 600.0
VOICE_VARIANT_PEAK_CEILING = 0.98
SHORT_UTTERANCE_MAX_TEMPERATURE = 0.72
SHORT_UTTERANCE_MAX_TOP_P = 0.90
SHORT_UTTERANCE_REPAIR_MAX_FRAMES = 12
MICRO_UTTERANCE_REPAIR_MAX_FRAMES = 6
MICRO_UTTERANCE_MAX_SPEAKABLE_CHARS = 1
GENERATION_CEILING_WARNING = "TTS_GENERATION_CEILING_REACHED"
GENERATION_CEILING_METRIC = "generation_ceiling_hit"
GENERATION_ENDPOINT_ACTIVE_METRIC = "generation_endpoint_active"
GENERATION_FRAME_CAP_FIELD = "generation_frame_cap"
DEFAULT_SEGMENT_ACTIVE_FLOOR_DBFS = -45.0
# Clarity repair regenerates a segment ASR could not confirm, and its whole purpose is
# less sampling variance. The cap used to sit at 0.78, above the old neutral temperature
# of 0.74, so it already did nothing for the 71% of segments that were neutral - and once
# every segment generates at 0.74 it would have done nothing at all. It has to sit below
# the generation temperature to mean anything, so it now does.
CLARITY_MAX_TEMPERATURE = 0.66
CLARITY_MAX_TOP_P = 0.90
LOCKED_ENGLISH_NAME_PRONUNCIATION_SOURCES = frozenset(
    {
        ENGLISH_NAME_PRONUNCIATION_SOURCE,
        CONTEXTUAL_ENGLISH_NAME_PRONUNCIATION_SOURCE,
    }
)


def vietnamized_kept_english(surface: str) -> str:
    """Chữ đem đọc của một mục `keep_english` cho máy không nói được tiếng Anh: từng chữ Anh Việt hoá như "Nghe ngay" làm cho Supertonic
    (`readaloud.names.english_reading`, tức `english_vi.vietnamized_english`); chữ luật không chắc hay âm tiết Việt viết sẵn giữ nguyên."""
    from .readaloud.names import english_reading

    return " ".join(english_reading(word) or word for word in surface.split())


def is_fatal_tts_error(error: BaseException) -> bool:
    """A failure that will still be there after waiting: a missing module, a broken driver.

    Memory pressure is deliberately not in this set. See TRANSIENT_TTS_MEMORY_MARKERS.
    """
    message = str(error).casefold()
    return any(marker in message for marker in FATAL_TTS_MARKERS)


def is_transient_tts_memory_error(error: BaseException) -> bool:
    """A failure that ends when whoever took the memory gives it back."""
    message = str(error).casefold()
    if any(marker in message for marker in FATAL_TTS_MARKERS):
        return False
    return any(marker in message for marker in TRANSIENT_TTS_MEMORY_MARKERS)


def _set_generation_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed % (2**32))
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def _row_value(row: Any, key: str, default: Any) -> Any:
    try:
        value = row[key]
    except (IndexError, KeyError, TypeError):
        return default
    return default if value is None else value


def apply_pitch_variant(
    audio: Any,
    sample_rate: int,
    pitch_semitones: int,
    *,
    formant_ratio: float = 1.0,
    allow_padding: bool = True,
) -> np.ndarray:
    """Scale F0 by semitones and optionally warp the spectral envelope.

    Pitch alone cannot make two characters sound like different people: speaker identity
    lives in the formants, so scaling F0 while holding the envelope fixed only ever
    produces the same voice higher or lower. A listener comparing the same sentence from
    -6 to +6 semitones - F0 from 106 Hz to 206 Hz - heard no change of person at all.

    Warping the envelope along the frequency axis is what changes the perceived speaker:
    below 1 the vocal tract reads larger and the voice deeper, above 1 smaller and
    brighter. The usable range was found by ear; 0.82 already sounds muffled.
    """
    array = np.asarray(audio, dtype=np.float32).reshape(-1)
    steps = int(pitch_semitones)
    ratio = float(formant_ratio)
    if (steps == 0 and abs(ratio - 1.0) <= 1e-6) or array.size < WORLD_MIN_SECONDS * sample_rate:
        return array
    if not FORMANT_RATIO_MIN <= ratio <= FORMANT_RATIO_MAX:
        raise ValueError(
            f"formant ratio {ratio} is outside the audible range "
            f"[{FORMANT_RATIO_MIN}, {FORMANT_RATIO_MAX}]"
        )
    if sample_rate < 8_000:
        raise ValueError(f"WORLD pitch shifting requires at least 8000 Hz, got {sample_rate}")
    waveform = np.asarray(array, dtype=np.float64)
    f0, time_axis = pyworld.harvest(
        waveform,
        sample_rate,
        f0_floor=WORLD_F0_FLOOR_HZ,
        f0_ceil=WORLD_F0_CEIL_HZ,
        frame_period=WORLD_FRAME_PERIOD_MS,
    )
    f0 = pyworld.stonemask(waveform, f0, time_axis, sample_rate)
    voiced = f0 > 0.0
    if int(np.count_nonzero(voiced)) < WORLD_MIN_VOICED_FRAMES:
        raise ValueError("WORLD could not find enough voiced frames for formant-preserving pitch shift")
    spectral_envelope = pyworld.cheaptrick(waveform, f0, time_axis, sample_rate)
    aperiodicity = pyworld.d4c(waveform, f0, time_axis, sample_rate)
    if abs(ratio - 1.0) > 1e-6:
        bins = spectral_envelope.shape[1]
        source_bins = np.arange(bins, dtype=np.float64)
        query_bins = source_bins / ratio
        spectral_envelope = np.stack(
            [
                np.interp(
                    query_bins,
                    source_bins,
                    frame,
                    left=frame[0],
                    right=frame[-1],
                )
                for frame in spectral_envelope
            ]
        )
    shifted_f0 = f0.copy()
    if steps:
        shifted_f0[voiced] *= 2.0 ** (float(steps) / 12.0)
    shifted = pyworld.synthesize(
        shifted_f0,
        spectral_envelope,
        aperiodicity,
        sample_rate,
        frame_period=WORLD_FRAME_PERIOD_MS,
    ).astype(np.float32, copy=False)
    if shifted.size >= array.size:
        return shifted[: array.size]
    if not allow_padding:
        raise ValueError(
            "WORLD pitch shift shortened a strict no-padding waveform"
        )
    return np.pad(shifted, (0, array.size - shifted.size)).astype(np.float32, copy=False)


def apply_speed_change(audio: Any, sample_rate: int, speed: float) -> np.ndarray:
    """Read the same line `speed` times faster, keeping pitch and spectrum.

    WSOLA (waveform-similarity overlap-add): 40 ms Hann frames laid down every 20 ms, each taken from
    the input `speed` times further along, shifted by up to half a frame to the spot whose waveform
    best continues the previous frame. Pitch and timbre are the input's own samples; only the
    spacing changes, so the line comes out exactly `1 / speed` as long.

    "Best continues" is the NORMALISED cross-correlation (divided by the candidate's energy). The raw
    correlation of the first version leaned towards loud stretches instead of matching ones: it cost
    0.16-0.32 UTMOSv2 at every tempo, even x1.025, and raised loudness by 0.4-0.6 dB; normalised, x1.05
    costs nothing measurable and loudness stays within 0.2 dB (docs/VOICE_BALANCE.md). Either way it
    beats the WORLD resynthesis it replaced (0.48-1.03 lost at the balance tempi). The balance table's
    reference loudness is measured after this step. See `voice_balance.tempo` for the factor.
    """
    array = np.asarray(audio, dtype=np.float32).reshape(-1)
    speed = float(speed)
    if abs(speed - 1.0) <= 1e-6 or array.size < WORLD_MIN_SECONDS * sample_rate:
        return array
    if not SPEED_FACTOR_MIN <= speed <= SPEED_FACTOR_MAX:
        raise ValueError(f"speed factor {speed} is outside [{SPEED_FACTOR_MIN}, {SPEED_FACTOR_MAX}]")
    if sample_rate < 8_000:
        raise ValueError(f"speed change requires at least 8000 Hz, got {sample_rate}")
    waveform = np.asarray(array, dtype=np.float64)
    frame = int(WSOLA_FRAME_SECONDS * sample_rate)
    synthesis_hop = frame // 2
    analysis_hop = int(round(synthesis_hop * speed))
    tolerance = frame // 2
    window = 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(frame) / frame)
    frames = int(np.ceil(waveform.size / analysis_hop)) + 1
    padded = np.concatenate(
        [np.zeros(tolerance), waveform, np.zeros(frames * analysis_hop + frame + 2 * tolerance + synthesis_hop - waveform.size)]
    )
    out = np.zeros(frames * synthesis_hop + frame)
    weight = np.zeros_like(out)
    natural: np.ndarray | None = None
    for index in range(frames):
        start = index * analysis_hop
        region = padded[start:start + frame + 2 * tolerance]
        if natural is None:
            shift = tolerance
        else:
            match = np.correlate(region, natural, mode="valid")[: 2 * tolerance + 1]
            energy = np.convolve(region * region, np.ones(frame), mode="valid")[: 2 * tolerance + 1]
            shift = int(np.argmax(match / (np.sqrt(energy) + 1e-9)))
        out[index * synthesis_hop:index * synthesis_hop + frame] += window * region[shift:shift + frame]
        weight[index * synthesis_hop:index * synthesis_hop + frame] += window
        natural = padded[start + shift + synthesis_hop:start + shift + synthesis_hop + frame]
    faster = (out / np.maximum(weight, 1e-8))[: int(round(waveform.size / speed))]
    peak = float(np.max(np.abs(waveform))) or 1.0
    faster_peak = float(np.max(np.abs(faster))) or 1.0
    return np.asarray(faster * min(1.0, peak / faster_peak), dtype=np.float32)


def apply_voice_variant(
    audio: Any,
    sample_rate: int,
    pitch_semitones: int,
    formant_ratio: float,
) -> np.ndarray:
    """Apply a preset's reading register and a character's formant, independently.

    These are two different jobs and they use two different engines, each the one that
    was judged better for that job by ear:

    - Register is an F0 change. WORLD scales F0 while holding the spectral envelope, which
      keeps the result a configuration a real vocal tract can produce, and the listener
      preferred it. Its analysis-resynthesis round trip measured -0.015 MOS.
    - Identity is a formant change. Praat resamples to move the formants and restores
      pitch with PSOLA, never estimating or resynthesising a spectrum. A PARCOR
      area-function reshape was clearly worst by ear, and WORLD's envelope warp was
      indistinguishable from Praat, so Praat wins on not rebuilding the spectrum at all.

    Doing both in a single Praat call would make the register change PSOLA-based too,
    which is not what was approved for it.
    """
    array = np.asarray(audio, dtype=np.float32).reshape(-1)
    steps = int(pitch_semitones)
    ratio = float(formant_ratio)
    if array.size == 0:
        return array
    if steps:
        array = apply_pitch_variant(array, int(sample_rate), steps)
    if abs(ratio - 1.0) <= 1e-6:
        return np.asarray(array, dtype=np.float32).reshape(-1)
    if not FORMANT_RATIO_MIN <= ratio <= FORMANT_RATIO_MAX:
        raise ValueError(
            f"formant ratio {ratio} is outside the audible range "
            f"[{FORMANT_RATIO_MIN}, {FORMANT_RATIO_MAX}]"
        )
    return _praat_formant_shift(array, int(sample_rate), ratio)


def praat_pitch_window(
    audio: "np.ndarray",
    sample_rate: int,
    floor_hz: float,
    ceiling_hz: float,
) -> tuple[float, float]:
    """Narrow the pitch search to the range this recording actually uses.

    Praat's pitch tracker is given a floor and a ceiling, and a window far wider than the
    voice invites the classic halving error: a frame is scored as an octave below where it
    belongs, and every PSOLA operation downstream then places its pulses wrong. It shows up
    on low-pitched words, because those sit closest to the floor - which is exactly where a
    listener located it, on "mẹ" in one voice and on "những từ trầm trong câu" in another.
    A fixed 60-600 Hz window is ten times wider than a female preset needs.

    The range is measured from the audio rather than configured, so it follows whatever the
    register and age shifts have already done to the voice. Praat's own guidance is a floor
    somewhat below the lowest real pitch and a ceiling somewhat above the highest; the
    margins here are that, and they fall back to the wide window when a clip is too short
    or too unvoiced to measure.
    """
    import parselmouth

    try:
        pitch = parselmouth.Sound(
            np.asarray(audio, dtype=np.float64).reshape(-1),
            sampling_frequency=int(sample_rate),
        ).to_pitch(pitch_floor=floor_hz, pitch_ceiling=ceiling_hz)
        values = np.asarray(pitch.selected_array["frequency"])
        voiced = values[values > 0.0]
    except Exception:  # noqa: BLE001
        return floor_hz, ceiling_hz
    if voiced.size < 20:
        return floor_hz, ceiling_hz
    low = float(np.percentile(voiced, 2)) * 0.75
    high = float(np.percentile(voiced, 98)) * 1.35
    return max(floor_hz, low), min(ceiling_hz, max(high, low * 2.0))


def _praat_formant_shift(
    array: np.ndarray,
    sample_rate: int,
    formant_ratio: float,
) -> np.ndarray:
    import parselmouth
    from parselmouth.praat import call

    source = np.asarray(array, dtype=np.float32).reshape(-1)
    sound = parselmouth.Sound(
        source.astype(np.float64),
        sampling_frequency=int(sample_rate),
    )
    floor_hz, ceiling_hz = praat_pitch_window(
        source, int(sample_rate), VOICE_VARIANT_PITCH_FLOOR_HZ, VOICE_VARIANT_PITCH_CEILING_HZ
    )
    shifted = call(
        sound,
        "Change gender",
        floor_hz,
        ceiling_hz,
        float(formant_ratio),
        0.0,  # keep the pitch median exactly as the register step left it
        1.0,
        1.0,
    )
    result = np.asarray(shifted.values, dtype=np.float32).reshape(-1)
    if result.size == 0:
        raise ValueError("Praat formant shift produced no samples")
    if not np.isfinite(result).all():
        raise ValueError("Praat formant shift produced non-finite samples")
    # PSOLA can overshoot the input peak. The chapter is mastered afterwards, so a small
    # uniform trim costs nothing and keeps the delivery WAV inside PCM range.
    peak = float(np.max(np.abs(result)))
    if peak > VOICE_VARIANT_PEAK_CEILING:
        result = result * (VOICE_VARIANT_PEAK_CEILING / peak)
    if result.size >= source.size:
        return result[: source.size].astype(np.float32, copy=False)
    return np.pad(result, (0, source.size - result.size)).astype(np.float32, copy=False)


def short_utterance_repair_frame_cap(text: str) -> int | None:
    if not is_short_utterance(text):
        return None
    speakable_chars = sum(char.isalnum() for char in text)
    return (
        MICRO_UTTERANCE_REPAIR_MAX_FRAMES
        if speakable_chars <= MICRO_UTTERANCE_MAX_SPEAKABLE_CHARS
        else SHORT_UTTERANCE_REPAIR_MAX_FRAMES
    )


def _max_new_frames(row: Any, settings: dict[str, Any] | None) -> int:
    policy_frames = segment_duration_policy(
        str(_row_value(row, "text", "")),
        settings,
        row,
    ).generation_max_frames
    persisted_cap = int(_row_value(row, GENERATION_FRAME_CAP_FIELD, 0) or 0)
    return min(policy_frames, persisted_cap) if persisted_cap > 0 else policy_frames


def vieneu_sampling_for_segment(
    row: Any,
    settings: dict[str, Any] | None = None,
    *,
    repair_short_utterance: bool = False,
    delivery_mode: str = DELIVERY_PRIMARY,
    vocalization_delivery_profile: str | None = None,
) -> dict[str, float | int]:
    normalized_delivery = str(delivery_mode).strip().casefold()
    if normalized_delivery not in DELIVERY_MODES:
        raise ValueError(f"Unsupported TTS delivery mode: {delivery_mode}")
    normalized_vocalization_profile = (
        str(vocalization_delivery_profile).strip().casefold()
        if vocalization_delivery_profile is not None
        else None
    )
    if normalized_vocalization_profile not in {
        None,
        HA_VOCALIZATION_DELIVERY_PROFILE,
    }:
        raise ValueError(
            f"Unsupported TTS vocalization delivery profile: {vocalization_delivery_profile}"
        )
    text = str(_row_value(row, "text", ""))
    pace = str(_row_value(row, "pace", "normal"))
    temperature = GENERATION_TEMPERATURE
    top_p = GENERATION_TOP_P
    if normalized_delivery == DELIVERY_CLARITY:
        temperature = min(temperature, CLARITY_MAX_TEMPERATURE)
        top_p = min(top_p, CLARITY_MAX_TOP_P)
    max_new_frames = _max_new_frames(row, settings)
    if is_short_utterance(text):
        temperature = min(temperature, SHORT_UTTERANCE_MAX_TEMPERATURE)
        top_p = min(top_p, SHORT_UTTERANCE_MAX_TOP_P)
        warning_codes = str(_row_value(row, "warning_code", "")).split("|")
        if repair_short_utterance and GENERATION_CEILING_WARNING in warning_codes:
            repair_frames = (
                HA_VOCALIZATION_MAX_NEW_FRAMES
                if normalized_vocalization_profile
                == HA_VOCALIZATION_DELIVERY_PROFILE
                else short_utterance_repair_frame_cap(text)
            )
            if repair_frames is not None:
                max_new_frames = min(max_new_frames, repair_frames)
    if normalized_vocalization_profile == HA_VOCALIZATION_DELIVERY_PROFILE:
        temperature = min(temperature, HA_VOCALIZATION_MAX_TEMPERATURE)
        top_p = min(top_p, HA_VOCALIZATION_MAX_TOP_P)
        max_new_frames = min(max_new_frames, HA_VOCALIZATION_MAX_NEW_FRAMES)
    return {
        "temperature": temperature,
        "top_k": 25,
        "top_p": top_p,
        "repetition_penalty": 1.2,
        "silence_p": PACE_SILENCE_PROPORTIONS.get(pace, PACE_SILENCE_PROPORTIONS["normal"]),
        "max_new_frames": max_new_frames,
    }


class EngineAdapter:
    """Một máy đọc của Studio: nạp / bỏ, tần số mẫu của chính nó, danh sách giọng, đọc MỘT câu.

    Điều phối viên (`TTSCoordinator`) giữ mỗi máy một adapter theo `voice_profiles.engine`, nạp LƯỜI khi cuốn có
    giọng của máy ấy, rồi đổi bản thu về tần số dự án trước mọi bước sau (cao độ, tempo, độ to). Hạt giống theo
    câu như VieNeu (`generation_seed`): cùng câu cùng giọng ra cùng audio.

    `native_tempo`: máy tự đọc nhanh/chậm theo tham số của nó (`engine_speed` của bảng cân bằng) thay vì kéo giãn
    bản thu bằng WSOLA - `generate_one` nhận `speed` và điều phối viên không kéo giãn nữa.

    `MAX_CHUNK_CHARS`: câu dài hơn thì đọc thành nhiều lần gọi (`chunks`) rồi nối (`join_chunks`); None = một lần cho cả câu.

    `speaks_english`: máy đọc được chữ Anh để nguyên (docs/READING_FOREIGN_NAMES.md mục 4 và 8, đo 04-10). False thì tên / từ Anh mà bảng cách
    đọc để nguyên (nguồn `keep_english`) được Việt hoá cho đoạn của máy này (`TTSCoordinator.spoken_text_with_anchors`).
    """

    name = ""
    label = ""
    native_tempo = False
    speaks_english = True
    MAX_CHUNK_CHARS: int | None = None

    def __init__(self, settings: dict[str, Any], log: Callable[[str], None]) -> None:
        self.settings = settings
        self.log = log
        self.tts: Any = None
        self.sample_rate = int(settings["tts"]["sample_rate"])
        self.voices: list[str] = []

    def load(self) -> None:
        raise NotImplementedError

    def unload(self) -> None:
        had_model = self.tts is not None
        self.tts = None
        self.voices = []
        if not had_model:
            return
        self.release_inference_cache()
        trim_process_working_set()

    @staticmethod
    def release_inference_cache() -> None:
        gc.collect()

    def voice_for_profile(self, profile: Any) -> str:
        self.load()
        if str(profile["engine"]) != self.name:
            raise AudioQualityError(
                f"Unknown TTS engine pairing: {self.label} cannot read a {profile['engine']!r} profile ({profile['voice_key']})"
            )
        preset = str(profile["preset_name"] or "").strip()
        if not preset or preset not in self.voices:
            raise AudioQualityError(
                f"Locked {self.label} preset {preset!r} is unavailable; refusing to change voice silently"
            )
        return preset

    def generate_one(
        self,
        row: Any,
        profile: Any,
        seed: int,
        *,
        sampling: dict[str, float | int] | None = None,
        speed: float | None = None,
    ) -> np.ndarray:
        """Đọc `row["text"]` bằng giọng của `profile`: float32 một kênh ở `self.sample_rate`."""
        raise NotImplementedError

    @classmethod
    def chunk_plan(cls, text: str) -> list[tuple[str, str]]:
        """Các lần gọi của một câu, mỗi lần kèm dấu câu thô ở cuối mảnh (`.`, `…`, `?`, `!`, `,`... hay "" khi cắt giữa câu ở từ) để
        `join_chunks` chọn khoảng lặng. Nguyên câu nếu không quá `MAX_CHUNK_CHARS`; không thì cắt theo `plan_chunks`. Chữ đem đọc vẫn là
        chữ Studio đã chuẩn bị, không qua các phép đọc riêng của "Nghe ngay"."""
        if cls.MAX_CHUNK_CHARS is None or len(text) <= cls.MAX_CHUNK_CHARS:
            return [(text, _end_mark(text.split()[-1]) if text.strip() else "")]
        return plan_chunks(text, cls.MAX_CHUNK_CHARS) or [(text, "")]

    @classmethod
    def chunks(cls, text: str) -> list[str]:
        """Chữ của các lần gọi trong `chunk_plan`."""
        return [chunk for chunk, _end in cls.chunk_plan(text)]


# ---- chia câu dài thành mảnh, nối mảnh -------------------------------------------------------------------------------------------
# Đo 04-10 trên ZeroTTS (docs/VOICE_BALANCE.md, join_report: 5 giọng x 13 đoạn 300-450 ký tự, UTMOSv2 + ASR): chia theo ranh giới câu
# và nối "cắt lặng mép + fade + lặng theo dấu" cho UTMOS không kém cách cũ (+0,022 ± 0,026), nhưng lặng tại chỗ nối 0,25 s thay vì
# 0,36 s - gần lặng ZeroTTS tự sinh khi đọc một lần (trung vị sau dấu chấm 0,27 s, phẩy 0,20 s, hỏi 0,31 s, than 0,28 s, giữa từ 0,03 s).
CHUNK_MIN_CHARS = 30
CHUNK_END_MARKS = ".!?…,;:"
CHUNK_TRIM_DB = -45.0  # dưới mức này (khung 5 ms) là lặng ở mép trong của mảnh
CHUNK_TRIM_FRAME_SECONDS = 0.005
CHUNK_TRIM_KEEP_SECONDS = 0.010  # chừa lại mỗi mép, không cắt vào âm đầu / cuối
CHUNK_FADE_SECONDS = 0.015  # raised-cosine ở mép trong
CHUNK_JOIN_GAP_SECONDS = {".": 0.27, "…": 0.27, "?": 0.31, "!": 0.28, ",": 0.20}  # TỔNG lặng giữa hai tiếng, theo dấu cuối mảnh trước
CHUNK_JOIN_GAP_DEFAULT_SECONDS = 0.20  # dấu khác (`;`, `:`) hay cắt giữa câu ở từ: như dấu phẩy
CHUNK_PEAK_CEILING = 0.99


def _end_mark(token: str) -> str:
    from .readaloud.vieneu import CLOSERS

    core = token.rstrip(CLOSERS)
    return core[-1] if core and core[-1] in CHUNK_END_MARKS else ""


def _even_split(atoms: list[tuple[str, str]], limit: int) -> list[tuple[str, str]]:
    """Gộp các nguyên tử (chữ, dấu cuối) liền nhau thành SỐ MẢNH ÍT NHẤT, mỗi mảnh không quá `limit` ký tự, cỡ mảnh đều nhất (tối thiểu
    tổng bình phương lệch khỏi cỡ trung bình) - quy hoạch động."""
    count = len(atoms)
    total = sum(len(text) for text, _mark in atoms) + count - 1
    prefix = [0]
    for text, _mark in atoms:
        prefix.append(prefix[-1] + len(text) + 1)

    def span(i: int, j: int) -> int:  # độ dài ký tự của atoms[i:j] nối bằng khoảng trắng
        return prefix[j] - prefix[i] - 1

    inf = float("inf")
    for pieces in range(-(-total // limit), count + 1):
        target = total / pieces
        best = [[inf] * (count + 1) for _ in range(pieces + 1)]
        came = [[0] * (count + 1) for _ in range(pieces + 1)]
        best[0][0] = 0.0
        for m in range(1, pieces + 1):
            for j in range(m, count + 1):
                for i in range(m - 1, j):
                    size = span(i, j)
                    if size > limit or best[m - 1][i] == inf:
                        continue
                    cost = best[m - 1][i] + (size - target) ** 2
                    if cost < best[m][j]:
                        best[m][j], came[m][j] = cost, i
        if best[pieces][count] < inf:
            cuts, j = [], count
            for m in range(pieces, 0, -1):
                i = came[m][j]
                cuts.append((i, j))
                j = i
            return [(" ".join(text for text, _mark in atoms[i:j]), atoms[j - 1][1]) for i, j in reversed(cuts)]
    raise AssertionError("mỗi nguyên tử vừa trần nên chia thành từng nguyên tử luôn được")


def plan_chunks(text: str, limit: int) -> list[tuple[str, str]]:
    """Cắt `text` (dài hơn `limit`) thành các mảnh (chữ, dấu cuối). Cắt ở ranh giới câu, gộp NGUYÊN câu liền kề tới `limit`; câu dài hơn
    `limit` đứng riêng, cắt ở dấu phẩy thành số mảnh ít nhất và đều (không cắt được ở dấu phẩy thì ở từ; một từ dài hơn `limit` thì cắt
    cứng), không gộp mẩu của nó với câu kề; mảnh dưới `CHUNK_MIN_CHARS` gộp vào mảnh kề nếu còn vừa `limit`."""
    from .readaloud.vieneu import PHRASE_END, SENTENCE_END, _groups
    from .webui.word_timing import tokens

    toks = tokens(text)

    def words(first: int, last: int) -> str:
        return " ".join(toks[first:last + 1])

    pieces: list[tuple[str, str, bool]] = []  # (chữ, dấu cuối, nguyên câu)
    for first, last in _groups(toks, 0, len(toks) - 1, SENTENCE_END):
        if len(words(first, last)) <= limit:
            pieces.append((words(first, last), _end_mark(toks[last]), True))
            continue
        atoms: list[tuple[str, str]] = []
        for a, b in _groups(toks, first, last, PHRASE_END):
            if len(words(a, b)) <= limit:
                atoms.append((words(a, b), _end_mark(toks[b])))
                continue
            for index in range(a, b + 1):  # khúc giữa hai dấu phẩy cũng quá trần: cắt ở từ
                slices = [toks[index][start:start + limit] for start in range(0, len(toks[index]), limit)]
                atoms += [(piece, "") for piece in slices[:-1]] + [(slices[-1], _end_mark(toks[index]))]
        pieces += [(chunk, mark, False) for chunk, mark in _even_split(atoms, limit)]
    merged: list[tuple[str, str, bool]] = []
    for chunk, mark, whole in pieces:
        if whole and merged and merged[-1][2] and len(merged[-1][0]) + 1 + len(chunk) <= limit:
            merged[-1] = (f"{merged[-1][0]} {chunk}", mark, True)
        else:
            merged.append((chunk, mark, whole))
    out = [(chunk, mark) for chunk, mark, _whole in merged]
    index = 0
    while index < len(out):  # mảnh mồ côi gộp vào mảnh kề (trước, rồi sau) nếu còn vừa trần
        if len(out[index][0]) < CHUNK_MIN_CHARS and len(out) > 1:
            if index > 0 and len(out[index - 1][0]) + 1 + len(out[index][0]) <= limit:
                out[index - 1:index + 1] = [(f"{out[index - 1][0]} {out[index][0]}", out[index][1])]
                continue
            if index + 1 < len(out) and len(out[index][0]) + 1 + len(out[index + 1][0]) <= limit:
                out[index:index + 2] = [(f"{out[index][0]} {out[index + 1][0]}", out[index + 1][1])]
                continue
        index += 1
    return out


def chunk_gap_seconds(end_mark: str) -> float:
    """Tổng lặng giữa hai tiếng sau mảnh kết thúc bằng `end_mark` (xem CHUNK_JOIN_GAP_SECONDS)."""
    return CHUNK_JOIN_GAP_SECONDS.get(end_mark, CHUNK_JOIN_GAP_DEFAULT_SECONDS)


def _trim_silence(wave: np.ndarray, sample_rate: int, *, head: bool, tail: bool) -> np.ndarray:
    """Cắt lặng dưới `CHUNK_TRIM_DB` ở đầu / cuối (khung `CHUNK_TRIM_FRAME_SECONDS`), chừa `CHUNK_TRIM_KEEP_SECONDS` mỗi mép."""
    frame = max(1, int(sample_rate * CHUNK_TRIM_FRAME_SECONDS))
    count = wave.size // frame
    if count == 0:
        return wave
    rms = np.sqrt((wave[:count * frame].astype(np.float64).reshape(count, frame) ** 2).mean(axis=1))
    loud = np.flatnonzero(20.0 * np.log10(rms + 1e-9) > CHUNK_TRIM_DB)
    if loud.size == 0:
        return wave
    keep = int(sample_rate * CHUNK_TRIM_KEEP_SECONDS)
    start = max(0, int(loud[0]) * frame - keep) if head else 0
    stop = min(wave.size, (int(loud[-1]) + 1) * frame + keep) if tail else wave.size
    return wave[start:stop]


def _fade_ramp(sample_rate: int, limit: int) -> np.ndarray:
    count = min(int(sample_rate * CHUNK_FADE_SECONDS), limit)
    return (0.5 - 0.5 * np.cos(np.pi * np.arange(count) / count)).astype(np.float32) if count > 1 else np.zeros(0, dtype=np.float32)


def _fade_edges(wave: np.ndarray, sample_rate: int, *, head: bool, tail: bool) -> np.ndarray:
    ramp = _fade_ramp(sample_rate, wave.size // 2)
    if not ramp.size:
        return wave
    wave = wave.copy()
    if head:
        wave[:ramp.size] *= ramp
    if tail:
        wave[-ramp.size:] *= ramp[::-1]
    return wave


def join_chunks(waves: list[np.ndarray], sample_rate: int, ends: list[str] | None = None) -> np.ndarray:
    """Nối bản thu các lần gọi của một câu, theo thứ tự. `ends[i]` = dấu cuối của mảnh i (`chunk_plan`; thiếu thì như dấu phẩy).
    Mép TRONG mỗi mảnh cắt lặng (ZeroTTS tự mang ~0,1 s lặng cuối mảnh) rồi fade raised-cosine; giữa hai mảnh chèn lặng theo dấu cuối mảnh
    trước, `chunk_gap_seconds` TRỪ phần mép đã chừa (2 x `CHUNK_TRIM_KEEP_SECONDS`) - tổng không hơn phần chừa thì chồng crossfade. Đầu mảnh
    đầu và cuối mảnh cuối giữ nguyên. Không cân độ to từng mảnh (đo: không cải thiện); chặn đỉnh `CHUNK_PEAK_CEILING` sau khi nối."""
    parts = [np.asarray(wave, dtype=np.float32).reshape(-1) for wave in waves]
    if len(parts) <= 1:
        return parts[0] if parts else np.zeros(0, dtype=np.float32)
    last = len(parts) - 1
    parts = [_fade_edges(_trim_silence(part, sample_rate, head=i > 0, tail=i < last), sample_rate, head=i > 0, tail=i < last)
             for i, part in enumerate(parts)]
    kept = 2 * CHUNK_TRIM_KEEP_SECONDS
    out = parts[0]
    for index, part in enumerate(parts[1:]):
        gap = chunk_gap_seconds(ends[index] if ends is not None and index < len(ends) else ",")
        if gap > kept:
            out = np.concatenate([out, np.zeros(round((gap - kept) * sample_rate), dtype=np.float32), part])
        else:  # lặng không đủ chừa mép: chồng hai mép
            ramp = _fade_ramp(sample_rate, min(out.size, part.size))
            count = ramp.size
            out = np.concatenate([out[:out.size - count], out[out.size - count:] * ramp[::-1] + part[:count] * ramp, part[count:]])
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > CHUNK_PEAK_CEILING:
        out = out * np.float32(CHUNK_PEAK_CEILING / peak)
    return out.astype(np.float32, copy=False)


_VIENEU_FINAL_MARK = re.compile(r"[?!]+\s*$")


def keep_vieneu_final_mark() -> None:
    """VieNeu ép dấu cuối của khúc dưới 5 từ về "." (`punc_norm` của sea-g2p): "Thật sao?" thành "Thật sao." và mất giọng hỏi, giọng cảm
    (đo 10-10: F0 cuối câu hỏi ngắn +1,0 st khi giữ dấu, CER không tệ hơn). Khúc kết bằng "?" / "!" giữ dấu ấy; khúc thiếu dấu vẫn được thêm
    ".". Đặt thay hai hàm của `vieneu_utils.phonemize_text` (chốt dấu ở mức chữ, rồi ở mức phoneme); gọi nhiều lần cũng chỉ đặt một lần.
    Cùng luật với `readaloud.vieneu_engine.phonemize` (Nghe ngay); chép lại ở đây vì file này bị khoá, còn vieneu_engine thì không."""
    import vieneu_utils.phonemize_text as phonemize_text

    if getattr(phonemize_text, "_abook_keeps_final_mark", False):
        return
    original_punc_norm, original_phonemize = phonemize_text.punc_norm, phonemize_text._phonemize_cached

    def punc_norm(text: str) -> str:
        out = original_punc_norm(text)
        found = _VIENEU_FINAL_MARK.search(text)
        return out[:-1] + found.group(0)[0] if found and out.endswith(".") else out

    def phonemize(text: str, punc_norm: bool = True) -> str:
        out = original_phonemize(text, punc_norm)
        if punc_norm and out.endswith(".") and ("?" in text or "!" in text):
            written = original_phonemize(text, False).rstrip()  # dấu cuối thật của khúc, chưa bị ép
            if written.endswith(("?", "!")):
                out = out[:-1] + written[-1]
        return out

    phonemize_text.punc_norm, phonemize_text._phonemize_cached = punc_norm, phonemize
    phonemize_text._abook_keeps_final_mark = True


class VieNeuEngine(EngineAdapter):
    name = "vieneu"
    label = "VieNeu"

    def load(self) -> None:
        if self.tts is not None:
            return
        try:
            from vieneu import Vieneu
        except ImportError as exc:
            raise RuntimeError("Thiếu VieNeu; hãy chạy ABook") from exc
        keep_vieneu_final_mark()
        self.log("Nạp VieNeu-TTS.")
        self.tts = Vieneu(max_batch_size=max(1, int(self.settings["tts"]["batch_size"])))
        raw = list(self.tts.list_preset_voices())
        self.voices = []
        for item in raw:
            if isinstance(item, (tuple, list)) and item:
                voice_id = str((item[1] if len(item) > 1 else item[0]) or item[0]).strip()
            else:
                voice_id = str(item).strip()
            if voice_id and voice_id not in self.voices:
                self.voices.append(voice_id)
        if not self.voices:
            raise RuntimeError("VieNeu không cung cấp preset voice nào")
        self.sample_rate = int(getattr(self.tts, "sample_rate", self.sample_rate))

    @staticmethod
    def release_inference_cache() -> None:
        """Release temporary Python/CUDA allocations after a completed inference unit."""
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def generate_one(
        self,
        row: Any,
        profile: Any,
        seed: int,
        *,
        sampling: dict[str, float | int] | None = None,
        speed: float | None = None,
    ) -> np.ndarray:
        self.load()
        _set_generation_seed(seed)
        voice = self.voice_for_profile(profile)
        style = "doc_truyen" if str(row["speaker"]) == "NARRATOR" else "tu_nhien"
        effective_sampling = (
            sampling
            if sampling is not None
            else vieneu_sampling_for_segment(row, self.settings)
        )
        try:
            return np.asarray(
                self.tts.infer(
                    str(row["text"]),
                    voice=voice,
                    style=style,
                    **effective_sampling,
                ),
                dtype=np.float32,
            ).reshape(-1)
        except Exception as exc:  # noqa: BLE001
            raise AudioQualityError(str(exc)) from exc


# Đo 04-10 (ZeroTTS, câu 4 giây, máy dev đang bận ~50 % CPU): 4 luồng RTF 1,2-1,9; 8 luồng 1,4-2,0; 16 luồng 3,6-3,8 -
# thêm luồng quá vài cái là giành nhau. Bản thu không đổi theo số luồng (cùng hạt giống ra cùng byte ở 4, 8, 16).
ENGINE_THREADS_MAX = 4


def _engine_threads() -> int:
    """Số luồng CPU cho máy đọc ONNX: như worker của bể thu (`ABOOK_WORKER_THREADS`), không thì tối đa `ENGINE_THREADS_MAX`."""
    configured = int(os.environ.get("ABOOK_WORKER_THREADS", "0") or 0)
    return configured if configured > 0 else max(1, min(ENGINE_THREADS_MAX, (os.cpu_count() or 2) // 2))


class ZeroTTSEngine(EngineAdapter):
    """ZeroTTS (ZeroWeight AI, ONNX, CPU) từ mô-đun tải thêm `webui/zerotts_module.py`.

    Lấy mẫu nằm trong đồ thị ONNX, nhưng số ngẫu nhiên do runtime bốc từ `np.random` - đặt hạt giống numpy là cùng câu
    cùng giọng ra cùng audio. Tham số lấy mẫu giữ mặc định của gói (bộ đo cân bằng giọng dùng đúng mặc định ấy);
    trần khung sinh lấy từ ngân sách thời lượng của câu (`max_new_frames` của `vieneu_sampling_for_segment`, tính bằng
    khung VieNeu), đổi sang giây rồi sang khung 12,5 Hz của máy này.

    RAM đỉnh tăng theo bình phương độ dài một lần gọi (docs/VOICE_BALANCE.md: 200 ký tự 2,0 GB, 400 ký tự 4,5 GB, 800 ký tự
    14,5 GB và ASR sai 50 %), nên mỗi lần gọi tối đa 170 ký tự (~9 giây tiếng); câu dài hơn đọc thành nhiều lần gọi với cùng
    chuỗi hạt giống rồi nối (`chunk_plan`, `join_chunks`).

    Tiến trình sống lâu phình RAM dù mỗi lần gọi ngắn (đo 04-10: ~2,4 GB sau ~70 lần gọi mảnh <= 170 ký tự), nên phiên ONNX được nạp
    lại định kỳ (`recycle_if_due`): bản thu không đổi một byte, vì hạt giống đặt SAU khi nạp lại.
    """

    name = "zerotts"
    label = "ZeroTTS"
    MAX_CHUNK_CHARS = 170
    # Tiến trình sống lâu phình RAM (phiên ONNX giữ lại bộ nhớ đã cấp): nạp lại phiên sau từng này lần gọi `synthesize`. Đo 04-10 (300 lần
    # gọi, 300 chuỗi 100-170 ký tự khác nhau, 5 giọng, 4 luồng): không nạp lại RSS 2,9 -> 3,1 GB và còn đi lên; mỗi 25 lần RSS 2,0-2,6 GB
    # phẳng (đỉnh 2,58 GB), mỗi 75 lần đỉnh 2,74 GB. Nạp lại ~7 giây (tới ~18 giây khi máy bận), ~2-5 % thời gian đọc.
    RECYCLE_AFTER_CALLS: int | None = 25

    def __init__(self, settings: dict[str, Any], log: Callable[[str], None]) -> None:
        super().__init__(settings, log)
        self._normalize: Callable[[str], str] = str
        self._calls = 0

    def recycle_if_due(self) -> bool:
        """Nạp lại phiên ONNX khi đã gọi `RECYCLE_AFTER_CALLS` lần: bỏ máy cũ (`unload`: thu rác + trả trang về Windows) rồi `load` lại.
        Gọi giữa hai câu, TRƯỚC khi đặt hạt giống (lúc nạp, warmup có thể bốc số ngẫu nhiên của numpy)."""
        if self.tts is None or not self.RECYCLE_AFTER_CALLS or self._calls < self.RECYCLE_AFTER_CALLS:
            return False
        self.unload()
        self.load()
        return True

    def unload(self) -> None:
        self._calls = 0
        super().unload()

    def load(self) -> None:
        if self.tts is not None:
            return
        from .webui import zerotts_module

        found = zerotts_module.locate()
        if found is None:
            raise RuntimeError("Thiếu máy đọc ZeroTTS: tải giọng ZeroTTS ở Đổi giọng của Studio rồi chạy tiếp")
        engine_class = zerotts_module.import_engine(found)
        from zerotts.text_norm import normalize_vi_text

        self.log("Nạp ZeroTTS.")
        self.tts = engine_class(found.model, intra_op_num_threads=_engine_threads(), warmup=True)
        self._normalize = normalize_vi_text
        self.voices = list(self.tts.list_voices())
        self.sample_rate = int(self.tts.sample_rate)

    def generate_one(
        self,
        row: Any,
        profile: Any,
        seed: int,
        *,
        sampling: dict[str, float | int] | None = None,
        speed: float | None = None,
    ) -> np.ndarray:
        self.load()
        self.recycle_if_due()
        voice = self.voice_for_profile(profile)
        _set_generation_seed(seed)
        frames = int((sampling or {}).get("max_new_frames") or _max_new_frames(row, self.settings))
        max_frames = max(1, math.ceil(frames * VIENEU_V3_FRAME_SECONDS * float(self.tts.frame_rate)))
        plan = self.chunk_plan(str(row["text"]))
        try:
            waves = []
            for chunk, _end in plan:
                waves.append(np.asarray(self.tts.synthesize(self._normalize(chunk), voice=voice, max_frames=max_frames), dtype=np.float32).reshape(-1))
                self._calls += 1
        except Exception as exc:  # noqa: BLE001
            raise AudioQualityError(str(exc)) from exc
        return waves[0] if len(waves) == 1 else join_chunks(waves, self.sample_rate, [end for _chunk, end in plan])


# Câu ngắn ở tốc độ của cả giọng bị nuốt (53-79 % câu ngắn, CER ASR 53 %): tốc độ tăng dần theo số tiếng, gặp tốc độ của giọng
# thì dừng - `min(engine_speed, 1,28 + 0,06·max(0, n − 2))`, n = số tiếng (docs/VOICE_BALANCE.md "Câu ngắn": 1,7 % nuốt, CER 9,7 %).
SUPERTONIC_SHORT_SPEED = 1.28
SUPERTONIC_SPEED_PER_SYLLABLE = 0.06


def supertonic_speed(text: str, engine_speed: float) -> float:
    """Tham số `speed` cho một lần gọi Supertonic: tốc độ của giọng, trừ câu ngắn (xem SUPERTONIC_SHORT_SPEED)."""
    syllables = len(re.findall(r"\w+", text))
    return min(float(engine_speed), SUPERTONIC_SHORT_SPEED + SUPERTONIC_SPEED_PER_SYLLABLE * max(0, syllables - 2))


class SupertonicEngine(EngineAdapter):
    """Supertonic 3 (ONNX, CPU) từ mô-đun "Giọng Supertonic" của Nghe ngay (một bản tải cho cả hai nơi), đọc qua đúng engine
    của Nghe ngay (`readaloud/supertonic.py`). Tốc độ là tham số `speed` của máy: bảng cân bằng ghi `engine_speed` của từng
    giọng (chỉnh lặp tới mốc) và `r` = 1, nên điều phối viên không kéo giãn bản thu; câu ngắn đọc chậm hơn (`supertonic_speed`).
    Mỗi lần gọi tối đa 300 ký tự như hãng (`readaloud.supertonic.MAX_CHARS`).
    """

    name = "supertonic"
    label = "Supertonic"
    native_tempo = True
    speaks_english = True  # đo 2040 bản thu (04-10): chữ Anh để nguyên không kém; ASR "Kate", "Michael" để nguyên qua, dạng Việt hoá trượt
    MAX_CHUNK_CHARS = 300

    def load(self) -> None:
        if self.tts is not None:
            return
        from .readaloud import supertonic
        from .webui import supertonic_module

        found = supertonic_module.locate()
        if found is None:
            raise RuntimeError("Thiếu máy đọc Supertonic: tải giọng Supertonic ở Đổi giọng của Studio rồi chạy tiếp")
        self.log("Nạp Supertonic.")
        self.tts = supertonic.SupertonicEngine(found.folder, _engine_threads())
        self.voices = list(supertonic.NAMES)
        self.sample_rate = int(self.tts.SAMPLE_RATE)

    def generate_one(
        self,
        row: Any,
        profile: Any,
        seed: int,
        *,
        sampling: dict[str, float | int] | None = None,
        speed: float | None = None,
    ) -> np.ndarray:
        from .readaloud import supertonic

        self.load()
        voice = self.voice_for_profile(profile)
        if speed is None:
            raise AudioQualityError(f"Unknown TTS engine speed for {profile['voice_key']}: Supertonic needs engine_speed")
        rng = np.random.RandomState(seed % (2**32))
        try:
            waves = []
            plan = self.chunk_plan(str(row["text"]))
            for chunk, _end in plan:
                text = supertonic.normalize_pieces([chunk])
                waves.append(np.asarray(self.tts.infer(text, voice, rng, speed=supertonic_speed(text, speed)), dtype=np.float32).reshape(-1))
        except Exception as exc:  # noqa: BLE001
            raise AudioQualityError(str(exc)) from exc
        return waves[0] if len(waves) == 1 else join_chunks(waves, self.sample_rate, [end for _chunk, end in plan])


ENGINE_ADAPTERS: dict[str, type[EngineAdapter]] = {
    VieNeuEngine.name: VieNeuEngine,
    ZeroTTSEngine.name: ZeroTTSEngine,
    SupertonicEngine.name: SupertonicEngine,
}
# `keep_engine` của dây chuyền (`_resource_gate`, `unload_idle_models`): đang thu thì giữ MỌI máy đọc đã nạp - một cuốn
# có thể dùng giọng của nhiều máy trong cùng một chương.
KEEP_TTS_ENGINES = "tts"


class TTSCoordinator:
    def __init__(self, settings: dict[str, Any], db: ProjectDB, log: Callable[[str], None]) -> None:
        self.settings = settings
        self.db = db
        self.log = log
        # Mỗi máy đọc một adapter, tạo khi cuốn cần tới giọng của máy ấy (`engine`). VieNeu luôn có: người kể là VieNeu.
        self.engines: dict[str, EngineAdapter] = {VieNeuEngine.name: VieNeuEngine(settings, log)}
        # Tần số của mọi WAV câu trong dự án: bản thu của máy nào cũng được đổi về đây trước cao độ / tempo / độ to.
        self.sample_rate = int(settings["tts"]["sample_rate"])
        self._pronunciation_pattern: re.Pattern[str] | None = None
        self._pronunciation_map: dict[str, str] = {}
        self._pronunciation_metadata: dict[str, Any] = {}
        self._exact_pronunciation_pattern: re.Pattern[str] | None = None
        self._exact_pronunciation_map: dict[str, str] = {}
        self._exact_pronunciation_metadata: dict[str, Any] = {}
        self._has_kept_english = False
        self._book_origin: tuple[str | None] | None = None  # gốc cuốn ("ja" / "ko" / None), đoán một lần từ chữ các chương

    @property
    def vieneu(self) -> EngineAdapter:
        return self.engines[VieNeuEngine.name]

    @vieneu.setter
    def vieneu(self, engine: EngineAdapter) -> None:
        # Bản xem thử (webui/reading_preview.py) đưa lại VieNeu đã nạp từ lần trước.
        self.engines[VieNeuEngine.name] = engine

    def engine(self, name: str) -> EngineAdapter:
        """Adapter của máy đọc `name` (chưa nạp model - `load` khi đọc câu đầu)."""
        adapter = self.engines.get(name)
        if adapter is None:
            adapter_class = ENGINE_ADAPTERS.get(name)
            if adapter_class is None:
                raise AudioQualityError(f"Unknown TTS engine {name!r}; refusing to change voice silently")
            adapter = self.engines[name] = adapter_class(self.settings, self.log)
        return adapter

    def engine_for_profile(self, profile: Any) -> EngineAdapter:
        return self.engine(str(_row_value(profile, "engine", VieNeuEngine.name)))

    def load_engines_for_book(self) -> None:
        """Nạp mọi máy đọc mà các giọng của cuốn cần (worker của bể thu nạp trước khi nhận câu)."""
        for name in sorted({str(_row_value(profile, "engine", VieNeuEngine.name)) for profile in self.db.list_voice_profiles()}
                           | {VieNeuEngine.name}):
            self.engine(name).load()

    def unload_all(self) -> None:
        for adapter in self.engines.values():
            adapter.unload()

    def release_inference_cache(self) -> None:
        # gc.collect của VieNeu dọn cả rác Python của máy khác; máy ONNX không giữ bộ nhớ đệm nào khác.
        self.vieneu.release_inference_cache()

    def unload_idle_models(self, keep_engine: str | None = None) -> None:
        if keep_engine not in (KEEP_TTS_ENGINES, VieNeuEngine.name):
            self.unload_all()

    def generation_seed(self, row: Any, seed_salt: str = "") -> int:
        profile = self._voice_profile_for_row(row)
        # Người nghe yêu cầu thu lại câu (segments.listener_retakes): hạt giống mới cho mọi lượt thu của câu, không thì bản
        # thu lại y hệt bản bị chê. 0 (mọi câu chưa ai yêu cầu) giữ ĐÚNG chuỗi hạt giống cũ - sách cũ thu như trước.
        retakes = int(_row_value(row, "listener_retakes", 0) or 0)
        suffix = f"::retake{retakes}" if retakes > 0 else ""
        return stable_int(f"segment::{row['stable_id']}::{profile['voice_key']}::{seed_salt}{suffix}")

    def _voice_profile_for_row(self, row: Any) -> Any:
        if self._thought_reads_as_narrator(row):
            return self.db.voice_profile_by_key("narrator")
        return self.db.voice_profile(int(row["voice_profile_id"]))

    @staticmethod
    def _thought_reads_as_narrator(row: Any) -> bool:
        return thought_reads_as_narrator(
            _row_value(row, "kind", "narration"),
            _row_value(row, "speaker", ""),
            _row_value(row, "voice_profile_id", None),
        )

    def locked_voice_provenance(self, row: Any) -> dict[str, int]:
        profile = self._voice_profile_for_row(row)
        return {
            "voice_profile_id": int(profile["id"]),
            "pitch_semitones": int(profile["pitch_semitones"] or 0),
        }

    def forget_pronunciations(self) -> None:
        """Đọc lại bảng cách đọc ở lần dựng chuỗi nói kế tiếp.

        Bảng được nạp một lần rồi giữ cho cả tiến trình. Người nghe sửa một cách đọc giữa hai chương
        (`pipeline._apply_listener_overrides`) thì bản giữ ấy đã cũ - mà nó dựng cả chuỗi giao cho giọng
        lẫn chuỗi ASR phải nghe thấy, nên giữ nó là thu tên mới rồi chấm theo tên cũ."""
        self._pronunciation_pattern = None

    def _load_pronunciations(self) -> None:
        if self._pronunciation_pattern is None:
            minimum = float(self.settings["analysis"].get("low_confidence_threshold", 0.58))
            pronunciations = self.db.list_pronunciations(minimum)
            exact_pronunciations = [
                item
                for item in pronunciations
                if str(item["source"]) == CONTEXTUAL_ENGLISH_NAME_PRONUNCIATION_SOURCE
            ]
            pronunciations = [
                item
                for item in pronunciations
                if str(item["source"]) != CONTEXTUAL_ENGLISH_NAME_PRONUNCIATION_SOURCE
            ]
            self._pronunciation_map = {
                " ".join(str(item["surface"]).casefold().split()): str(item["spoken_form"])
                for item in pronunciations
            }
            self._pronunciation_metadata = {
                " ".join(str(item["surface"]).casefold().split()): item
                for item in pronunciations
            }
            self._has_kept_english = any(
                str(item["source"]) == KEEP_ENGLISH_PRONUNCIATION_SOURCE for item in pronunciations
            )
            surfaces = [str(item["surface"]) for item in pronunciations]
            self._pronunciation_pattern = (
                re.compile(
                    r"(?<!\w)(?:" + "|".join(re.escape(value) for value in surfaces) + r")(?!\w)",
                    re.IGNORECASE,
                )
                if surfaces
                else re.compile(r"(?!x)x")
            )
            self._exact_pronunciation_map = {
                str(item["surface"]): str(item["spoken_form"])
                for item in exact_pronunciations
            }
            self._exact_pronunciation_metadata = {
                str(item["surface"]): item for item in exact_pronunciations
            }
            exact_surfaces = [str(item["surface"]) for item in exact_pronunciations]
            self._exact_pronunciation_pattern = (
                re.compile(r"(?<!\w)(?:" + "|".join(re.escape(value) for value in exact_surfaces) + r")(?!\w)")
                if exact_surfaces
                else re.compile(r"(?!x)x")
            )

    @staticmethod
    def _source_span(
        origins: list[tuple[int, int]],
        start: int,
        end: int,
    ) -> tuple[int, int]:
        matched_origins = origins[start:end]
        if not matched_origins:
            return start, end
        return min(origin[0] for origin in matched_origins), max(
            origin[1] for origin in matched_origins
        )

    def _substitute_pronunciations(
        self,
        text: str,
        origins: list[tuple[int, int]],
        anchor_tags: list[frozenset[int]],
        pattern: re.Pattern[str],
        pronunciation_map: dict[str, str],
        metadata_map: dict[str, Any],
        *,
        case_sensitive: bool,
        source_text: str,
        anchors: list[dict[str, Any]],
        pronunciation_delivery_variant: str,
        speaks_english: bool,
    ) -> tuple[str, list[tuple[int, int]], list[frozenset[int]]]:
        output_parts: list[str] = []
        output_origins: list[tuple[int, int]] = []
        output_anchor_tags: list[frozenset[int]] = []
        cursor = 0
        for match in pattern.finditer(text):
            output_parts.append(text[cursor : match.start()])
            output_origins.extend(origins[cursor : match.start()])
            output_anchor_tags.extend(anchor_tags[cursor : match.start()])
            matched_text = match.group(0)
            key = (
                matched_text
                if case_sensitive
                else " ".join(matched_text.casefold().split())
            )
            canonical_replacement = pronunciation_map.get(key, matched_text)
            metadata = metadata_map.get(key)
            if (
                not speaks_english
                and metadata is not None
                and str(_row_value(metadata, "source", "")) == KEEP_ENGLISH_PRONUNCIATION_SOURCE
            ):
                canonical_replacement = vietnamized_kept_english(str(metadata["surface"]))
            locked_english_pronunciation = bool(
                metadata is not None
                and int(_row_value(metadata, "locked", 0)) == 1
                and str(_row_value(metadata, "source", ""))
                in LOCKED_ENGLISH_NAME_PRONUNCIATION_SOURCES
            )
            replacement = (
                matched_text
                if pronunciation_delivery_variant == PRONUNCIATION_DELIVERY_SOURCE
                and locked_english_pronunciation
                else canonical_replacement
            )
            source_start, source_end = self._source_span(
                origins,
                match.start(),
                match.end(),
            )
            replacement_anchor_tags = set().union(*anchor_tags[match.start() : match.end()])
            if (
                not replacement_anchor_tags
                and locked_english_pronunciation
                # Both delivery variants must anchor the same occurrences, because the
                # candidate allocator refuses a source-spelling take whose anchors do not
                # match the locked ones - and rightly so, since that comparison is what
                # stops one name being read two ways.
                #
                # This used to anchor every occurrence in the source variant as well, which
                # broke that comparison for any entry whose spoken form IS its spelling: the
                # locked variant anchored nothing there and the source variant anchored one,
                # so the two drifted by construction. On a book of English game terms that
                # was 18 of 43 entries and killed 17 of 79 segments, deterministically.
                #
                # Nothing is lost by dropping it. When the canonical form equals the
                # spelling, both variants read the text identically, so an anchor saying
                # "read as spelled here" records no decision - there was none to make.
                and canonical_replacement != matched_text
            ):
                anchor_index = len(anchors)
                replacement_anchor_tags.add(anchor_index)
                anchors.append(
                    {
                        "pronunciation_id": int(metadata["id"]),
                        "surface": str(metadata["surface"]),
                        "normalized_surface": str(metadata["normalized_surface"]),
                        "matched_surface": source_text[source_start:source_end],
                        "spoken_form": replacement,
                        "canonical_spoken_form": str(metadata["spoken_form"]),
                        "pronunciation_delivery_variant": pronunciation_delivery_variant,
                        "source": str(metadata["source"]),
                        "source_start": source_start,
                        "source_end": source_end,
                        "_anchor_index": anchor_index,
                        "_execution_order": len(anchors),
                    }
                )
            output_parts.append(replacement)
            output_origins.extend([(source_start, source_end)] * len(replacement))
            output_anchor_tags.extend(
                [frozenset(replacement_anchor_tags)] * len(replacement)
            )
            cursor = match.end()
        output_parts.append(text[cursor:])
        output_origins.extend(origins[cursor:])
        output_anchor_tags.extend(anchor_tags[cursor:])
        return "".join(output_parts), output_origins, output_anchor_tags

    @staticmethod
    def _private_use_markers(text: str, count: int) -> list[str]:
        occupied = set(text)
        markers: list[str] = []
        for start, end in ((0xF0000, 0xFFFFE), (0x100000, 0x10FFFE)):
            for codepoint in range(start, end):
                marker = chr(codepoint)
                if marker in occupied:
                    continue
                markers.append(marker)
                occupied.add(marker)
                if len(markers) == count:
                    return markers
        raise RuntimeError("Unable to allocate pronunciation anchor markers")

    def _normalize_with_anchor_spans(
        self,
        text: str,
        anchor_tags: list[frozenset[int]],
        anchors: list[dict[str, Any]],
    ) -> str:
        normalized_text = normalize_vocalizations_for_tts(text)
        if not anchors:
            return normalized_text
        positions: dict[int, list[int]] = {
            int(anchor["_anchor_index"]): [] for anchor in anchors
        }
        for position, tags in enumerate(anchor_tags):
            for anchor_index in tags:
                positions[anchor_index].append(position)
        markers = self._private_use_markers(text, len(anchors) * 2)
        marker_events: dict[str, tuple[dict[str, Any], str]] = {}
        boundary_markers: dict[int, list[str]] = {}
        for anchor, start_marker, end_marker in zip(
            anchors,
            markers[::2],
            markers[1::2],
            strict=True,
        ):
            anchor_positions = positions[int(anchor["_anchor_index"])]
            if not anchor_positions:
                raise RuntimeError("Applied pronunciation anchor has no spoken text span")
            start = min(anchor_positions)
            end = max(anchor_positions) + 1
            boundary_markers.setdefault(start, []).append(start_marker)
            boundary_markers.setdefault(end, []).append(end_marker)
            marker_events[start_marker] = (anchor, "start")
            marker_events[end_marker] = (anchor, "end")
        marked_parts: list[str] = []
        for boundary in range(len(text) + 1):
            marked_parts.extend(boundary_markers.get(boundary, ()))
            if boundary < len(text):
                marked_parts.append(text[boundary])
        normalized_marked_text = normalize_vocalizations_for_tts("".join(marked_parts))
        visible_characters: list[str] = []
        for character in normalized_marked_text:
            marker_event = marker_events.get(character)
            if marker_event is None:
                visible_characters.append(character)
                continue
            anchor, boundary = marker_event
            anchor[f"spoken_{boundary}"] = len(visible_characters)
        if "".join(visible_characters) != normalized_text:
            raise RuntimeError("Pronunciation anchor markers changed spoken-text normalization")
        for anchor in anchors:
            if "spoken_start" not in anchor or "spoken_end" not in anchor:
                raise RuntimeError("Pronunciation anchor marker was lost during normalization")
        return normalized_text

    def _origin_of_book(self) -> str | None:
        """Gốc của cuốn cho bước đọc chữ theo chữ (`studio_tn`), như Nghe ngay; chữ dự án không đổi giữa các lần gọi nên đoán một lần."""
        if self._book_origin is None:
            from .studio_names import book_origin_for_project

            self._book_origin = (book_origin_for_project(self.db),)
        return self._book_origin[0]

    def _row_speaks_english(self, row: Any) -> bool:
        """Máy đọc của đoạn có đọc được chữ Anh để nguyên không (`EngineAdapter.speaks_english`). Chỉ hỏi giọng của đoạn khi bảng cách đọc
        có mục `keep_english` - không có thì câu trả lời không đổi gì."""
        if not self._has_kept_english:
            return True
        return bool(self.engine_for_profile(self._voice_profile_for_row(row)).speaks_english)

    def spoken_text_with_anchors(
        self,
        row: Any,
        *,
        pronunciation_delivery_variant: str = PRONUNCIATION_DELIVERY_LOCKED,
    ) -> tuple[str, list[dict[str, Any]]]:
        normalized_variant = str(pronunciation_delivery_variant).strip().casefold()
        if normalized_variant not in PRONUNCIATION_DELIVERY_VARIANTS:
            raise ValueError("Unsupported pronunciation delivery variant")
        self._load_pronunciations()
        # Before anything else, so every downstream consumer sees the same string: the
        # voice, the transcript comparison that has to match what the voice was given, and
        # the pace metric that budgets a silence per punctuation group. Characters the voice
        # cannot say used to pass straight through - the owner heard "Thường (Common) (C) »
        # Hiếm" come out as one unbroken run, because a guillemet is not a pause and neither
        # is a bracket the voice ignores.
        #
        # Anchors are computed from this text, and their source offsets are only ever
        # compared against other anchors derived the same way (pipeline.py builds an
        # identity tuple from them), never used to slice row["text"]. Normalising here keeps
        # those offsets internally consistent. row["text"] itself is untouched - the book's
        # text is not what changes, only what is handed to the voice. A line the listener
        # re-worded in the Studio (`listener_text`: a typo, an odd spelling) is read in
        # their words; every consumer of this function sees the same string.
        source_text = spoken_symbols_to_words(str(_row_value(row, "listener_text", "") or row["text"]))
        origins = [(index, index + 1) for index in range(len(source_text))]
        anchor_tags = [frozenset() for _character in source_text]
        anchors: list[dict[str, Any]] = []
        # Đoạn của máy không nói được tiếng Anh nhận dạng Việt hoá của tên Anh để nguyên; khâu chấm ASR so với đúng chữ này.
        speaks_english = self._row_speaks_english(row)
        text, origins, anchor_tags = self._substitute_pronunciations(
            source_text,
            origins,
            anchor_tags,
            self._exact_pronunciation_pattern,
            self._exact_pronunciation_map,
            self._exact_pronunciation_metadata,
            case_sensitive=True,
            source_text=source_text,
            anchors=anchors,
            pronunciation_delivery_variant=normalized_variant,
            speaks_english=speaks_english,
        )
        text, _origins, anchor_tags = self._substitute_pronunciations(
            text,
            origins,
            anchor_tags,
            self._pronunciation_pattern,
            self._pronunciation_map,
            self._pronunciation_metadata,
            case_sensitive=False,
            source_text=source_text,
            anchors=anchors,
            pronunciation_delivery_variant=normalized_variant,
            speaks_english=speaks_english,
        )
        # Cùng bộ chuẩn hoá theo chữ với Nghe ngay (số La Mã, viết tắt, thán từ kéo dài, kính ngữ...), TRƯỚC `normalize_vocalizations_for_tts` (nó
        # đổi "III" thành "I. I" và "Aaaa" thành "A... a" trước khi luật theo chữ kịp nhận ra); chữ của bảng phát âm giữ nguyên.
        text, anchor_tags = studio_tn_tagged(text, anchor_tags, self._origin_of_book(), speaks_english)
        text = self._normalize_with_anchor_spans(text, anchor_tags, anchors)
        anchors.sort(
            key=lambda item: (
                int(item["source_start"]),
                int(item["source_end"]),
                int(item["_execution_order"]),
            )
        )
        occurrences: dict[int, int] = {}
        for order, anchor in enumerate(anchors, start=1):
            pronunciation_id = int(anchor["pronunciation_id"])
            occurrence = occurrences.get(pronunciation_id, 0) + 1
            occurrences[pronunciation_id] = occurrence
            anchor["occurrence"] = occurrence
            anchor["order"] = order
            del anchor["_anchor_index"]
            del anchor["_execution_order"]
        return text, anchors

    def spoken_text(
        self,
        row: Any,
        *,
        pronunciation_delivery_variant: str = PRONUNCIATION_DELIVERY_LOCKED,
    ) -> str:
        text, _anchors = self.spoken_text_with_anchors(
            row,
            pronunciation_delivery_variant=pronunciation_delivery_variant,
        )
        return text

    def _spoken_row(
        self,
        row: Any,
        *,
        pronunciation_delivery_variant: str = PRONUNCIATION_DELIVERY_LOCKED,
    ) -> dict[str, Any]:
        result = dict(row)
        result["text"] = self.spoken_text(
            row,
            pronunciation_delivery_variant=pronunciation_delivery_variant,
        )
        if self._thought_reads_as_narrator(row):
            narrator_profile = self.db.voice_profile_by_key("narrator")
            result["speaker"] = "NARRATOR"
            result["voice_profile_id"] = int(narrator_profile["id"])
        return result

    def prepare_voice_presets(self) -> None:
        self.vieneu.load()
        profiles = self.db.list_voice_profiles()
        for profile in profiles:
            self.engine_for_profile(profile).voice_for_profile(profile)
        engines = sorted({adapter.label for adapter in self.engines.values() if adapter.tts is not None})
        self.log(f"Đã xác minh {len(profiles)} voice profile đã khóa ({', '.join(engines)}).")

    def synthesize_atomic(
        self,
        row: Any,
        output: Path,
        seed_salt: str = "",
        *,
        repair_short_utterance: bool = False,
        delivery_mode: str = DELIVERY_PRIMARY,
        pronunciation_delivery_variant: str = PRONUNCIATION_DELIVERY_LOCKED,
    ) -> tuple[str, dict[str, Any], int]:
        try:
            profile = self._voice_profile_for_row(row)
            seed = self.generation_seed(row, seed_salt)
            normalized_pronunciation_variant = str(
                pronunciation_delivery_variant
            ).strip().casefold()
            if normalized_pronunciation_variant not in PRONUNCIATION_DELIVERY_VARIANTS:
                raise ValueError("Unsupported pronunciation delivery variant")
            spoken_row = self._spoken_row(
                row,
                pronunciation_delivery_variant=normalized_pronunciation_variant,
            )
            # Trước ngân sách sinh và trước độ to: cả hai cần biết giọng nào (bản ghi trong bảng
            # cân bằng giọng). Giọng chưa đo thì LỖI ở đây, không thu bằng 1,0.
            voice_constants = voice_balance.constants_for_profile(profile)
            spoken_row[VOICE_BALANCE_FIELD] = voice_constants.key
            vocalization_delivery_profile = (
                HA_VOCALIZATION_DELIVERY_PROFILE
                if is_standalone_ha_gasp(str(row["text"]))
                else None
            )
            sampling = vieneu_sampling_for_segment(
                spoken_row,
                self.settings,
                repair_short_utterance=repair_short_utterance,
                delivery_mode=delivery_mode,
                vocalization_delivery_profile=vocalization_delivery_profile,
            )
            engine = self.engine_for_profile(profile)
            # Máy tự đọc theo tốc độ (`native_tempo`) nhận tham số tốc độ của nó (`engine_speed` của bảng, nhân `x`) ở đây; bản
            # ghi của nó có r = 1 nên WSOLA bên dưới không kéo thêm.
            speed_factor = voice_balance.tempo(voice_constants)
            audio = engine.generate_one(
                spoken_row,
                profile,
                seed,
                sampling=sampling,
                **({"speed": voice_balance.engine_speed(voice_constants)} if engine.native_tempo else {}),
            )
            audio = resample_audio(audio, engine.sample_rate, self.sample_rate)
            raw_vocalization_samples = (
                int(np.asarray(audio).reshape(-1).size)
                if vocalization_delivery_profile
                == HA_VOCALIZATION_DELIVERY_PROFILE
                else None
            )
            duration_policy = segment_duration_policy(
                str(spoken_row["text"]),
                self.settings,
                spoken_row,
            )
            effective_generation_policy = SegmentDurationPolicy(
                generation_max_frames=int(sampling["max_new_frames"]),
                validation_max_seconds=duration_policy.validation_max_seconds,
            )
            generation_ceiling_hit = (
                engine.name == VieNeuEngine.name
                and is_short_utterance(str(spoken_row["text"]))
                and vieneu_generation_reached_frame_ceiling(audio, effective_generation_policy)
            )
            pitch_steps = int(_row_value(profile, "pitch_semitones", 0))
            pitch_variant_skipped = False
            try:
                if (
                    vocalization_delivery_profile
                    == HA_VOCALIZATION_DELIVERY_PROFILE
                ):
                    pitched_audio = apply_pitch_variant(
                        audio,
                        self.sample_rate,
                        pitch_steps,
                        allow_padding=False,
                    )
                    if (
                        int(np.asarray(pitched_audio).reshape(-1).size)
                        != raw_vocalization_samples
                    ):
                        raise ValueError(
                            "Ha vocalization pitch variant changed the raw sample count"
                        )
                else:
                    pitched_audio = apply_pitch_variant(
                        audio,
                        self.sample_rate,
                        pitch_steps,
                    )
                audio = pitched_audio
            except Exception as exc:  # noqa: BLE001
                # Pitch is optional voice diversification. The original waveform still contains
                # every spoken word, so preserve it instead of failing or retrying the whole TTS.
                pitch_variant_skipped = True
                self.log(
                    f"Bỏ biến thể cao độ {pitch_steps:+d} cho segment {row['stable_id']} "
                    f"vì xử lý pitch lỗi: {exc}"
                )
            # Tempo = x * r_v (bảng cân bằng giọng), sau cao độ vì hàm cao độ giữ nguyên độ dài, và
            # trước độ to (WSOLA chồng cửa sổ nâng độ to vài phần mười dB, nên o_v đo sau bước này). Bỏ qua tiếng
            # cười "ha": đường ấy có bất biến số mẫu thô.
            speed_change_skipped = False
            if (
                abs(speed_factor - 1.0) > 1e-6
                and not engine.native_tempo
                and vocalization_delivery_profile != HA_VOCALIZATION_DELIVERY_PROFILE
            ):
                try:
                    audio = apply_speed_change(audio, self.sample_rate, speed_factor)
                except Exception as exc:  # noqa: BLE001
                    speed_change_skipped = True
                    self.log(
                        f"Bỏ hệ số tốc độ x{speed_factor:.2f} cho segment {row['stable_id']} "
                        f"vì xử lý lỗi: {exc}"
                    )
            vocalization_provenance: dict[str, Any] = {}
            if vocalization_delivery_profile == HA_VOCALIZATION_DELIVERY_PROFILE:
                audio_array = np.asarray(audio, dtype=np.float32).reshape(-1)
                audio = audio_array
                sample_rate = int(self.sample_rate)
                original_samples = int(raw_vocalization_samples or 0)
                final_samples = int(audio_array.size)
                if original_samples <= 0 or final_samples != original_samples:
                    raise AudioQualityError(
                        "Ha vocalization must preserve its raw no-padding sample count"
                    )
                vocalization_provenance.update(
                    {
                        HA_VOCALIZATION_PROFILE_FIELD: HA_VOCALIZATION_DELIVERY_PROFILE,
                        HA_VOCALIZATION_TEMPERATURE_FIELD: float(
                            sampling["temperature"]
                        ),
                        HA_VOCALIZATION_TOP_P_FIELD: float(sampling["top_p"]),
                        HA_VOCALIZATION_MAX_NEW_FRAMES_FIELD: int(
                            sampling["max_new_frames"]
                        ),
                        HA_VOCALIZATION_SAMPLE_RATE_FIELD: sample_rate,
                        HA_VOCALIZATION_ORIGINAL_SAMPLES_FIELD: original_samples,
                        HA_VOCALIZATION_TARGET_SAMPLES_FIELD: original_samples,
                        HA_VOCALIZATION_PADDING_SAMPLES_FIELD: 0,
                        HA_VOCALIZATION_FINAL_SAMPLES_FIELD: final_samples,
                    }
                )
            checksum, metrics = atomic_write_wav(
                output,
                audio,
                self.sample_rate,
                str(spoken_row["text"]),
                self.settings,
                segment=spoken_row,
            )
            metrics["pitch_variant_skipped"] = float(pitch_variant_skipped)
            metrics["pitch_variant_mixed"] = 0.0
            metrics["tts_delivery_mode"] = str(delivery_mode).strip().casefold()
            metrics["pronunciation_delivery_variant"] = normalized_pronunciation_variant
            metrics["spoken_text_sha256"] = hashlib.sha256(
                str(spoken_row["text"]).encode("utf-8")
            ).hexdigest()
            metrics["voice_profile_id"] = int(profile["id"])
            metrics["pitch_semitones"] = pitch_steps
            metrics["effective_pitch_semitones"] = (
                0 if pitch_variant_skipped else pitch_steps
            )
            metrics["speed_factor"] = float(speed_factor)
            metrics["effective_speed_factor"] = 1.0 if speed_change_skipped else float(speed_factor)
            metrics.update(vocalization_provenance)
            if generation_ceiling_hit or (
                vocalization_delivery_profile == HA_VOCALIZATION_DELIVERY_PROFILE
            ):
                # This compares the trailing RMS of the levelled WAV, so it must use
                # the endpoint floor that tracks the loudness anchors, not the active
                # floor, which is measured on the raw waveform before any gain.
                audio_settings = self.settings.get("audio", {})
                endpoint_floor_dbfs = float(
                    audio_settings.get(
                        "segment_endpoint_floor_dbfs",
                        audio_settings.get(
                            "segment_active_floor_dbfs",
                            DEFAULT_SEGMENT_ACTIVE_FLOOR_DBFS,
                        ),
                    )
                )
                endpoint_floor = 10.0 ** (endpoint_floor_dbfs / 20.0)
                endpoint_active = float(
                    float(metrics.get("trailing_rms", 0.0)) > endpoint_floor
                )
                metrics[GENERATION_ENDPOINT_ACTIVE_METRIC] = endpoint_active
                metrics["generation_endpoint_floor_dbfs"] = endpoint_floor_dbfs
            if generation_ceiling_hit:
                metrics[GENERATION_CEILING_METRIC] = 1.0
            return checksum, metrics, seed
        finally:
            # VieNeu's PyTorch backend may retain allocator cache after returning a NumPy waveform.
            # The WAV is already committed (or the attempt has failed), so this is a safe boundary.
            self.release_inference_cache()
