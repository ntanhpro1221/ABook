"""B-EVAL HOOKS (nhánh dev/breakthrough-eval, CHỈ để đo, không bao giờ gộp).

Mọi hook đọc biến môi trường và TẮT mặc định: không đặt biến thì prompt, cài đặt và hành vi y hệt từng byte.

  ABOOK_PROMPT_DUMP=<file.jsonl>   mỗi lần gọi model sinh (và critic, role="critic") nối một dòng JSON: đầu vào đúng như gửi + raw
  ABOOK_GOLD_PREVIOUS=<thư mục gold>  _previous_turns lấy kind/người nói của đoạn trước lô từ GOLD (teacher forcing giữa các lô)
  ABOOK_ORACLE_DIR=<thư mục>       chèn khối "có mặt" (o1) / "xưng hô" (o2) từ <thư mục>/<gold_dir>/<chương>.o1|o2.json
  ABOOK_ORACLE_GOLD_DIR=<tên>      <gold_dir> (mặc định: tên thư mục của ABOOK_GOLD_PREVIOUS)
  ABOOK_ORACLE_KIND=o1|o2|o1o2     chọn khối nào (mặc định o1o2)
  ABOOK_EVAL_SETTINGS='{"batch_segments":3,"batch_chars":2000,"neighbor_chars":250}'  ghi đè cài đặt phân tích

seq trong file oracle và trong gold đều tính từ 0, cùng seq của bảng segments (score_models khớp gold bằng chính seq ấy).
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

NEIGHBOR_CHARS_DEFAULT = 500
_KIND_PRIORITY = ("dialogue", "thought", "narration")
_cache: dict[str, Any] = {}


def eval_settings() -> dict[str, Any]:
    raw = os.environ.get("ABOOK_EVAL_SETTINGS", "").strip()
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("ABOOK_EVAL_SETTINGS phải là một đối tượng JSON")
    return value


def apply_settings_override(analysis_settings: dict[str, Any]) -> dict[str, Any]:
    """Bản sao cài đặt phân tích với các khoá ghi đè (không đổi dict gốc); không đặt biến thì trả lại chính nó."""
    override = eval_settings()
    return {**analysis_settings, **override} if override else analysis_settings


def previous_turns(default: int) -> int:
    """Số đoạn "ngay trước" đưa vào prompt (E2 rộng: ABOOK_EVAL_SETTINGS {"previous_turns": 9}); không đặt thì mặc định."""
    return int(eval_settings().get("previous_turns", default))


def neighbor_chars() -> int:
    return int(eval_settings().get("neighbor_chars", NEIGHBOR_CHARS_DEFAULT))


def batch_segments_overridden() -> bool:
    return "batch_segments" in eval_settings()


# --- dump -------------------------------------------------------------------------------------------------------


def dump_enabled() -> bool:
    return bool(os.environ.get("ABOOK_PROMPT_DUMP", "").strip())


def dump_call(
    *,
    role: str,
    chapter: str,
    seqs: list[int],
    batch_ids: dict[str, str],
    request: dict[str, Any],
    raw: str,
    attempt: int,
) -> None:
    path = os.environ.get("ABOOK_PROMPT_DUMP", "").strip()
    if not path:
        return
    record = {
        "role": role,
        "chapter": chapter,
        "seqs": seqs,
        "batch_ids": batch_ids,
        "model": request.get("model"),
        "system": request.get("system"),
        "user": request.get("prompt"),
        "format": request.get("format"),
        "options": request.get("options"),
        "raw": raw,
        "attempt": attempt,
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(path, "ab") as handle:  # nhị phân: LF cả trên Windows
        handle.write(line.encode("utf-8"))


# --- gold -------------------------------------------------------------------------------------------------------


def _score_models() -> Any:
    if "score_models" not in _cache:
        file = Path(__file__).resolve().parents[1] / "scripts" / "model_eval" / "score_models.py"
        spec = importlib.util.spec_from_file_location("_abook_eval_score_models", file)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules[spec.name] = module  # dataclass tra module theo tên
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        _cache["score_models"] = module
    return _cache["score_models"]


def _gold() -> dict[tuple[str, int], Any] | None:
    directory = os.environ.get("ABOOK_GOLD_PREVIOUS", "").strip()
    if not directory:
        return None
    key = "gold:" + directory
    if key not in _cache:
        _cache[key] = _score_models().load_gold(Path(directory))
    return _cache[key]


def gold_turn(chapter: str, seq: int, model_kind: str, model_speaker: str) -> tuple[str, str]:
    """(kind, speaker) của một đoạn trước lô: theo gold nếu gold có câu ấy, không thì giữ nhãn của model."""
    gold = _gold()
    entry = gold.get((chapter, seq)) if gold else None
    if entry is None:
        return model_kind, model_speaker
    kind = model_kind if model_kind in entry.kinds else next(k for k in _KIND_PRIORITY if k in entry.kinds)
    if kind == "narration":
        return kind, model_speaker
    name = entry.speakers[0][0]  # đáp án ĐẦU TIÊN của câu
    if name == "NPC*":
        name = f"NPC_LOCAL:{entry.npc_label}" if entry.npc_label else "NPC_LOCAL"
    return kind, name


# --- oracle -----------------------------------------------------------------------------------------------------


def _oracle_kind() -> str:
    return os.environ.get("ABOOK_ORACLE_KIND", "o1o2").strip().lower()


def _oracle_file(chapter: str, which: str) -> Path | None:
    root = os.environ.get("ABOOK_ORACLE_DIR", "").strip()
    if not root:
        return None
    gold_dir = os.environ.get("ABOOK_ORACLE_GOLD_DIR", "").strip() or Path(
        os.environ.get("ABOOK_GOLD_PREVIOUS", "").strip()
    ).name
    path = Path(root) / gold_dir / f"{chapter}.{which}.json"
    return path if path.is_file() else None


def _oracle_json(chapter: str, which: str) -> list[dict[str, Any]]:
    path = _oracle_file(chapter, which)
    if path is None:
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, list) else []


def _blank(value: Any) -> bool:
    return str(value or "").strip() in {"", "-"}


def row_seq(row: Any) -> int:
    try:
        return int(row["seq"])
    except (KeyError, IndexError, TypeError, ValueError):
        return -1


def oracle_block(group: list[Any], chapter_titles: dict[int, str]) -> str:
    """Khối chữ chèn sau "Nhân vật đã biết" và trước _previous_turns, theo các đoạn (chương, seq) của lô."""
    if not os.environ.get("ABOOK_ORACLE_DIR", "").strip():
        return ""
    rows = [(chapter_titles.get(int(row["chapter_id"]), ""), row_seq(row)) for row in group]
    kind = _oracle_kind()
    chapters = list(dict.fromkeys(chapter for chapter, _ in rows))
    out = ""
    if "o1" in kind:
        present: list[str] = []
        for chapter, seq in rows:
            for span in _oracle_json(chapter, "o1"):
                if int(span["from_seq"]) <= seq <= int(span["to_seq"]):
                    present += [name for name in span.get("present", []) if name not in present]
        if present:
            out += f"Nhân vật có mặt trong cảnh này: {', '.join(present)}.\n\n"
    if "o2" in kind:
        lines: list[str] = []
        for chapter in chapters:
            for item in _oracle_json(chapter, "o2"):
                speaker, listener = str(item["speaker"]), str(item["listener"])
                parts = []
                if not _blank(item.get("self")):
                    parts.append(f'tự xưng "{item["self"]}"')
                if not _blank(item.get("calls")):
                    parts.append(f'gọi {listener} là "{item["calls"]}"')
                line = f"- {speaker} nói với {listener}: " + (", ".join(parts) if parts else "không xưng hô")
                if not _blank(item.get("note")):
                    line += f" ({item['note']})"
                if line not in lines:
                    lines.append(line)
        if lines:
            out += "Cách xưng hô giữa các nhân vật:\n" + "\n".join(lines) + "\n\n"
    return out
