"""Bộ hằng số cân bằng giọng: mỗi giọng một bản ghi đo trước, lúc thu máy tự áp.

Một giọng = (engine, phiên bản engine, preset, bậc formant), khoá bằng chuỗi ổn định
`vieneu@3.8.1/<preset>/f100` (xem `voice_key`); máy đọc khác cùng dạng, chỉ bậc gốc: `zerotts@0.1.5/baotrang/f100`. Bảng nằm ở `assets/voice_balance.json`; cả hai file
này quyết định âm thanh nên đều nằm trong `QUALITY_IMPLEMENTATION_FILES`.

Ba đại lượng, mỗi cái một thang và một cách ghép (docs/VOICE_BALANCE.md):

- tốc độ: thang tỉ lệ, ghép bằng NHÂN. `tempo = x * r_v` (`x` là núm chung của cả sách);
- độ to: dB/LUFS, ghép bằng CỘNG dB (công thức đầy đủ ở `audio_io.segment_gain_db`);
- màu giọng `pitch_st`: bán cung, ghép bằng CỘNG, cộng thêm độ lệch theo tuổi nhân vật.

Giọng thiếu trong bảng thì LỖI (`VoiceBalanceError`), không bao giờ lặng lẽ dùng 1,0: một giọng chưa đo
mà vẫn thu được là đúng cái lỗi mà bảng này sinh ra để chặn.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

TABLE_PATH = Path(__file__).resolve().parent / "assets" / "voice_balance.json"
TABLE_VERSION = 1
DEFAULT_ENGINE = "vieneu"

# Biên hợp lý, chặn số đo hỏng chứ không phải chặn quyết định: tempo = x * r còn phải lọt
# [SPEED_FACTOR_MIN, SPEED_FACTOR_MAX] của `voice_catalog` (kiểm ở `_validate`).
X_RANGE = (0.5, 1.5)
R_RANGE = (0.5, 1.6)
PACE_FLOOR_SCALE_RANGE = (0.5, 1.0)
LEVEL_RANGE_LUFS = (-40.0, -10.0)
O_DB_RANGE = (-12.0, 12.0)
REF_LUFS_RANGE = (-40.0, -5.0)
PITCH_ST_RANGE = (-12, 12)
# Máy đọc tự đọc nhanh/chậm theo tham số của chính nó (Supertonic `speed`): bản ghi mang `engine_speed` (tham số ấy) và
# `r` = 1 (WSOLA không kéo thêm). Biên theo từng máy - tham số của máy không cùng thang với tempo WSOLA, nên không nới
# R_RANGE chung. Supertonic: hãng cho 0,7 - 2,0.
ENGINE_SPEED_RANGE = {"supertonic": (0.7, 2.0)}


class VoiceBalanceError(ValueError):
    """Giọng này chưa có bản ghi trong bảng cân bằng, hoặc bảng hỏng."""


@dataclass(frozen=True)
class VoiceConstants:
    key: str
    r: float  # hệ số tốc độ, nhân
    o_db: float  # lệch độ to (dB), đo ở x = 1, sau khi áp cao độ và tempo
    ref_lufs: float  # LUFS trung bình của bản thô (sau cao độ + tempo) của giọng
    pitch_st: int  # màu giọng, bán cung
    engine_speed: float | None = None  # tham số tốc độ của chính máy đọc (ENGINE_SPEED_RANGE), None = máy kéo bằng WSOLA


def formant_key(formant_ratio: float) -> str:
    """`f100` cho 1,00; `f093` cho 0,93. Cũng là phần cuối của khoá voice_key trong DB."""
    return f"f{int(round(float(formant_ratio) * 100)):03d}"


def voice_key(engine: str, version: str, preset: str, formant_ratio: float) -> str:
    return f"{engine}@{version}/{preset}/{formant_key(formant_ratio)}"


def _validate(table: Any) -> dict[str, Any]:
    from .voice_catalog import SPEED_FACTOR_MAX, SPEED_FACTOR_MIN

    def number(container: dict[str, Any], name: str, bounds: tuple[float, float], where: str) -> float:
        value = container.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise VoiceBalanceError(f"voice_balance.json: {where}.{name} phải là số, nhận {value!r}")
        if not bounds[0] <= float(value) <= bounds[1]:
            raise VoiceBalanceError(
                f"voice_balance.json: {where}.{name}={value} ngoài [{bounds[0]}, {bounds[1]}]"
            )
        return float(value)

    if not isinstance(table, dict):
        raise VoiceBalanceError("voice_balance.json: gốc phải là object")
    if table.get("version") != TABLE_VERSION:
        raise VoiceBalanceError(
            f"voice_balance.json: version {table.get('version')!r}, mã này đọc version {TABLE_VERSION}"
        )
    versions = table.get("engine_versions")
    if not isinstance(versions, dict) or not versions:
        raise VoiceBalanceError("voice_balance.json: thiếu engine_versions")
    x = number(table, "x", X_RANGE, "")
    number(table, "L_lufs", LEVEL_RANGE_LUFS, "")
    number(table, "pace_floor_scale", PACE_FLOOR_SCALE_RANGE, "")
    floors = table.get("engine_pace_floor", {})
    if not isinstance(floors, dict):
        raise VoiceBalanceError("voice_balance.json: engine_pace_floor phải là object")
    for engine in floors:
        if engine not in versions:
            raise VoiceBalanceError(f"voice_balance.json: engine_pace_floor.{engine} không có trong engine_versions")
        number(floors, engine, PACE_FLOOR_SCALE_RANGE, "engine_pace_floor")
    voices = table.get("voices")
    if not isinstance(voices, dict) or not voices:
        raise VoiceBalanceError("voice_balance.json: thiếu voices")
    for key, record in voices.items():
        if not isinstance(record, dict):
            raise VoiceBalanceError(f"voice_balance.json: {key} phải là object")
        r = number(record, "r", R_RANGE, key)
        number(record, "o_db", O_DB_RANGE, key)
        number(record, "ref_lufs", REF_LUFS_RANGE, key)
        pitch = number(record, "pitch_st", PITCH_ST_RANGE, key)
        if pitch != int(pitch):
            raise VoiceBalanceError(f"voice_balance.json: {key}.pitch_st phải là số nguyên bán cung")
        if not SPEED_FACTOR_MIN <= x * r <= SPEED_FACTOR_MAX:
            raise VoiceBalanceError(
                f"voice_balance.json: tempo x*r = {x * r:.3f} của {key} ngoài "
                f"[{SPEED_FACTOR_MIN}, {SPEED_FACTOR_MAX}]"
            )
        engine, _, rest = key.partition("@")
        version = rest.partition("/")[0]
        if "engine_speed" in record:
            if engine not in ENGINE_SPEED_RANGE:
                raise VoiceBalanceError(f"voice_balance.json: {key} có engine_speed nhưng {engine} không tự đọc theo tốc độ")
            number(record, "engine_speed", ENGINE_SPEED_RANGE[engine], key)
        if versions.get(engine) != version:
            raise VoiceBalanceError(
                f"voice_balance.json: {key} thuộc {engine}@{version} nhưng engine_versions ghi "
                f"{versions.get(engine)!r}"
            )
    return table


@lru_cache(maxsize=1)
def load_table() -> dict[str, Any]:
    """Nạp và kiểm bảng một lần. Gọi `reload_table()` sau khi sửa file (script nhập số, test)."""
    try:
        data = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VoiceBalanceError(f"không đọc được {TABLE_PATH.name}: {exc}") from exc
    return _validate(data)


def reload_table() -> None:
    load_table.cache_clear()


def engine_version(engine: str = DEFAULT_ENGINE) -> str:
    """Phiên bản engine mà bảng được đo cho. Khớp bản ghim trong `runtime_contract`."""
    version = load_table()["engine_versions"].get(engine)
    if not version:
        raise VoiceBalanceError(f"bảng cân bằng giọng không có engine {engine!r}")
    return str(version)


def x() -> float:
    """Núm tốc độ chung của cả sách (nhân vào mọi `r_v`)."""
    return float(load_table()["x"])


def level_lufs() -> float:
    """L: mức độ to chung (LUFS) mà mọi giọng được đưa về, trước các offset tương đối của câu."""
    return float(load_table()["L_lufs"])


def pace_floor_scale() -> float:
    """Hệ số CHUNG nhân vào sàn của cổng nhịp (xem `pace_gate_scale`)."""
    return float(load_table()["pace_floor_scale"])


def pace_gate_scale(key: str = "") -> float:
    """Nhân số của sàn cổng nhịp: `pace_floor_scale * x`, nhân thêm sàn riêng của máy đọc của giọng `key` nếu bảng có
    (`engine_pace_floor`; Supertonic 0,9: nó chèn lặng giữa câu dài hơn ngân sách dấu câu của cổng). Tempo chung đổi thì sàn đổi theo."""
    engine = str(key).partition("@")[0]
    return pace_floor_scale() * x() * float(load_table().get("engine_pace_floor", {}).get(engine, 1.0))


# Giọng GIẢ của các bộ chạy giả (`webui/reading_preview.fake_voice`, test): tên preset không có thật nên không
# thể đo. Chỉ các bộ chạy giả đăng ký vào đây; giọng thật không bao giờ lọt qua cửa này.
_NEUTRAL_RECORD = {"r": 1.0, "o_db": 0.0, "ref_lufs": -19.8, "pitch_st": 0}
_NEUTRAL: dict[str, dict[str, Any]] = {}


def register_neutral_voices(profiles: Any) -> None:
    """Cho các hồ sơ giọng GIẢ (dựng giao diện, test) hằng số trung tính: r = 1, o_db = 0, màu gốc."""
    for profile in profiles:
        _NEUTRAL.setdefault(voice_key_for_profile(profile), dict(_NEUTRAL_RECORD))


def constants_for_key(key: str) -> VoiceConstants:
    record = load_table()["voices"].get(key) or _NEUTRAL.get(key)
    if record is None:
        raise VoiceBalanceError(
            f"giọng {key!r} chưa có trong voice_balance.json - đo giọng này (scripts/"
            "voice_balance_import.py) trước khi phân vai hoặc thu"
        )
    return VoiceConstants(
        key=key,
        r=float(record["r"]),
        o_db=float(record["o_db"]),
        ref_lufs=float(record["ref_lufs"]),
        pitch_st=int(record["pitch_st"]),
        engine_speed=float(record["engine_speed"]) if "engine_speed" in record else None,
    )


def constants_for(engine: str, version: str, preset: str, formant_ratio: float) -> VoiceConstants:
    return constants_for_key(voice_key(engine, version, preset, formant_ratio))


def voice_key_for_profile(profile: Any) -> str:
    """Khoá bảng của một hàng `voice_profiles` (engine, preset, bậc formant; phiên bản theo bảng)."""
    def field(name: str, default: Any) -> Any:
        try:
            value = profile[name]
        except (IndexError, KeyError):
            return default
        return default if value is None else value

    engine = str(field("engine", DEFAULT_ENGINE))
    return voice_key(
        engine, engine_version(engine), str(field("preset_name", "")), float(field("formant_ratio", 1.0))
    )


def constants_for_profile(profile: Any) -> VoiceConstants:
    return constants_for_key(voice_key_for_profile(profile))


def tempo(constants: VoiceConstants) -> float:
    """Hệ số tốc độ áp lên bản thô của giọng: `x * r_v`."""
    return x() * constants.r


def engine_speed(constants: VoiceConstants) -> float | None:
    """Tham số tốc độ đưa cho máy đọc tự đọc theo tốc độ: `x * engine_speed`; None với máy kéo bằng WSOLA."""
    return None if constants.engine_speed is None else x() * constants.engine_speed


def raw_pace_floor_scale(constants: VoiceConstants) -> float:
    """Sàn nhịp của BẢN THÔ (trước khi tăng tốc): sàn cổng chia cho tempo. `x` triệt tiêu."""
    return pace_floor_scale() / constants.r


def preset_pitch_st(preset: str, engine: str = DEFAULT_ENGINE) -> int:
    """Màu giọng nền của preset, bán cung. Lấy ở bậc formant gốc (f100): màu giọng không đổi theo bậc."""
    return constants_for(engine, engine_version(engine), preset, 1.0).pitch_st


def balanced_preset_names() -> list[str]:
    """Các preset VieNeu PHẢI có số trong bảng: phân vai được ∪ chọn được làm người kể.

    Quang Sơn, Ngọc Trân (miền Trung) không phân vai nhưng vẫn là người kể chọn được; giọng Tin tức thì không ở đâu chọn được
    nên không có bản ghi. Khi casting mở thêm giọng, giọng ấy phải được đo rồi mới vào bảng (test độ phủ sẽ đòi).
    """
    from .voice_catalog import casting_presets, narrator_presets

    names: list[str] = []
    for gender in ("male", "female"):
        for preset in casting_presets(gender) + narrator_presets(gender):
            if preset["name"] not in names:
                names.append(preset["name"])
    return names


def castable_keys() -> Iterator[str]:
    """Mọi khoá mà phân vai hay người kể có thể tạo ra cho engine VieNeu (thang formant + formant theo tuổi), cùng bậc gốc
    của mọi giọng máy khác mà người nghe chọn tay được.

    Dùng chung cho test độ phủ và cho người nhập số: bảng phải có bản ghi cho từng khoá này, và chỉ những khoá này.
    """
    from .voice_catalog import (
        GENDER_FEMALE,
        GENDER_MALE,
        GENDER_UNKNOWN,
        VOCAL_TRACT_CM_BY_AGE,
        formant_ratio_for_age,
        formant_variants_for_preset,
    )

    version = engine_version(DEFAULT_ENGINE)
    seen: set[str] = set()
    for name in balanced_preset_names():
        ratios = list(formant_variants_for_preset(name))
        for age in VOCAL_TRACT_CM_BY_AGE:
            for gender in (GENDER_MALE, GENDER_FEMALE, GENDER_UNKNOWN):
                ratios.append(formant_ratio_for_age(name, age, gender))
        for ratio in ratios:
            key = voice_key(DEFAULT_ENGINE, version, name, ratio)
            if key not in seen:
                seen.add(key)
                yield key
    # Giọng máy khác người nghe chọn tay được: chỉ bậc gốc (không có thang formant, không đổi theo tuổi).
    from .voice_catalog import castable_engine_voices

    for voice in castable_engine_voices():
        engine = str(voice["engine"])
        yield voice_key(engine, engine_version(engine), str(voice["name"]), 1.0)
