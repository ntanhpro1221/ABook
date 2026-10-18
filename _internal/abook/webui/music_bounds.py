"""Ranh giới cảnh của nhạc nền do LLM chia ("Y", CS-SEG) - thay cho luật dấu hiệu khi máy đã có model đọc không khí.

Đo ở Corpus `research/music/PLAN_scenegap_confirm.md` mục 11: ranh giới do qwen3.5:4b chia cảnh (đúng prompt và cửa sổ dưới đây)
đưa vào `music_scenes` thắng bản gộp +6,5 điểm giây nhạc sai rõ (Holm p 0,013). Mã đo: LLM_Train/music/seg_scenes.py.

Chạy SAU pha phân tích (worker.run_music_after_analysis, TRƯỚC `music_moods`: cùng model, đã nạp) hay khi người dùng bấm "Tính lại" ở
tab Nhạc. Kết quả nằm trong `music_bounds.json` của dự án; `music_plan.build` và `music_moods.compute`
đều đọc nó (`load`) và đưa vào `music_scenes.chapter_scenes(boundaries=...)` - nên hai bên luôn chia đoạn GIỐNG NHAU. Chương nào chưa có
ranh LLM (không model, Nghe ngay, điện thoại, chưa tính tới) thì chạy luật dấu hiệu như trước: một chương hoặc có đủ ranh Y, hoặc dùng A.

Chỉ nói chuyện với Ollama qua HTTP (không gọi CLI `ollama`). Temperature 0, không seed: cùng digest model và cùng chữ thì ra cùng ranh;
thêm seed là đổi cấu hình đã đo.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from ..io_utils import atomic_write_json
from . import music_moods, music_scenes

MODEL = music_moods.MODEL
PROMPT_VERSION = "csseg-1"
FILE = "music_bounds.json"
VERSION = 1
WINDOW, OVERLAP = 12000, 2000  # ký tự mỗi cửa sổ, và phần lấn sang cửa sổ kế
# Chương nhiều đoạn hơn mức này (đoạn/giờ đọc) chỉ bị ĐẾM, không đổi hành vi (SCENEY_SPEC 5b). Trần 22 là ĐỔI BÀI/giờ của cả cuốn,
# không phải đoạn/giờ của chương: nó nằm ở `music_plan.SWITCH_CAP_PER_HOUR`.
DENSE_PER_HOUR = 36.0
# NGUYÊN VĂN prompt đã đo (LLM_Train/music/seg_scenes.py SEG_PROMPT): đổi một chữ là đổi kết quả đã đo - tests/test_music_bounds.py
# so với băm của bản gốc; muốn đổi thì đổi PROMPT_VERSION và đo lại.
SEG_PROMPT = """Bạn chia một chương truyện thành các CẢNH để dựng nhạc nền sách nói. Mỗi dòng dưới đây là `số câu<TAB>câu`.
Cảnh mới bắt đầu khi đổi thời gian, đổi nơi chốn, đổi nhóm nhân vật đang được kể, hoặc mạch cảm xúc đổi rõ. Một cảnh thường dài 1-4
phút đọc (khoảng 30-120 câu); đừng cắt ở mỗi lượt thoại.
Trả lời đúng MỘT dòng JSON: {{"bat_dau": [các số câu BẮT ĐẦU một cảnh mới trong đoạn dưới, tăng dần]}}. Không viết gì khác.

ĐOẠN:
{text}"""
OPTIONS = {"temperature": 0, "num_ctx": 16384, "num_predict": 300}


def local_numbers(segments: list[dict[str, Any]]) -> list[int]:
    """Số câu mà model nhìn thấy cho từng câu: `seq` của câu trong chương (phép đo đọc cột `seq`), KHÔNG phải `id` (khoá DB cả cuốn).
    Chữ đọc theo chụp từ bản cũ (chương chờ thu lại) chưa mang `seq` thì đánh số theo vị trí từ 1 - vẫn ánh xạ ngược được."""
    seqs = [segment.get("seq") for segment in segments]
    if all(isinstance(seq, int) and not isinstance(seq, bool) for seq in seqs) and len(set(seqs)) == len(seqs):
        return list(seqs)
    return list(range(1, len(segments) + 1))


def windows(segments: list[dict[str, Any]]) -> list[str]:
    """Cửa sổ chữ gửi model: mỗi dòng `số câu<TAB>câu`, mỗi cửa sổ <= WINDOW ký tự, cửa sổ sau lấn OVERLAP ký tự của cửa sổ trước
    (đúng `seg_scenes.windows`)."""
    lines = [f"{local}\t{' '.join(str(segment.get('text') or '').split())}"
             for local, segment in zip(local_numbers(segments), segments)]
    out, start = [], 0
    while start < len(lines):
        size, end = 0, start
        while end < len(lines) and size + len(lines[end]) + 1 <= WINDOW:
            size += len(lines[end]) + 1
            end += 1
        end = max(end, start + 1)
        out.append("\n".join(lines[start:end]))
        if end >= len(lines):
            break
        back, size = end, 0
        while back > start + 1 and size < OVERLAP:
            back -= 1
            size += len(lines[back]) + 1
        start = back
    return out


def ask_window(base_url: str, text: str, *, session: Any = None) -> list[int]:
    """Một lượt hỏi: các số câu bắt đầu cảnh mới trong cửa sổ. Trả lời hỏng (không phải JSON, sai dạng) -> [] (cửa sổ ấy 0 ranh, như
    phép đo); Ollama không đáp được thì ném lỗi (để cả lượt tính dừng thay vì lần lượt hỏng từng cửa sổ)."""
    reply = music_moods._post(session, f"{base_url.rstrip('/')}/api/generate",
                              {"model": MODEL, "prompt": SEG_PROMPT.format(text=text), "stream": False, "think": False,
                               "format": "json", "options": dict(OPTIONS)}, 300)
    reply.raise_for_status()
    try:
        return [int(number) for number in json.loads(reply.json()["response"]).get("bat_dau", [])]
    except (ValueError, KeyError, TypeError, AttributeError):
        return []


def chapter_bounds(segments: list[dict[str, Any]], numbers: list[int]) -> list[int]:
    """Id các câu bắt đầu cảnh mới (theo thứ tự đọc, không trùng, bỏ câu đầu chương) từ các số câu model trả. Số không có trong chương
    thì bỏ."""
    by_number = {local: index for index, local in enumerate(local_numbers(segments))}
    positions = sorted({by_number[number] for number in numbers if number in by_number} - {0})
    return [segments[index].get("id") for index in positions]


def _read(project_root: Path) -> dict[str, Any] | None:
    try:
        value = json.loads((Path(project_root) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(value, dict) or value.get("version") != VERSION or value.get("prompt") != PROMPT_VERSION:
        return None
    chapters = value.get("chapters")
    if not isinstance(chapters, dict) or not all(isinstance(ids, list) for ids in chapters.values()):
        return None
    return value


def load(project_root: Path) -> dict[int, dict[str, dict[Any, str]]] | None:
    """Ranh giới LLM của dự án đúng dạng `music_scenes.book_scenes(boundaries=...)`: {chapterId: {"llm": {id câu bắt đầu cảnh: "llm"}}}.
    Sai phiên bản / prompt, hỏng, hay chưa có -> None (mọi chương chạy luật dấu hiệu)."""
    value = _read(project_root)
    if value is None:
        return None
    try:
        return {int(chapter): {"llm": {segment_id: "llm" for segment_id in ids}} for chapter, ids in value["chapters"].items()}
    except (ValueError, TypeError):  # khoá chương không phải số, id không băm được
        return None


def _density(script: dict[str, Any], ids: list[Any]) -> tuple[int, float]:
    """(số đoạn của chương khi dùng các ranh này, số đoạn mỗi giờ đọc)."""
    scenes = music_scenes.chapter_scenes(script, boundaries={"llm": {segment_id: "llm" for segment_id in ids}})
    hours = (scenes[-1]["end"] - scenes[0]["start"]) / 3600.0 if scenes else 0.0
    return len(scenes), (len(scenes) / hours if hours > 0 else 0.0)


def compute(project_root: Path, base_url: str, *, stop_requested: Callable[[], bool] = lambda: False,
            log: Callable[[str], None] = print, pause_requested: Callable[[], bool] = lambda: False,
            emit: Callable[[str, dict[str, Any]], None] = lambda _kind, _payload: None) -> int:
    """Hỏi LLM chia cảnh cho từng chương chưa có kết quả và ghi `music_bounds.json` sau MỖI chương. Cùng prompt và cùng digest model thì
    giữ chương đã có (làm tiếp được); khác thì làm lại cả cuốn. Một chương chỉ được ghi khi đủ mọi cửa sổ của nó (dừng giữa chương thì
    chương ấy chưa có file và dùng luật dấu hiệu). Trả số cửa sổ đã hỏi. `pause_requested`: nút "Tạm dừng" / gác pin - đứng chờ giữa
    hai cửa sổ; `stop_requested` thì trả về với phần đã xong."""
    from . import music_plan

    project_root = Path(project_root)
    digest = music_moods.model_digest(base_url)
    if digest is None:
        raise music_moods.MoodsUnavailable(f"Ollama chưa có model {MODEL}")
    old = _read(project_root)
    same = bool(old and old.get("digest") == digest)
    kept: dict[str, list[Any]] = old["chapters"] if same else {}
    scripts = list(music_plan.book_scripts(project_root))
    results: dict[str, list[Any]] = {}
    dense: dict[str, bool] = {str(chapter): True for chapter in (old.get("dense") or [])} if same else {}
    asked = 0

    def entries() -> dict[str, list[Any]]:
        # Theo thứ tự chương của sách; chương chưa tới lượt giữ nguyên kết quả cũ (cùng digest) để dừng giữa chừng không làm mất chúng.
        keys = [str(script.get("chapterId")) for script in scripts]
        merged = {key: results.get(key, kept.get(key)) for key in keys}
        return {key: ids for key, ids in merged.items() if ids is not None}

    def save() -> None:
        found = entries()
        atomic_write_json(project_root / FILE, {
            "version": VERSION, "prompt": PROMPT_VERSION, "model": MODEL, "digest": digest,
            "built": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "chapters": found,
            "dense": [int(key) for key in found if dense.get(key)]})

    for script in scripts:
        segments = [segment for segment in script.get("segments") or [] if isinstance(segment, dict)]
        chapter = script.get("chapterId")
        key = str(chapter)
        present = {segment.get("id") for segment in segments}
        fresh = not (key in kept and all(segment_id in present for segment_id in kept[key]))
        if fresh:
            ids: list[Any] = []
            if len(segments) > 1:
                numbers: list[int] = []
                for text in windows(segments):
                    while pause_requested() and not stop_requested():
                        time.sleep(1.0)
                    if stop_requested():
                        return asked
                    asked += 1
                    numbers += ask_window(base_url, text)
                ids = chapter_bounds(segments, numbers)
        else:
            ids = list(kept[key])
        results[key] = ids
        scenes, per_hour = _density(script, ids)
        dense[key] = per_hour > DENSE_PER_HOUR
        if fresh:
            log(f"Chia cảnh (LLM): chương {chapter} - {len(ids)} ranh LLM, {scenes} đoạn, {per_hour:.1f} đoạn/giờ đọc")
            if dense[key]:
                emit("music_bounds_dense", {"chapterId": chapter, "bounds": len(ids), "scenes": scenes, "perHour": round(per_hour, 1)})
            save()
    if not same or set(entries()) != set(kept):  # bỏ chương không còn trong sách, ghi digest mới; chạy lại không đổi gì thì để nguyên file
        save()
    return asked


def run_after_analysis(project_root: Path, base_url: str, stop_requested: Callable[[], bool],
                       log: Callable[[str], None], emit: Callable[[str, dict[str, Any]], None],
                       pause_requested: Callable[[], bool] = lambda: False) -> None:
    """Móc của dây chuyền sau pha phân tích: chia cảnh bằng LLM nếu người dùng đã tải model và nhạc nền của cuốn không tắt. KHÔNG dỡ
    model: `music_moods` chạy ngay sau (cùng model) và dỡ. Lỗi ném ra - worker hoãn tới sau các việc sau, dây chuyền chỉ ghi nhật ký."""
    from . import music_plan

    if music_moods.model_digest(base_url) is None or not music_plan.read_overrides(project_root)["enabled"]:
        return
    asked = compute(project_root, base_url, stop_requested=stop_requested, log=log, pause_requested=pause_requested, emit=emit)
    emit("music_bounds_done", {"asked": asked})
