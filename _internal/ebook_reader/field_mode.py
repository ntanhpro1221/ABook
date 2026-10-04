"""B8 - TÁCH VIỆC: model chỉ trả một phần trường (nhánh dev/breakthrough-eval, CHỈ để đo, không bao giờ gộp).

  ABOOK_SPEAKER_ONLY=1   (nhánh b; ABOOK_POINTER_MODE=1 kéo theo - nhánh c) mỗi đoạn model chỉ trả id, kind, speaker.
                         Host điền: emotion=neutral, intensity=0, pace/volume=normal, gender/age=unknown, confidence=0.9;
                         tắt kiểm cảm xúc của host (_host_affect_adjudication, _semantic_delivery_issues) vì cảm xúc
                         không còn là việc của model - không thì host đòi sửa "neutral mâu thuẫn cue" mãi.
  ABOOK_EMOTION_ONLY=1   (nhánh d) kind + speaker từng đoạn là DỮ KIỆN ở dòng việc cuối tin nhắn (lấy từ gold
                         ABOOK_EMOTION_GOLD=<thư mục gold>, luật chọn như gold_replay); model chỉ trả id, emotion,
                         intensity, pace, volume. Host giữ kind/speaker đã cho, gender theo gold, age=unknown, confidence=0.9.

THÂN CHUNG + ĐUÔI VIỆC (nhánh e = một adapter học cả b và d): prompt hệ thống và toàn bộ tin nhắn tới hết phần đoạn văn
(và phản hồi lần trước nếu có) GIỐNG HỆT nhau ở b và d (generator_system chung, dòng đoạn văn giữ cả allowed_emotions,
bỏ câu ràng buộc confidence); chỉ dòng NHIỆM VỤ ở cuối khác (task_tail). Schema (Ollama `format`) là tham số riêng, không
nằm trong prompt, nên không phá tiền tố KV chung. Nhánh c = b + khối con trỏ + quy tắc 11 (không chung thân với d).
Không đặt biến nào: mode() == "" và bộ phân tích y hệt từng byte (mọi hàm dưới đây không được gọi).

Lượt critic: cùng phép bỏ trường - ứng viên chỉ hiện các trường model còn trả, verdict chỉ trả các trường ấy (cùng
id/rationale/evidence_quote/critic_confidence); host điền phần còn lại của verdict bằng chính ứng viên (đồng ý).
pronunciations (cấp gốc) giữ nguyên ở mọi chế độ.
Cùng các hàm biến đổi dùng cho lúc chạy và lúc dựng dữ liệu (LLM_Train/b8/build_b8.py).
"""
from __future__ import annotations

import copy
import os
import re
from typing import Any

SPEAKER = "speaker"
EMOTION = "emotion"
GEN_KEEP = {SPEAKER: ("id", "kind", "speaker"), EMOTION: ("id", "emotion", "intensity", "pace", "volume")}
CRITIC_KEEP = {SPEAKER: ("kind", "speaker"), EMOTION: ("emotion", "intensity", "pace", "volume")}
CRITIC_ALWAYS = ("id", "rationale", "evidence_quote", "critic_confidence")
SPEAKER_DEFAULTS = {"emotion": "neutral", "intensity": 0, "pace": "normal", "volume": "normal", "gender": "unknown",
                    "age": "unknown", "confidence": 0.9}
GENDER = {"m": "male", "f": "female"}


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip() not in {"", "0"}


def mode() -> str:
    speaker = _flag("ABOOK_SPEAKER_ONLY") or _flag("ABOOK_POINTER_MODE")
    emotion = _flag("ABOOK_EMOTION_ONLY")
    if speaker and emotion:
        raise ValueError("ABOOK_EMOTION_ONLY không đi cùng ABOOK_SPEAKER_ONLY/ABOOK_POINTER_MODE")
    return SPEAKER if speaker else EMOTION if emotion else ""


def emotion_gold_dir() -> str:
    directory = os.environ.get("ABOOK_EMOTION_GOLD", "").strip()
    if not directory:
        raise RuntimeError("ABOOK_EMOTION_ONLY cần ABOOK_EMOTION_GOLD=<thư mục gold> (kind + speaker cho sẵn)")
    return directory


# --- prompt hệ thống -----------------------------------------------------------------------------------------


def _rules(prompt: str) -> tuple[str, dict[int, str]]:
    starts = [(m.start(), int(m.group(1))) for m in re.finditer(r"(?m)^(\d+)\. ", prompt)]
    head = prompt[: starts[0][0]]
    rules = {}
    for index, (start, number) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(prompt)
        rules[number] = prompt[start:end]
    return head, rules


def _cut(text: str, old: str, new: str = "") -> str:
    if old not in text:
        raise RuntimeError(f"field_mode: không thấy đoạn cần sửa trong prompt: {old[:50]!r}")
    return text.replace(old, new, 1)


def generator_system(base: str, field_mode: str) -> str:
    """Prompt hệ thống CHUNG cho hai việc tách (speaker / emotion) - thân prompt giống hệt nhau, việc nằm ở dòng cuối tin
    nhắn (task_tail). Bỏ quy tắc 7 (gender/age do host điền) và câu giữ gender ở quy tắc 2; quy tắc 9 nói về dòng NHIỆM VỤ."""
    if not field_mode:
        return base
    head, rules = _rules(base)
    rules[2] = _cut(rules[2], " Phải giữ đúng gender đã biết của cùng tên qua mọi batch.")
    del rules[7]
    rules[9] = ("9. Dòng NHIỆM VỤ ở cuối tin nhắn nói phải trả những trường nào cho mỗi đoạn: chỉ trả đúng các trường ấy."
                " Các trường còn lại (và gender, age, confidence) do host điền; trường đã cho sẵn là dữ kiện, không bàn lại.\n")
    return head + "".join(rules[number] for number in sorted(rules))


def task_tail(field_mode: str, batch_ids: list[str], given: dict[str, dict[str, str]] | None = None) -> str:
    """Dòng việc ở CUỐI tin nhắn (sau mọi phần khác, kể cả phản hồi lần trước): phần trước nó là thân chung."""
    if field_mode == SPEAKER:
        return "\n\nNHIỆM VỤ: NGƯỜI NÓI. Mỗi đoạn chỉ trả id, kind, speaker."
    lines = [f"- {batch_id}: kind={given[batch_id]['kind']}; speaker={given[batch_id]['speaker']}" for batch_id in batch_ids]
    return ("\n\nNHIỆM VỤ: CẢM XÚC. Mỗi đoạn chỉ trả id, emotion, intensity, pace, volume. kind và speaker đã chốt:\n"
            + "\n".join(lines))


_CRITIC_SIX = "Luôn trả sáu trường kind, speaker, emotion, intensity, pace và volume"
_CRITIC_CUES = ("Các cue nhận thức mơ hồ “thất thần”, “bàng hoàng”, “hỗn loạn” khi đứng một mình không bắt buộc\n"
                "emotion=afraid, intensity cao hoặc pace=fast; candidate neutral với intensity=0 hoặc 1 và pace=normal vẫn có thể\n"
                "tương thích khi không có cue affect rõ ràng khác. Cue sợ hãi rõ ràng khác vẫn phải được xét độc lập.\n")
_CRITIC_EXAMPLE = ("Ví dụ: candidate\nthought/Hạ Phong/neutral/0/normal/normal cho câu “Mình sẽ chết mất!” có thể được sửa thành\n"
                   "thought/Hạ Phong/afraid/2/fast/normal. ")
_CRITIC_SPEAKER_PARAS = (
    "Khóa kind=dialogue chỉ xác nhận ranh giới lời nói, không xác nhận danh tính người nói; vẫn phải kiểm speaker độc lập từ\n"
    "lời dẫn và mạch hội thoại. Không được đổi speaker thành NARRATOR chỉ vì bạn bất đồng với kind đã khóa.\n",
    "Speaker là identity source-bound: chỉ được chọn đúng một giá trị trong allowed_speakers do host gửi cho request.\n",
    "Danh sách đó gồm các identity đã xuất hiện trong candidate của batch cùng NARRATOR và UNKNOWN. Mọi NPC_LOCAL:: là\n"
    "opaque host ID, phải sao chép byte-for-byte; không sửa scope, hash hay nhãn, không trả dạng NPC_LOCAL:<nhãn> và không\n"
    "tự tạo local ID hoặc tên riêng mới. Nếu candidate dùng sai một identity chưa có trong allowed_speakers, trả UNKNOWN\n"
    "để generator phân tích lại từ nguồn; không bịa chuỗi speaker ngoài enum.\n",
    "Câu kể ngôi ba có chủ thể cùng động từ nhận thức hoặc ý muốn, như “cậu biết... muốn...”, chỉ báo cáo trạng thái\n"
    "của nhân vật và vẫn là narration. Chỉ tiếng nói nội tâm trực tiếp như “Mình đang ở đâu thế này?” mới là thought.\n",
    "Segment kind=thought dùng speaker là chính nhân vật đang nghĩ, vì nội tâm được đọc bằng giọng người đó.\n"
    "Chỉ chấp nhận NARRATOR khi text và previous_text không cho biết ai đang nghĩ.\n",
)


def critic_system(base: str, field_mode: str) -> str:
    if field_mode == SPEAKER:
        text = _cut(base, _CRITIC_SIX, "Luôn trả hai trường kind và speaker")
        text = _cut(text, _CRITIC_CUES)
        text = _cut(text, _CRITIC_EXAMPLE)
        text = re.sub(r"\bsáu\b", "hai", text)
        return text + "Chỉ trả kind và speaker; emotion, intensity, pace và volume do host giữ, không trả chúng.\n"
    if field_mode == EMOTION:
        text = _cut(base, _CRITIC_SIX, "Luôn trả bốn trường emotion, intensity, pace và volume")
        for paragraph in _CRITIC_SPEAKER_PARAS:
            text = _cut(text, paragraph)
        text = _cut(text, _CRITIC_EXAMPLE, "Ví dụ: candidate neutral/0/normal/normal cho câu “Mình sẽ chết mất!” có thể "
                                           "được sửa thành afraid/2/fast/normal. ")
        text = re.sub(r"\bsáu\b", "bốn", text)
        return text + "kind và speaker là dữ kiện host đã chốt; chỉ trả emotion, intensity, pace và volume.\n"
    return base


# --- schema --------------------------------------------------------------------------------------------------


def _strip_items(items: dict[str, Any], keep: tuple[str, ...]) -> None:
    for branch in items.get("oneOf", [items]):
        branch["properties"] = {key: value for key, value in branch["properties"].items() if key in keep}
        branch["required"] = [key for key in branch["required"] if key in keep]


def output_schema(schema: dict[str, Any], field_mode: str) -> dict[str, Any]:
    schema = copy.deepcopy(schema)
    _strip_items(schema["properties"]["segments"]["items"], GEN_KEEP[field_mode])
    return schema


def critic_schema(schema: dict[str, Any], field_mode: str) -> dict[str, Any]:
    schema = copy.deepcopy(schema)
    _strip_items(schema["properties"]["verdicts"]["items"], CRITIC_ALWAYS + CRITIC_KEEP[field_mode])
    return schema


# --- dòng request ---------------------------------------------------------------------------------------------


def critic_rows(rows: list[dict[str, Any]], field_mode: str) -> list[dict[str, Any]]:
    keep = CRITIC_KEEP[field_mode]
    out = []
    for row in rows:
        row = dict(row)
        if field_mode == SPEAKER:
            row.pop("batch_signature_count", None)  # tần suất chữ ký giọng: thông tin cảm xúc
        if isinstance(row.get("candidate"), dict):
            if field_mode == EMOTION:  # kind/speaker là dữ kiện: vẫn hiện, ngoài candidate
                row["given"] = {key: row["candidate"][key] for key in ("kind", "speaker") if key in row["candidate"]}
            row["candidate"] = {key: value for key, value in row["candidate"].items() if key in keep}
        if isinstance(row.get("host_locked_fields"), dict):
            row["host_locked_fields"] = {key: value for key, value in row["host_locked_fields"].items() if key in keep}
        out.append(dict(sorted(row.items())))
    return out


# --- host điền ------------------------------------------------------------------------------------------------


def fill_generator(payload: dict[str, Any], field_mode: str, given: dict[str, dict[str, str]] | None = None) -> None:
    for item in payload.get("segments", []) if isinstance(payload.get("segments"), list) else []:
        if not isinstance(item, dict):
            continue
        if field_mode == SPEAKER:
            for key, value in SPEAKER_DEFAULTS.items():
                item[key] = value
        else:
            facts = (given or {}).get(str(item.get("id", "")), {"kind": "narration", "speaker": "NARRATOR", "gender": "unknown"})
            item["kind"], item["speaker"] = facts["kind"], facts["speaker"]
            item["gender"], item["age"], item["confidence"] = facts.get("gender", "unknown"), "unknown", 0.9


def fill_critic(payload: dict[str, Any], candidate_rows: list[dict[str, Any]], field_mode: str) -> None:
    candidates = {str(row["id"]): row.get("candidate", {}) for row in candidate_rows}
    keep = CRITIC_KEEP[field_mode]
    for verdict in payload.get("verdicts", []) if isinstance(payload.get("verdicts"), list) else []:
        if not isinstance(verdict, dict):
            continue
        candidate = candidates.get(str(verdict.get("id", "")), {})
        for key, value in candidate.items():
            if key not in keep:
                verdict[key] = value


def given_from_gold(entry: Any, hint: str, allowed_kinds: tuple[str, ...] | None) -> dict[str, str]:
    """Dữ kiện kind + speaker + gender của một đoạn từ gold, đúng luật chọn của gold_replay.generator."""
    if allowed_kinds is None:
        allowed_kinds = ("dialogue",) if hint == "dialogue" else ("narration", "thought")
    if entry is None:
        kind = hint if hint in allowed_kinds else allowed_kinds[0]
        return {"kind": kind, "speaker": "NARRATOR", "gender": "unknown"} if kind == "narration" else {
            "kind": kind, "speaker": "UNKNOWN", "gender": "unknown"}
    kind = next((k for k in ("narration", "dialogue", "thought") if k in entry.kinds and k in allowed_kinds), allowed_kinds[0])
    if kind == "narration":
        return {"kind": kind, "speaker": "NARRATOR", "gender": "unknown"}
    speaker = next((o for o, c in entry.speakers if c == 1.0), entry.speakers[0][0])
    if speaker == "NPC*":
        speaker = f"NPC_LOCAL:{entry.npc_label or 'người lạ'}"
    elif speaker == "NARRATOR" and len(entry.speakers) > 1:
        speaker = next((o for o, c in entry.speakers if c == 1.0 and o not in ("NARRATOR", "NPC*", "UNKNOWN")), "NARRATOR")
    if not speaker.startswith("NPC_LOCAL") and speaker not in ("NARRATOR", "UNKNOWN"):
        speaker = " ".join(word[:1].upper() + word[1:].lower() for word in speaker.split(" "))
    gender = GENDER.get(entry.gender, "unknown") if speaker not in ("NARRATOR", "UNKNOWN") else "unknown"
    return {"kind": kind, "speaker": speaker, "gender": gender}
