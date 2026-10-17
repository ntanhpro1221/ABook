"""Nhạc nền THEO CẢNH cho sách chỉ có chữ nghe bằng "Nghe ngay" (máy tính). Đặc tả: Corpus research/music/SPEC_nnscene_app.md.

Sách chữ không có nhãn câu, nên đường Studio chạy trên kịch bản "trần": mỗi câu chỉ có `id`, `text`, `sceneBreak` (cờ của chính bộ tách
`text_processing.segment_chapter_text`) và `kind` ("heading" cho dòng tiêu đề, còn lại "narration") - không emotion / intensity nên mọi câu
trung tính. Từ đó `music_scenes.book_scenes` chia cảnh, `music_plan.build` chọn bài (cùng danh mục, cùng `book_key` theo cuốn). Số đo của đường
này nằm trong PLAN_nnscene.md mục 8; ĐỔI BƯỚC NÀO Ở ĐÂY cũng làm số ấy hết giá trị - muốn đổi thì đo lại.

Dựng từng chương, khi trình phát cần (không dựng cả cuốn trước): chương mới dựng với lịch sử là các chương liền trước ĐÃ dựng - truyền cho
`music_plan.build` như `keep` / `kept_siblings` (cơ chế sửa một đoạn của Studio), nên `music_select.choose` thấy đúng danh sách bài vừa dùng như
khi dựng một lần cả cuốn: dựng lần lượt từ chương đầu ra đúng plan của dựng một lần. Nhảy tới chương xa thì chương ấy dựng không lịch sử.

Cue mang `firstSegment` = mã ĐOẠN của màn đọc (`ui/src/listen/textScript.ts`, `readaloud/paragraphs.py`) nơi cảnh bắt đầu: trình phát đổi bài khi
đoạn ấy bắt đầu phát, không theo giây ước (xem `ui/src/listen/sceneCues.ts`). Mốc giây còn lại trong cue (bài anh em, bước âm lượng) là giây ƯỚC của
plan (`music_scenes._durations`), trình phát co giãn theo các mốc `firstSegment`.

Học sinh là NN-lite (`music_nnlite`, 2 MB đóng sẵn trong app, SPEC_nnlite_app): ranh cảnh LB + chỉnh V/E/T quanh mức chương LVJ; nếu model ấy không nạp
được thì bỏ bước ấy (đường "N0": `book_scenes(scripts, None, None, None)` -> `music_plan.build`). Đường này KHÔNG bao giờ dùng học sinh q06 (`music_scene_student`,
gói "Học sinh không khí cảnh" chỉ dành cho sách làm bằng Studio): q06 không có ranh LB lẫn LVJ nên nhạc sai màu rõ hơn (SPEC_nnscene_route.md).
Khoá đệm ghi học sinh nào đã dùng (`student_tag`), nên model đổi thì các chương chưa nghe dựng lại.

Dựng nền: `Builder` chạy MỘT luồng, chương đang nghe trước rồi vài chương kế; hỏi cue của chương chưa dựng xong thì
trình phát chưa có nhạc cho chương ấy (giọng không chờ) và hỏi lại sau."""
from __future__ import annotations

import bisect
import hashlib
import json
import threading
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterable

from .. import text_processing
from ..io_utils import atomic_write_json
from ..readaloud import paragraphs
from . import humanize, music_plan, music_playlist, music_scenes, music_select

SCENE = music_playlist.SCENE  # `music.playlist` của lớp sửa: người nghe chọn "Theo cảnh (máy tự dựng)"
SEGMENTER_VERSION = 1  # đổi khi cách tách câu / ánh xạ sang đoạn đổi: plan đã dựng không dùng lại
FORMAT_VERSION = 2  # 2: plan cũ có thể chọn bài quá cỡ (cỡ chỉ có ở mảnh tracks/ của danh mục, ô cells/ không có)

# Chỗ cắm học sinh (không bắt buộc): hàm (kịch bản, đoạn nền) -> các mục `dV/dE/dT/chapterV` cho `music_scenes.book_scenes(student=...)`, hay None.
StudentItems = Callable[[dict[str, Any], list[dict[str, Any]]], "list[dict[str, Any]] | None"]
# Nguồn ranh cảnh "lite" (không bắt buộc, chỉ đường NN-lite): hàm kịch bản -> {id câu mở cảnh mới: lý do}, `music_nnlite.scene_bounds` (LB, SPEC_lb_app).
SceneBounds = Callable[[dict[str, Any]], "dict[Any, str]"]
LITE_SOURCE = "lite"
AHEAD_CHAPTERS = 3  # chương dựng trước chỗ đang nghe
BUILD_WAIT_SECONDS = 2.0  # hỏi cue chương chưa dựng: chờ chừng này (chương nhẹ dựng kịp), rồi trả "chưa có"
VERIFY_ROUNDS = 12  # trần số lần chọn lại một chương vì bài quá cỡ (mỗi vòng loại thêm ít nhất một bài; hết vòng thì giữ lần chọn cuối - tải sẽ bị chặn và chọn lại)


# ---- câu của chương + đoạn của màn đọc ------------------------------------------------------------------------------------------
def chapter_script(chapter_id: int, title: str, text: str, skip: Iterable[str] | None = None) -> tuple[dict[str, Any], list[int]]:
    """(kịch bản trần, mã đoạn màn đọc của từng câu) cho chữ một chương, đúng đường đo: câu của `segment_chapter_text` trên chữ đã bỏ các dòng
    người nghe chọn bỏ (`skip`), mỗi câu chỉ `id` (số thứ tự), `text`, `kind` và `sceneBreak` khi bộ tách đặt cờ."""
    body = paragraphs.without_lines(text, list(skip or ()))
    rows = text_processing.segment_chapter_text(chapter_id, body)
    segments = []
    for index, row in enumerate(rows):
        segments.append({"id": int(row["seq"]), "text": str(row["text"]),
                         "kind": "heading" if index == 0 and humanize.is_heading(str(row["text"])) else "narration",
                         **({"sceneBreak": True} if row.get("scene_break") else {})})
    return {"chapterId": chapter_id, "title": title, "segments": segments}, paragraph_ids([s["text"] for s in segments], body)


def _letters(text: str) -> int:
    return sum(1 for char in text if unicodedata.category(char)[0] in "LN")


def paragraph_ids(sentences: list[str], body: str) -> list[int]:
    """Với mỗi câu: mã đoạn của màn đọc (chỉ số trong `paragraphs.split_paragraphs(body)`, cũng là `id` của `textScript`) chứa chỗ câu bắt đầu.
    Hai bên cùng đọc một chữ nên tổng số chữ cái / chữ số tới một chỗ bằng nhau; lệch nhẹ (ký tự đặc biệt) thì co theo tỉ lệ."""
    pieces = paragraphs.split_paragraphs(body)
    if not pieces:
        return [0] * len(sentences)
    starts, total = [], 0
    for piece in pieces:
        starts.append(total)
        total += _letters(piece.text)
    spoken = sum(_letters(text) for text in sentences)
    scale = total / spoken if spoken and total else 1.0
    out, seen = [], 0
    for text in sentences:
        out.append(max(0, bisect.bisect_right(starts, round(seen * scale)) - 1))
        seen += _letters(text)
    return out


# ---- một chương ----------------------------------------------------------------------------------------------------------------
def chapter_scenes(script: dict[str, Any], student: StudentItems | None = None, bounds: SceneBounds | None = None) -> list[dict[str, Any]]:
    """Các đoạn nhạc của chương (ranh giới của app trên kịch bản trần). MỘT chỗ gọi `music_scenes.book_scenes`: có `student` thì chỉnh V/E/T
    quanh mức chương đúng như Studio, không thì không (hay `student` trả None: chương không dùng được).
    Sách chữ không có nhãn câu nên đoạn của học sinh có `confidence` thấp và bộ chọn kéo hết về đích êm; sàn `WEAK_MOOD` (NN-V, SPEC_nnv_app) cho
    V / E của học sinh tới bộ chọn bài. CHỈ ở đường này: Studio (sách có nhãn câu) và N0 (không đoạn `moodSource` = "student") giữ nguyên.
    `bounds` (chỉ đường NN-lite, LB): thêm nguồn ranh "lite" ({id: "mood_shift"}) vào đoạn nền TRƯỚC khi học sinh chạy, nên học sinh đoán trên các đoạn mới; "cue" thắng khi trùng chỗ.
    Học sinh không dùng được chương (None) thì chương đi đường N0 nguyên, không ranh LB."""
    lite = {LITE_SOURCE: bounds(script)} if student is not None and bounds is not None else None
    boundaries = {script.get("chapterId"): lite} if lite else None
    items = student(script, music_scenes.book_scenes([script], None, boundaries, None)) if student is not None else None
    if items is None:
        boundaries = None
    scenes = music_scenes.book_scenes([script], None, boundaries, items)
    return [dict(s, confidence=max(float(s.get("confidence") or 0.0), music_select.WEAK_MOOD)) if s.get("moodSource") == "student" else s
            for s in scenes]


class SceneBook:
    """Plan nhạc theo cảnh của MỘT cuốn, mỗi chương một file trong thư mục đệm `directory` (khoá `key` nằm trong tên thư mục con: đổi khoá là
    dựng lại từ đầu, thư mục khoá cũ bị bỏ)."""

    def __init__(self, directory: Path, key: dict[str, Any]) -> None:
        digest = hashlib.sha1(json.dumps({**key, "segmenter": SEGMENTER_VERSION, "format": FORMAT_VERSION}, sort_keys=True).encode()).hexdigest()[:12]
        self.root = Path(directory)
        self.directory = self.root / digest
        self.lock = threading.RLock()
        if self.root.is_dir():
            for old in self.root.iterdir():
                if old.is_dir() and old.name != digest:
                    for file in old.glob("*.json"):
                        file.unlink(missing_ok=True)
                    try:
                        old.rmdir()
                    except OSError:
                        pass

    def _file(self, chapter_id: int) -> Path:
        return self.directory / f"{int(chapter_id)}.json"

    def read(self, chapter_id: int, text_sha: str | None = None) -> dict[str, Any] | None:
        """Bản ghi đã dựng của chương, hay None (chưa dựng, hỏng, hay chữ chương đã đổi so với `text_sha`)."""
        try:
            record = json.loads(self._file(chapter_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(record, dict) or (text_sha is not None and record.get("textSha") != text_sha):
            return None
        return record

    def write(self, record: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._file(record["chapterId"]), record)

    def discard(self, chapter_id: int) -> None:
        """Bỏ bản ghi của chương (dựng lại lần hỏi kế)."""
        with self.lock:
            self._file(chapter_id).unlink(missing_ok=True)

    def history(self, order: list[int], chapter_id: int, sha_of: Callable[[int], str | None]) -> list[dict[str, Any]]:
        """Các chương liền trước `chapter_id` đã dựng (liền một mạch, theo thứ tự sách), vừa đủ cho cửa sổ "bài vừa dùng" của `music_select.choose`
        (`RECENT_SCENES` lần đổi bài). Chương liền trước chưa dựng thì không có lịch sử."""
        if chapter_id not in order:
            return []
        found: list[dict[str, Any]] = []
        for previous in reversed(order[:order.index(chapter_id)]):
            record = self.read(previous, sha_of(previous))
            if record is None:
                break
            found.insert(0, record)
            runs: list[str] = []
            for scene in (scene for part in found for scene in part["scenes"]):
                if scene.get("link") and (not runs or runs[-1] != scene["link"]):
                    runs.append(scene["link"])
            if len(runs) > music_select.RECENT_SCENES:
                break
        return found


def build_chapter(book: SceneBook, order: list[int], chapter_id: int, title: str, text: str, skip: Iterable[str] | None, *,
                  sha_of: Callable[[int], str], near: Callable[[float, float], Iterable[dict[str, Any]]],
                  lookup: Callable[[list[str]], dict[str, dict[str, Any]]], catalog_revision: str | None, taxonomy: dict[str, Any] | None,
                  book_key: str, available: Callable[[str], bool] | None = None,
                  verify: Callable[[list[str]], bool] | None = None, student: StudentItems | None = None,
                  bounds: SceneBounds | None = None) -> dict[str, Any]:
    """Dựng (hay lấy lại) plan của một chương. Chữ đã tách nằm trong bản ghi (chữ không đổi thì khỏi tách lại).
    `available` chỉ được dùng thứ ĐÃ BIẾT (bộ chọn hỏi hàng trăm bài xếp hạng - tra cỡ từng bài là tải hàng trăm mảnh danh mục). `verify(links)`: sau mỗi lần
    chọn, tra cỡ các bài ĐÃ CHỌN (đầu cảnh + bài anh em) trong MỘT lượt; True khi vừa phát hiện bài nào máy này không dùng (quá cỡ) - `available` từ đó loại nó,
    chọn lại chương cho tới khi không còn bài nào bị loại (mỗi vòng thêm ít nhất một bài vào sổ nên dừng)."""
    sha = sha_of(chapter_id)
    with book.lock:
        record = book.read(chapter_id, sha)
        if record is not None:
            return record
        script, paragraph = chapter_script(chapter_id, title, text, skip)
        scenes = chapter_scenes(script, student, bounds)
        previous = book.history(order, chapter_id, sha_of)
        before = [scene for part in previous for scene in part["scenes"]]
        history = {"scenes": before} if before else None
        for _ in range(VERIFY_ROUNDS):
            plan = music_plan.build(
                book.directory, near, lookup, catalog_revision=catalog_revision, book_key=book_key, taxonomy=taxonomy,
                scenes=(music_plan.scenes_of(history) or []) + scenes,
                keep=music_plan.kept_tracks(history) if history else None, kept_siblings=music_plan.kept_siblings(history) if history else None,
                available=available, persist=False)
            chosen = [scene for scene in plan["scenes"] if scene.get("chapterId") == chapter_id]
            if verify is None or not verify(chosen_links(chosen)):
                break
        by_sentence = {segment["id"]: paragraph[index] for index, segment in enumerate(script["segments"])}
        for scene in chosen:
            scene["paragraph"] = by_sentence.get(scene.get("firstSegment"), 0)
        record = {"version": FORMAT_VERSION, "chapterId": chapter_id, "textSha": sha, "segments": len(script["segments"]),
                  "seconds": round(sum(music_scenes._durations(script["segments"])), 3), "scenes": chosen,
                  "tracks": {link: plan["tracks"].get(link) or {} for link in plan["tracks"] if any(
                      scene.get("link") == link or any(s["link"] == link for s in scene.get("siblings") or []) for scene in chosen)}}
        book.write(record)
        return record


def chosen_links(scenes: Iterable[dict[str, Any]]) -> list[str]:
    """Các bài một chương đã chọn dùng: đầu cảnh + bài anh em (không trùng, theo thứ tự gặp)."""
    found: dict[str, None] = {}
    for scene in scenes:
        for link in [scene.get("link")] + [sibling["link"] for sibling in scene.get("siblings") or []]:
            if link:
                found[link] = None
    return list(found)


def chapter_cues(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Mốc nhạc của chương cho trình phát (giây ƯỚC, `music_plan.chapter_cues`), mốc mở một cảnh mang `firstSegment` = mã đoạn màn đọc nơi cảnh
    bắt đầu; mốc nối bài anh em không có (trình phát co giãn theo mốc đoạn gần nhất)."""
    plan = {"enabled": True, "scenes": record["scenes"]}
    cues = music_plan.chapter_cues(plan, int(record["chapterId"]), float(record["seconds"]))
    heads = {scene["key"]: scene.get("paragraph", 0) for scene in record["scenes"]}
    for cue in cues:
        if not cue.get("sibling") and cue["key"] in heads:
            cue["firstSegment"] = heads[cue["key"]]
    return cues


def text_sha(text: str, skip: Iterable[str] | None) -> str:
    """Mã băm chữ chương sau khi bỏ dòng `skip` (đổi chữ hay dòng bỏ thì plan chương ấy dựng lại)."""
    return hashlib.sha1(paragraphs.without_lines(text, list(skip or ())).encode("utf-8")).hexdigest()


def scene_dir_name(book_id: str) -> str:
    return hashlib.sha1(book_id.encode("utf-8")).hexdigest()[:16]


def student_tag(lite_sha: str | None) -> str:
    """Phần khoá đệm nói học sinh nào đã dựng plan: "nnlite-lvj1-<mã model>" (NN-lite, music_nnlite.py; lvj1: ranh cảnh LB `music_nnlite.scene_bounds` + mức chương LVJ; plan dựng trước LVJ hay bằng q06 không dùng lại), hay "none" khi model không nạp được (đường N0)."""
    return f"nnlite-lvj1-{lite_sha}" if lite_sha else "none"


class Builder:
    """Hàng đợi dựng nền, MỘT luồng: việc nhỏ số ưu tiên đi trước (chương đang nghe 0, các chương kế 1, 2, ...). Việc cùng (cuốn, chương) chỉ chạy một
    lần. `cancel(book)` bỏ việc chưa chạy của cuốn (đóng cuốn, đổi cuốn) và báo `stop` cho việc đang chạy."""

    class Task:
        def __init__(self, book: str, chapter: int, priority: int, job: Callable[[Callable[[], bool]], None]) -> None:
            self.book, self.chapter, self.priority, self.job = book, chapter, priority, job
            self.done = threading.Event()
            self.cancelled = False
            self.error: BaseException | None = None

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: list[Builder.Task] = []
        self._running: Builder.Task | None = None
        self._thread: threading.Thread | None = None

    def submit(self, book: str, chapter: int, priority: int, job: Callable[[Callable[[], bool]], None]) -> "Builder.Task":
        with self._lock:
            for task in (*self._tasks, *([self._running] if self._running else [])):
                if task.book == book and task.chapter == chapter and not task.cancelled:
                    task.priority = min(task.priority, priority)
                    return task
            task = Builder.Task(book, chapter, priority, job)
            self._tasks.append(task)
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="music-scene-builder", daemon=True)
                self._thread.start()
            return task

    def cancel(self, book: str | None = None) -> None:
        """Bỏ việc của `book` (None: mọi cuốn): chưa chạy thì xoá, đang chạy thì báo dừng."""
        with self._lock:
            for task in (*self._tasks, *([self._running] if self._running else [])):
                if book is None or task.book == book:
                    task.cancelled = True
            for task in [task for task in self._tasks if task.cancelled]:
                self._tasks.remove(task)
                task.done.set()

    def cancel_others(self, book: str) -> None:
        """Đang nghe cuốn `book`: việc nền của cuốn khác không còn ai chờ."""
        with self._lock:
            others = {task.book for task in (*self._tasks, *([self._running] if self._running else [])) if task.book != book}
        for other in others:
            self.cancel(other)

    def idle(self) -> bool:
        with self._lock:
            return not self._tasks and self._running is None

    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._tasks:
                    self._thread = None
                    break
                task = min(self._tasks, key=lambda item: item.priority)
                self._tasks.remove(task)
                self._running = task
            try:
                if not task.cancelled:
                    task.job(lambda: task.cancelled)
            except BaseException as error:  # noqa: BLE001 - việc nền: lỗi là "chưa có nhạc cho chương này", không làm sập luồng
                task.error = error
            finally:
                with self._lock:
                    self._running = None
                task.done.set()
