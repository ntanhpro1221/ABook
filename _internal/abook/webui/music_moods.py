"""Không khí của từng đoạn nhạc nền do LLM đọc CẢ ĐOẠN (valence + tension) - thay cho cộng nhãn cảm xúc từng câu.

Đo ở docs/MUSIC_RESEARCH.md ("KẾT QUẢ llmVT VỚI qwen3.5:4b GỐC"): V và T từ qwen3.5:4b đọc nguyên đoạn hơn đường nhãn
câu +0,098 r (VET), thắng 15/20 chương. Chỉ V và T đổi; arousal, độ lệch, 13 cảm xúc, độ tin cậy vẫn từ nhãn câu
(`music_scenes`), và ranh giới đoạn là của app - LLM không bao giờ cắt đoạn.

Chạy SAU pha phân tích (pipeline.py `after_analysis`: model phân tích đã dỡ khỏi GPU, Ollama còn sống) hay khi người dùng
bấm "Tính lại" ở tab Nhạc. Không có model (người dùng chưa tải qwen3.5:4b, điện thoại, lỗi) thì cuốn chạy đường nhãn y như
trước. Kết quả nằm trong `music_moods.json` của dự án; `music_plan.build` đọc nó khi chia đoạn.

Chỉ nói chuyện với Ollama qua HTTP (không gọi CLI `ollama`: khi máy chủ tắt nó tự mở app khay).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from ..io_utils import atomic_write_json
from . import music_scenes

MODEL = "qwen3.5:4b"
PROMPT_VERSION = "vet-1"
FILE = "music_moods.json"
VERSION = 1
# NGUYÊN VĂN prompt đã đo (LLM_Train/music/segment_mood_llm.py): đổi một chữ là đổi kết quả đã đo - tests/test_music_moods.py
# so với băm của bản gốc; muốn đổi thì đổi PROMPT_VERSION và đo lại.
PROMPT = """Bạn dựng nhạc nền cho sách nói. Dưới đây là MỘT ĐOẠN liền mạch trong một chương truyện (mỗi dòng là một câu).
Hãy chấm không khí của CẢ ĐOẠN theo cảm nhận NGƯỜI NGHE truyện (không theo từng câu), để chọn một bản nhạc nền hợp suốt đoạn:

- V vui/buồn: -2 rất buồn/khổ, 0 trung tính, +2 rất vui/ấm. Cảnh hài thì V dương dù nhân vật đang khổ; cảnh nghiêm thì theo
  nhân vật tiêu điểm.
- E năng lượng: -2 lắng/mệt/tĩnh, 0 vừa, +2 dồn dập/hỗn loạn.
- T căng thẳng: -2 thả lỏng/an toàn, 0 bình thường, +2 hiểm nguy/hồi hộp tột độ.

Mỗi trục là số nguyên hoặc nửa bậc trong -2..2. Chỉ trả lời JSON đúng dạng {{"V": số, "E": số, "T": số}}.

ĐOẠN:
{text}"""


class MoodsUnavailable(RuntimeError):
    """Chưa có model đọc không khí trong Ollama (người dùng chưa tải) - không tính được."""


def scene_text(segments: list[dict[str, Any]], first_index: int, last_index: int) -> str:
    """Chữ của các câu từ vị trí `first_index` tới `last_index` (gồm cả hai), mỗi câu một dòng."""
    return "\n".join(" ".join(str(segment.get("text") or "").split()) for segment in segments[first_index:last_index + 1])


def _post(session: Any, url: str, body: dict[str, Any], timeout: float) -> Any:
    if session is None:
        import requests

        session = requests
    return session.post(url, json=body, timeout=timeout)


def ask(base_url: str, text: str, *, session: Any = None) -> dict[str, float] | None:
    """Một lượt hỏi: V / E / T của cả đoạn, kẹp [-2, 2]. Trả lời hỏng định dạng -> None; Ollama không đáp được thì ném lỗi
    (để cả lượt tính dừng thay vì lần lượt hỏng từng đoạn)."""
    reply = _post(session, f"{base_url.rstrip('/')}/api/generate",
                  {"model": MODEL, "prompt": PROMPT.format(text=text), "stream": False, "think": False, "format": "json",
                   "options": {"temperature": 0, "num_ctx": 16384}, "keep_alive": "5m"}, 300)
    reply.raise_for_status()
    try:
        got = json.loads(reply.json()["response"])
        return {axis: max(-2.0, min(2.0, float(got[axis]))) for axis in "VET"}
    except (ValueError, KeyError, TypeError):
        return None


def model_digest(base_url: str) -> str | None:
    """Digest của model đọc không khí trong Ollama, hay None nếu chưa tải (hay Ollama không đáp)."""
    import requests

    try:
        reply = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=5)
        reply.raise_for_status()
        models = reply.json().get("models") or []
    except (OSError, ValueError, AttributeError):
        return None
    names = {MODEL, f"{MODEL}:latest"}
    for entry in models:
        if isinstance(entry, dict) and names & {entry.get("name"), entry.get("model")}:
            return str(entry.get("digest") or "") or None
    return None


def load(project_root: Path) -> dict[str, Any] | None:
    """`music_moods.json` của dự án nếu đúng phiên bản và đúng prompt đã đo; sai / hỏng / chưa có -> None."""
    try:
        value = json.loads((Path(project_root) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (not isinstance(value, dict) or value.get("version") != VERSION or value.get("prompt") != PROMPT_VERSION
            or not isinstance(value.get("scenes"), list)):
        return None
    return value


def _key(item: dict[str, Any]) -> tuple[Any, Any, Any]:
    return item.get("chapterId"), item.get("firstSegment"), item.get("lastSegment")


def compute(project_root: Path, base_url: str, *, stop_requested: Callable[[], bool] = lambda: False,
            log: Callable[[str], None] = print, pause_requested: Callable[[], bool] = lambda: False) -> int:
    """Hỏi LLM cho từng đoạn (ranh giới của app) chưa có kết quả và ghi `music_moods.json` sau mỗi chương. Cùng prompt và
    cùng digest model thì giữ kết quả đã có (làm tiếp được); khác thì làm lại cả cuốn. Trả số lượt đã hỏi.
    `pause_requested`: nút "Tạm dừng" / gác pin - đứng chờ giữa hai lượt (sách dài có thể mất nửa giờ GPU)."""
    from . import music_plan

    project_root = Path(project_root)
    digest = model_digest(base_url)
    if digest is None:
        raise MoodsUnavailable(f"Ollama chưa có model {MODEL}")
    old = load(project_root)
    kept = {_key(item): item for item in (old["scenes"] if old and old.get("digest") == digest else [])
            if isinstance(item, dict)}
    # Mọi đoạn của cuốn tính trước (không cần model): sổ chỉ giữ đoạn còn đúng ranh giới hiện tại.
    chapters = []
    for script in music_plan.book_scripts(project_root):
        segments = [segment for segment in script.get("segments") or [] if isinstance(segment, dict)]
        chapters.append((script, segments, music_scenes.chapter_scenes(script)))
    current = {_key(scene) for _script, _segments, scenes in chapters for scene in scenes}
    results = {key: item for key, item in kept.items() if key in current}
    asked = failed = 0
    unsaved = False

    def save() -> None:
        nonlocal unsaved
        # Theo thứ tự đoạn của sách (không theo thứ tự hỏi), để file không xáo khi làm tiếp.
        ordered = [results[_key(scene)] for _script, _segments, scenes in chapters for scene in scenes
                   if _key(scene) in results]
        atomic_write_json(project_root / FILE, {"version": VERSION, "prompt": PROMPT_VERSION, "model": MODEL,
                                                "digest": digest, "built": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                                "scenes": ordered})
        unsaved = False

    try:
        for script, segments, scenes in chapters:
            position = {segment.get("id"): index for index, segment in enumerate(segments)}
            for scene in scenes:
                key = _key(scene)
                if key in results:
                    continue
                while pause_requested() and not stop_requested():
                    time.sleep(1.0)
                if stop_requested():
                    return asked
                first, last = position.get(scene["firstSegment"]), position.get(scene["lastSegment"])
                if first is None or last is None:
                    continue
                asked += 1
                got = ask(base_url, scene_text(segments, first, last))
                if got is None:
                    failed += 1
                    continue
                results[key] = {"chapterId": key[0], "firstSegment": key[1], "lastSegment": key[2],
                                "V": got["V"], "E": got["E"], "T": got["T"]}
                unsaved = True
            if unsaved:
                save()
                log(f"Đọc không khí cả đoạn: xong chương {script.get('chapterId')} ({len(results)} đoạn)")
        save()  # lần cuối: bỏ các đoạn không còn đúng ranh giới, ghi digest mới
        if failed:
            log(f"Đọc không khí cả đoạn: {failed} đoạn không đọc được (giữ đường nhãn câu)")
        return asked
    finally:
        if unsaved:  # dừng giữa chương / lỗi mạng: phần đã xong vẫn ghi
            save()


def release(base_url: str) -> None:
    """Dỡ model khỏi VRAM (keep_alive 0). Không dỡ được cũng không sao."""
    try:
        _post(None, f"{base_url.rstrip('/')}/api/generate", {"model": MODEL, "keep_alive": 0}, 20)
    except Exception:  # noqa: BLE001 - chỉ là dọn dẹp
        pass


def run_after_analysis(project_root: Path, base_url: str, stop_requested: Callable[[], bool],
                       log: Callable[[str], None], emit: Callable[[str, dict[str, Any]], None],
                       pause_requested: Callable[[], bool] = lambda: False) -> None:
    """Móc của dây chuyền sau pha phân tích: tính không khí cả đoạn cho nhạc nền nếu người dùng đã tải model và nhạc nền của
    cuốn không tắt. Lỗi ném ra - dây chuyền bắt và chỉ ghi nhật ký (không bao giờ làm hỏng pha phân tích)."""
    from . import music_plan

    if model_digest(base_url) is None or not music_plan.read_overrides(project_root)["enabled"]:
        return
    try:
        asked = compute(project_root, base_url, stop_requested=stop_requested, log=log, pause_requested=pause_requested)
        emit("music_moods_done", {"asked": asked})
    finally:
        release(base_url)
