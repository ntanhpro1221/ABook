from __future__ import annotations

import json

from pathlib import Path
from typing import Any


GENDER_MALE = "male"
GENDER_FEMALE = "female"
GENDER_UNKNOWN = "unknown"
REGION_NORTH = "Bắc"
REGION_SOUTH = "Nam"
REGION_CENTRAL = "Trung"
STYLE_NATURAL = "tu_nhien"
STYLE_STORY = "doc_truyen"
STYLE_NEWS = "tin_tuc"

REGION_PRIORITY = {
    REGION_NORTH: 0,
    REGION_SOUTH: 1,
    REGION_CENTRAL: 2,
}
STYLE_PRIORITY = {
    STYLE_NATURAL: 0,
    STYLE_STORY: 1,
}
# Central Vietnamese is the least mutually intelligible of the three dialects, and its
# tone system diverges most from the written Northern-standard orthography an audiobook
# reads from. Measured on committed audio, the Central presets missed tones on ordinary
# vocabulary rather than on names - "khốn kiếp" heard as "khôn kiêp", "thuần khiết" as
# "thuân khiệt" - and tone carries lexical meaning, so that is a comprehension cost for
# listeners, not only for ASR. The presets stay in the catalog because VieNeu offers them
# and older books may have locked them; they are simply never cast.
CASTING_REGIONS = frozenset({REGION_NORTH, REGION_SOUTH})
SPEED_FACTOR_MIN = 0.70
SPEED_FACTOR_MAX = 1.50
DEFAULT_NARRATOR_BY_GENDER = {
    GENDER_MALE: "Đức Trí",
    GENDER_FEMALE: "Đoan Trang",
}
VOICE_PREVIEW_FILENAMES = {
    "Phạm Tuyên": "pham_tuyen.wav",
    "Thanh Bình": "thanh_binh.wav",
    "Xuân Vĩnh": "xuan_vinh.wav",
    "Thái Sơn": "thai_son.wav",
    "Quang Sơn": "quang_son.wav",
    "Trúc Ly": "truc_ly.wav",
    "Đoan Trang": "doan_trang.wav",
    "Ngọc Linh": "ngoc_linh.wav",
    "Thục Đoan": "thuc_doan.wav",
    "Ngọc Trân": "ngoc_tran.wav",
    "Adam": "adam.wav",
    "Adam bựa": "adam_bua.wav",
    "Thiện Minh": "anh_khoi.wav",
    "Đức Trí": "duc_tri.wav",
    "Kim Thanh": "kim_thanh.wav",
    "Quốc Tuấn": "manh_dung.wav",
    "Hải Đăng": "minh_quan_pro.wav",
    "Mỹ Duyên": "my_duyen.wav",
    "Ngọc Huyền": "ngoc_huyen.wav",
    "Quỳnh Anh": "quynh_anh.wav",
    "Thiền Tâm Đức": "thien_tam_duc.wav",
    # Máy đọc ZeroTTS: cùng hai câu dò, cùng hạt giống, qua đúng adapter của Studio (scripts/make_voice_previews.py --engine zerotts).
    "baotrang": "zerotts_baotrang.wav",
    "giahuy": "zerotts_giahuy.wav",
    "huuduc": "zerotts_huuduc.wav",
    "kimoanh": "zerotts_kimoanh.wav",
    "quangminh": "zerotts_quangminh.wav",
    # Supertonic: cùng câu, cùng hạt giống, ở tốc độ của máy trong bảng cân bằng (`engine_speed`).
    "F1": "supertonic_f1.wav",
    "F3": "supertonic_f3.wav",
    "M4": "supertonic_m4.wav",
    "M5": "supertonic_m5.wav",
}

VIENEU_PRESETS: tuple[dict[str, str], ...] = (
    {
        "name": "Phạm Tuyên", "gender": GENDER_MALE, "region": REGION_NORTH,
        "style": STYLE_NATURAL, "description": "Nam · Bắc · Tự nhiên",
    },
    {
        "name": "Thái Sơn", "gender": GENDER_MALE, "region": REGION_SOUTH,
        "style": STYLE_STORY, "description": "Nam · Nam · Kể chuyện",
    },
    {
        "name": "Thanh Bình", "gender": GENDER_MALE, "region": REGION_NORTH,
        "style": STYLE_STORY, "description": "Nam · Bắc · Kể chuyện",
    },
    {
        "name": "Xuân Vĩnh", "gender": GENDER_MALE, "region": REGION_NORTH,
        "style": STYLE_NATURAL, "description": "Nam · Bắc · Tự nhiên",
    },
    {
        "name": "Quang Sơn", "gender": GENDER_MALE, "region": REGION_CENTRAL,
        "style": STYLE_NATURAL, "description": "Nam · Trung · Tự nhiên",
    },
    {
        "name": "Minh Đức", "gender": GENDER_MALE, "region": REGION_NORTH,
        "style": STYLE_NEWS, "description": "Nam · Bắc · Tin tức",
    },
    {
        "name": "Minh Triết", "gender": GENDER_MALE, "region": REGION_SOUTH,
        "style": STYLE_NEWS, "description": "Nam · Nam · Tin tức",
    },
    {
        "name": "Ngọc Linh", "gender": GENDER_FEMALE, "region": REGION_NORTH,
        "style": STYLE_STORY, "description": "Nữ · Bắc · Kể chuyện",
    },
    {
        "name": "Thục Đoan", "gender": GENDER_FEMALE, "region": REGION_SOUTH,
        "style": STYLE_STORY, "description": "Nữ · Nam · Kể chuyện",
    },
    {
        "name": "Trúc Ly", "gender": GENDER_FEMALE, "region": REGION_NORTH,
        "style": STYLE_NATURAL, "description": "Nữ · Bắc · Tự nhiên",
    },
    {
        "name": "Đoan Trang", "gender": GENDER_FEMALE, "region": REGION_NORTH,
        "style": STYLE_NATURAL, "description": "Nữ · Bắc · Tự nhiên",
    },
    {
        "name": "Ngọc Trân", "gender": GENDER_FEMALE, "region": REGION_CENTRAL,
        "style": STYLE_NATURAL, "description": "Nữ · Trung · Tự nhiên",
    },
    {
        "name": "Mai Anh", "gender": GENDER_FEMALE, "region": REGION_NORTH,
        "style": STYLE_NEWS, "description": "Nữ · Bắc · Tin tức",
    },
    {
        "name": "Thùy Dung", "gender": GENDER_FEMALE, "region": REGION_SOUTH,
        "style": STYLE_NEWS, "description": "Nữ · Nam · Tin tức",
    },
    # VieNeu 3.8.1, nhận ngày 2026-09-18 sau khi chủ sách nghe từng giọng.
    {
        "name": "Adam", "gender": GENDER_MALE, "region": REGION_SOUTH,
        "style": STYLE_NATURAL, "description": "Nam · Nam · Tự nhiên",
    },
    {
        "name": "Adam bựa", "gender": GENDER_MALE, "region": REGION_NORTH,
        "style": STYLE_NATURAL, "description": "Nam · Bắc · Tự nhiên",
    },
    {
        "name": "Thiện Minh", "gender": GENDER_MALE, "region": REGION_NORTH,
        "style": STYLE_STORY, "description": "Nam · Bắc · Kể chuyện",
    },
    {
        "name": "Đức Trí", "gender": GENDER_MALE, "region": REGION_SOUTH,
        "style": STYLE_STORY, "description": "Nam · Nam · Kể chuyện",
    },
    {
        "name": "Kim Thanh", "gender": GENDER_FEMALE, "region": REGION_SOUTH,
        "style": STYLE_STORY, "description": "Nữ · Nam · Kể chuyện",
    },
    {
        "name": "Quốc Tuấn", "gender": GENDER_MALE, "region": REGION_NORTH,
        "style": STYLE_NATURAL, "description": "Nam · Bắc · Tự nhiên",
    },
    {
        "name": "Hải Đăng", "gender": GENDER_MALE, "region": REGION_NORTH,
        "style": STYLE_NATURAL, "description": "Nam · Bắc · Tự nhiên",
    },
    {
        "name": "Mỹ Duyên", "gender": GENDER_FEMALE, "region": REGION_SOUTH,
        "style": STYLE_STORY, "description": "Nữ · Nam · Kể chuyện",
    },
    {
        "name": "Ngọc Huyền", "gender": GENDER_FEMALE, "region": REGION_NORTH,
        "style": STYLE_NATURAL, "description": "Nữ · Bắc · Tự nhiên",
    },
    {
        "name": "Quỳnh Anh", "gender": GENDER_FEMALE, "region": REGION_NORTH,
        "style": STYLE_STORY, "description": "Nữ · Bắc · Kể chuyện",
    },
    {
        "name": "Thiền Tâm Đức", "gender": GENDER_MALE, "region": REGION_NORTH,
        "style": STYLE_STORY, "description": "Nam · Bắc · Kể chuyện",
    },
)

# Chỗ phân xử cuối giữa những giọng người nghe CHƯA xếp hạng (`assets/voice_rank.json`, `listener_rank`): một thứ tự CỐ
# ĐỊNH tuỳ ý, KHÔNG phải phán quyết chất lượng - đứng ở đây không có nghĩa giọng ấy tốt hơn. Không theo tên hiển thị -
# VieNeu đổi tên giọng (3.8.2: Anh Khôi -> Thiện Minh...) thì sửa tên tại chỗ, giữ vị trí, phân vai không đổi. Đặt
# 04-10 bằng đúng thứ tự tên (casefold) sau lần đổi tên 3.8.2. Giọng mới thêm vào cuối.
CAST_ORDER: tuple[str, ...] = (
    "Adam", "Adam bựa", "Hải Đăng", "Kim Thanh", "Mai Anh", "Minh Triết", "Minh Đức", "Mỹ Duyên", "Ngọc Huyền", "Ngọc Linh",
    "Ngọc Trân", "Phạm Tuyên", "Quang Sơn", "Quốc Tuấn", "Quỳnh Anh", "Thanh Bình", "Thiền Tâm Đức", "Thiện Minh", "Thái Sơn",
    "Thùy Dung", "Thục Đoan", "Trúc Ly", "Xuân Vĩnh", "Đoan Trang", "Đức Trí",
)
_CAST_RANK = {name: rank for rank, name in enumerate(CAST_ORDER)}


def cast_rank(name: str) -> int:
    """Vị trí cố định của giọng trong `CAST_ORDER`; giọng không có trong đó xếp sau mọi giọng có."""
    return _CAST_RANK.get(name, len(CAST_ORDER))


ENGINE_VIENEU = "vieneu"
ENGINE_ZEROTTS = "zerotts"
ENGINE_SUPERTONIC = "supertonic"
# Tên máy đọc như người nghe thấy trong Studio (nhóm giọng ở "Đổi giọng").
ENGINE_LABELS = {ENGINE_VIENEU: "VieNeu", ENGINE_ZEROTTS: "ZeroTTS", ENGINE_SUPERTONIC: "Supertonic"}

# Giọng của các máy đọc khác VieNeu. `name` là tên giọng của chính máy ấy (khoá trong DB, trong bảng cân bằng
# `<engine>@<phiên bản>/<name>`), `label` là tên người nghe thấy. Mỗi preset là một giọng.
#
# Phân vai TỰ ĐỘNG không chạm tới những giọng này (casting_presets chỉ đọc VIENEU_PRESETS): chúng chỉ đến tay một
# nhân vật khi người nghe chọn trong "Đổi giọng". `castable` = chọn tay được: cần chủ sách nghe đạt VÀ có số cân bằng
# trong voice_balance.json.
#
# ZeroTTS: năm giọng chủ sách chấm "có" ở trang chấm giọng (03-10). Giới, tuổi, chất giọng theo voices/index.json của
# model; miền chưa ai ghi nên để trống.
# Supertonic F1, F3, M4, M5: chủ sách chấm "có"; tốc độ là tham số `speed` của máy, chỉnh lặp tới mốc (docs/VOICE_BALANCE.md
# "Supertonic chỉnh lặp"), ghi ở `engine_speed` của bảng cân bằng. Sáu giọng còn lại có số nhưng chủ sách chưa chọn: đóng.
ENGINE_VOICES: tuple[dict[str, Any], ...] = (
    {
        "engine": ENGINE_ZEROTTS, "name": "baotrang", "label": "Bảo Trang", "gender": GENDER_FEMALE, "region": "",
        "style": STYLE_NEWS, "description": "Nữ · Trưởng thành · Rõ ràng", "castable": True,
    },
    {
        "engine": ENGINE_ZEROTTS, "name": "kimoanh", "label": "Kim Oanh", "gender": GENDER_FEMALE, "region": "",
        "style": STYLE_STORY, "description": "Nữ · Trung niên · Ấm, truyền cảm", "castable": True,
    },
    {
        "engine": ENGINE_ZEROTTS, "name": "giahuy", "label": "Gia Huy", "gender": GENDER_MALE, "region": "",
        "style": STYLE_STORY, "description": "Nam · Trẻ · Trầm ấm", "castable": True,
    },
    {
        "engine": ENGINE_ZEROTTS, "name": "huuduc", "label": "Hữu Đức", "gender": GENDER_MALE, "region": "",
        "style": STYLE_STORY, "description": "Nam · Lớn tuổi · Trầm, điềm đạm", "castable": True,
    },
    {
        "engine": ENGINE_ZEROTTS, "name": "quangminh", "label": "Quang Minh", "gender": GENDER_MALE, "region": "",
        "style": STYLE_NEWS, "description": "Nam · Trẻ · Rõ ràng, dứt khoát", "castable": True,
    },
    {
        "engine": ENGINE_SUPERTONIC, "name": "F1", "label": "Supertonic F1", "gender": GENDER_FEMALE, "region": "",
        "style": STYLE_NATURAL, "description": "Nữ", "castable": True,
    },
    {
        "engine": ENGINE_SUPERTONIC, "name": "F3", "label": "Supertonic F3", "gender": GENDER_FEMALE, "region": "",
        "style": STYLE_NATURAL, "description": "Nữ", "castable": True,
    },
    {
        "engine": ENGINE_SUPERTONIC, "name": "M4", "label": "Supertonic M4", "gender": GENDER_MALE, "region": "",
        "style": STYLE_NATURAL, "description": "Nam", "castable": True,
    },
    {
        "engine": ENGINE_SUPERTONIC, "name": "M5", "label": "Supertonic M5", "gender": GENDER_MALE, "region": "",
        "style": STYLE_NATURAL, "description": "Nam", "castable": True,
    },
    {
        "engine": ENGINE_SUPERTONIC, "name": "F2", "label": "Supertonic F2", "gender": GENDER_FEMALE, "region": "",
        "style": STYLE_NATURAL, "description": "Nữ", "castable": False,
    },
    {
        "engine": ENGINE_SUPERTONIC, "name": "F4", "label": "Supertonic F4", "gender": GENDER_FEMALE, "region": "",
        "style": STYLE_NATURAL, "description": "Nữ", "castable": False,
    },
    {
        "engine": ENGINE_SUPERTONIC, "name": "F5", "label": "Supertonic F5", "gender": GENDER_FEMALE, "region": "",
        "style": STYLE_NATURAL, "description": "Nữ", "castable": False,
    },
    {
        "engine": ENGINE_SUPERTONIC, "name": "M1", "label": "Supertonic M1", "gender": GENDER_MALE, "region": "",
        "style": STYLE_NATURAL, "description": "Nam", "castable": False,
    },
    {
        "engine": ENGINE_SUPERTONIC, "name": "M2", "label": "Supertonic M2", "gender": GENDER_MALE, "region": "",
        "style": STYLE_NATURAL, "description": "Nam", "castable": False,
    },
    {
        "engine": ENGINE_SUPERTONIC, "name": "M3", "label": "Supertonic M3", "gender": GENDER_MALE, "region": "",
        "style": STYLE_NATURAL, "description": "Nam", "castable": False,
    },
)


def preset_by_name(name: str) -> dict[str, str]:
    for preset in VIENEU_PRESETS:
        if preset["name"] == name:
            return preset
    raise ValueError(f"Unknown VieNeu preset: {name!r}")


def engine_voice(name: str, engine: str | None = None) -> dict[str, Any] | None:
    """Giọng của máy đọc khác VieNeu mang tên `name` (của `engine` nếu nói rõ), hay None."""
    for voice in ENGINE_VOICES:
        if voice["name"] == name and (engine is None or voice["engine"] == engine):
            return voice
    return None


def engine_of_voice(name: str) -> str:
    """Máy đọc của một tên giọng: VieNeu cho preset VieNeu, máy của giọng ấy cho giọng máy khác."""
    voice = engine_voice(name)
    return str(voice["engine"]) if voice is not None else ENGINE_VIENEU


def castable_engine_voices(gender: str | None = None) -> list[dict[str, Any]]:
    """Giọng máy khác người nghe chọn tay được (không bao giờ vào phân vai tự động), theo thứ tự danh mục."""
    return [voice for voice in ENGINE_VOICES if voice["castable"] and (not gender or voice["gender"] == gender)]


def preset_priority(preset: dict[str, Any]) -> tuple[int, int, int, str]:
    name = str(preset.get("name", ""))
    return (
        REGION_PRIORITY.get(str(preset.get("region", "")), len(REGION_PRIORITY)),
        STYLE_PRIORITY.get(str(preset.get("style", "")), len(STYLE_PRIORITY)),
        cast_rank(name),
        name.casefold(),
    )


def casting_preset_priority(preset: dict[str, Any]) -> tuple[int, int, int, int, str]:
    region = str(preset.get("region", ""))
    style = str(preset.get("style", ""))
    name = str(preset.get("name", ""))
    return (
        0 if style == STYLE_NATURAL else 1,
        REGION_PRIORITY.get(region, len(REGION_PRIORITY)),
        STYLE_PRIORITY.get(style, len(STYLE_PRIORITY)),
        cast_rank(name),
        name.casefold(),
    )


# A listener's ranking of the presets they have actually heard, per role
# (`assets/voice_rank.json`: narrator / character, each male and female), as a list
# of TIERS, best first; each tier is a list of presets the listener rates equal, so a tie
# inside a tier falls through to the computed proxies and then to `CAST_ORDER`. This
# outranks measured voice features because those are proxies for how good the
# result sounds and this is the thing itself - and the proxies have been wrong here
# before: reach and shift between them put Ngọc Linh last of the three girl voices, which
# is exactly backwards. An empty list ranks nothing, so casting falls through to the
# arbitrary `CAST_ORDER`.
#
# Male verdict, 05-11: quality first ("tốt" above "rất ổn"), then fit for the role inside
# a quality level. Good as a narrator: Đức Trí, Thiền Tâm Đức. Good as a natural voice:
# Xuân Vĩnh. Good: Phạm Tuyên. "Rất ổn", just under good: Thái Sơn, Adam. "Narrates well"
# does not mean "not natural" or the reverse - it only fits better - and a voice outside
# the narrator group is no match for one inside it when it narrates (Phạm Tuyên is good,
# yet narrates worse than the two named narrators). Hence narrator = [Đức Trí, Thiền Tâm
# Đức] > [Phạm Tuyên, Xuân Vĩnh] > [Thái Sơn, Adam], character = [Xuân Vĩnh] > [Đức Trí,
# Thiền Tâm Đức, Phạm Tuyên] > [Thái Sơn, Adam]; any other male preset (Adam bựa included)
# is unranked, below every tier.
#
# Female verdict, updated 06-11 ("quỳnh trang" read as Quỳnh Anh):
# narrator = [Đoan Trang] > [Ngọc Linh] > [Kim Thanh, Mỹ Duyên, Quỳnh Anh, Thục Đoan];
# character = [Ngọc Linh] > [Đoan Trang] > [Kim Thanh, Mỹ Duyên, Quỳnh Anh, Thục Đoan].
# Mai Anh remains a news preset, unranked, not castable or selectable, without balance entries.
# The default female narrator is Đoan Trang.
#
# Children are cast from the female presets by the female `character` tiers: there is no
# child role.
#
# Only what was actually judged goes in. A preset absent from a list is unheard rather
# than rejected, and sorts after every ranked one, so the theory still decides among the
# unheard.
VOICE_RANK_PATH = Path(__file__).resolve().parent / "assets" / "voice_rank.json"


VOICE_RANK_ROLES = ("narrator", "character")

VoiceRank = dict[str, dict[str, tuple[tuple[str, ...], ...]]]


def load_voice_rank(path: Path = VOICE_RANK_PATH) -> VoiceRank:
    """Read and check the listener's ranking; a bad name or tier fails here, not in a book."""
    data = json.loads(path.read_text(encoding="utf-8"))
    known = {str(preset["name"]) for preset in VIENEU_PRESETS}
    table: VoiceRank = {}
    for role in VOICE_RANK_ROLES:
        table[role] = {}
        for gender in (GENDER_MALE, GENDER_FEMALE):
            tiers = tuple(tuple(str(name) for name in tier) for tier in data[role][gender])
            where = f"{path.name}: {role}.{gender}"
            if not all(tiers):
                raise ValueError(f"{where} has an empty tier")
            names = [name for tier in tiers for name in tier]
            unknown = [name for name in names if name not in known]
            if unknown:
                raise ValueError(f"{where} names no such VieNeu preset: {unknown}")
            if len(set(names)) != len(names):
                raise ValueError(f"{where} lists a preset twice")
            table[role][gender] = tiers
    return table


VOICE_RANK = load_voice_rank()


def listener_rank(preset_name: str, gender: str, role: str = "character") -> int:
    """The listener's tier for a preset in this role (0 = best); unranked = the number of tiers, after every ranked one.

    A child is ranked by the caller as female (`PresetAllocator.choose` casts children from the female presets).
    """
    tiers = VOICE_RANK[role].get(str(gender), ())
    name = str(preset_name)
    return next((index for index, tier in enumerate(tiers) if name in tier), len(tiers))


def preset_eligible(preset: dict[str, Any], role: str) -> bool:
    """Quyền dùng theo vai: phán quyết chủ sách mở cả giọng tin tức, chỉ cho vai đã xếp hạng.

    Giọng chưa nghe giữ luật catalog cũ. Vùng miền và lệnh cấm phân vai vẫn có hiệu lực.
    """
    tiers = VOICE_RANK[role].get(str(preset["gender"]), ())
    ranked = any(preset["name"] in tier for tier in tiers)
    if preset["style"] == STYLE_NEWS and not ranked:
        return False
    return role != "character" or (
        preset["region"] in CASTING_REGIONS and preset["name"] not in EXCLUDED_PRESETS
    )

# How far a preset's own F0 may be carried toward an age target (teen, elderly). Set where
# the presets actually stop working, judged by ear carried the whole way, rather than at a
# round number.


# Presets barred from every role, for the same kind of reason the Central region is barred:
# a Vietnamese listener judged them, and that judgement is not something the code can
# second-guess. Xuân Vĩnh was first given a ranking penalty, which only made it a last
# resort rather than never - the listener's answer was that it should not be reachable at
# all, in any role, at any warp.
#
# Empty since VieNeu 3.8.1 (2026-09-18): the same listener heard Xuân Vĩnh again and found
# it had become a natural Northern male voice, "very good", and reopened it. The set stays
# so the next such verdict has somewhere to go.
EXCLUDED_PRESETS: frozenset[str] = frozenset()


def narrator_presets(
    gender: str | None = None,
    region: str | None = None,
) -> list[dict[str, str]]:
    candidates = [
        preset
        for preset in VIENEU_PRESETS
        if preset_eligible(preset, "narrator")
        and (not gender or preset["gender"] == gender)
        and (not region or preset["region"] == region)
    ]
    preferred_order = {
        DEFAULT_NARRATOR_BY_GENDER[GENDER_MALE]: 0,
        DEFAULT_NARRATOR_BY_GENDER[GENDER_FEMALE]: 1,
    }
    return sorted(
        candidates,
        key=lambda preset: (
            preferred_order.get(preset["name"], len(preferred_order)),
            # The owner's narrator tiers, by the preset's own gender (this list spans both),
            # ahead of the arbitrary order - so the fallback after the default narrator is
            # the next best narrator rather than the next alphabetical one.
            listener_rank(preset["name"], preset["gender"], role="narrator"),
            *preset_priority(preset),
        ),
    )


def casting_presets(gender: str) -> list[dict[str, str]]:
    """Every preset eligible for casting, best first.

    There is one region allowlist for every role. NPCs used to reach a wider pool that
    added the Central presets; that pool is gone with them, so the distinction would now
    only be a parameter that never changes anything.
    """
    candidates = [
        preset
        for preset in VIENEU_PRESETS
        if preset["gender"] == gender
        and preset_eligible(preset, "character")
    ]
    return sorted(candidates, key=casting_preset_priority)
