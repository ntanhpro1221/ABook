"""Làm tiếp cuốn này: dự án nối tiếp dự án trước của cùng một cuốn (truyện dài làm nhiều đợt), gieo từ dự án ấy.

Truyện mạng dài - vài trăm tới vài nghìn chương, còn ra tiếp - không làm một lần được, nên mỗi đợt là một dự án. Dự án
mới mà không biết gì về dự án trước thì mất những thứ người nghe đã quen: giọng từng nhân vật (bộ cấp giọng xếp hạng theo
đúng nhóm nhân vật dự án ấy tình cờ thấy, nên cùng một người có thể nhận giọng khác), cách đọc tên (tên không chắc đọc
khác đi giữa hai lần chạy, và cách đọc người nghe đã chọn mất), ghim giới/tuổi, và danh sách "nhân vật đã biết" mà prompt
phân tích mở đầu bằng nó (đo trên cuốn 2: từ lô hai trở đi 80% tên riêng của một lô đã xuất hiện ở lô trước, lô chín 95%).

Cuốn 2 đi qua 19 lô bằng các script vận hành - `scripts/port_pronunciations.py`, `port_casting.py`,
`seed_listener_acceptances.py`, `backfill_exposure.py`, gọi từ `launch_batch.sh`. Module này là đúng các bước ấy đưa vào
lõi cho Studio (nút "Làm tiếp cuốn này") và `cli create --seed-from`: app cài đặt chỉ mang `abook`, không mang
`scripts/`. Số đo gốc của từng luật nằm trong docstring của script tương ứng; ở đây chỉ nhắc lại cái cần để đọc code.

Hai giới hạn cứng:

- Chỉ gieo GIỮA `create` và `run`: dự án đích đã phân tích thì đổi cách đọc tên là làm trôi chữ nói dưới audio đã có.
- Dự án nguồn chỉ được ĐỌC (sqlite `mode=ro`): nó có thể đang chạy, và `ProjectDB(...)` ghi schema ngay khi mở.

Dự án nối tiếp ghi `continues.json` (dự án trước + số phần), để lần "làm tiếp" sau đi được cả chuỗi và thư viện nghe gộp
được các phần về một cuốn.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

from . import aliases, bracket_rule
from .database import LISTENER_PRONUNCIATION_SOURCE, ProjectDB
from .io_utils import discover_txt_files, natural_key
from . import names as renames

DB_NAME = "project.sqlite3"
LINK_FILE = "continues.json"
# Sổ cộng dồn: số câu mỗi nhân vật đã nói qua MỌI phần - `upsert_character` ghi đè `mention_count` bằng số của riêng dự
# án hiện tại. `character_registry._book_exposure` đọc nó khi cấp giọng; DDL giống hệt `scripts/backfill_exposure.py`.
LEDGER_TABLE = "character_exposure"
LEDGER_DDL = f"""
CREATE TABLE IF NOT EXISTS {LEDGER_TABLE} (
    canonical_name TEXT PRIMARY KEY,
    dialogue_lines INTEGER NOT NULL,
    batches INTEGER NOT NULL,
    updated_at REAL NOT NULL
)
"""
# "Tên · Phần 2": cùng quy ước "Tên · Tập 16" mà thư viện nghe gom thành bộ (ui/src/listen/model.ts `seriesOf`) - phần sau
# đứng cạnh phần đầu và được mời nghe tiếp khi phần trước hết. Bỏ được cả hậu tố cũ "(phần 2)".
PART_SUFFIX = re.compile(r"\s*(?:\(phần\s*\d+\)|[·|:—–-]\s*phần\s*\d+)\s*$", re.IGNORECASE)

SPOKE_HERE_SQL = """
    SELECT c.canonical_name AS canonical_name, v.*,
           sum(s.kind = 'dialogue') AS lines_here,
           max(c.mention_count) AS mentions_here
    FROM characters c
    JOIN segments s ON s.canonical_character_id = c.id
    JOIN voice_profiles v ON v.id = s.voice_profile_id
    GROUP BY c.id, v.id
    ORDER BY c.canonical_name
"""
PINNED_SQL = """
    SELECT DISTINCT c.canonical_name AS canonical_name, v.*,
           c.mention_count AS mentions_here
    FROM characters c
    JOIN voice_profiles v ON v.voice_key = c.locked_voice_key
    WHERE c.locked_voice_key <> ''
    ORDER BY c.canonical_name
"""

Log = Callable[[str], None]


class ContinuationError(ValueError):
    """Không gieo được; lời nhắn viết cho người dùng đọc."""


class _SeedingDB(ProjectDB):
    """ProjectDB mà mọi phép ghi trong `batch()` đi chung MỘT kết nối, MỘT giao dịch.

    Mỗi phép ghi của ProjectDB tự mở kết nối (ba PRAGMA), commit rồi đóng - và kết nối cuối đóng thì SQLite dồn WAL vào
    file. Bản sao lô 18 (cuốn 2: 1.136 cách đọc, 644 nhân vật, 119 giọng) là hơn 4.000 lần mở: 38 giây cho một lần bấm.
    Chung một giao dịch thì nhanh, và lượt gieo thành nguyên tử - hỏng giữa chừng là không ghi gì, dự án vẫn như lúc vừa
    tạo. Vẫn gọi đúng các phương thức của ProjectDB (luật khoá giới, khoá cách đọc... nằm ở đó), chỉ đổi đường kết nối:
    chúng đều đi qua `connect()`/`transaction()`, không tự BEGIN/COMMIT.
    """

    _shared: sqlite3.Connection | None = None

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if self._shared is not None:
            yield self._shared
            return
        with super().connect() as connection:
            yield connection

    @contextmanager
    def transaction(self, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        if self._shared is not None:
            yield self._shared
            return
        with super().transaction(immediate) as connection:
            yield connection

    @contextmanager
    def batch(self) -> Iterator[None]:
        with super().transaction() as connection:
            self._shared = connection
            try:
                yield
            finally:
                self._shared = None


def _quiet(_message: str) -> None:
    return None


def is_project(path: Path) -> bool:
    return (Path(path) / DB_NAME).is_file()


def _read_only(project: Path) -> sqlite3.Connection:
    # `as_uri` mã hoá dấu cách, '#', '%'... trong đường dẫn thư viện - chuỗi ghép tay thì hỏng ở đó.
    connection = sqlite3.connect(f"{(Path(project) / DB_NAME).resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _rows(connection: sqlite3.Connection, sql: str, *params: Any) -> list[sqlite3.Row]:
    """Dự án cũ hơn một bảng/cột thì không có gì để mang - không phải lỗi."""
    try:
        return list(connection.execute(sql, params))
    except sqlite3.OperationalError:
        return []


def analysed_segments(project: Path) -> int:
    """Số đoạn đã qua phân tích. Khác 0 là quá muộn để gieo."""
    with closing(_read_only(project)) as connection:
        rows = _rows(connection, "SELECT COUNT(*) FROM segments WHERE status <> 'pending'")
    return int(rows[0][0]) if rows else 0


# ---- chuỗi các phần ----------------------------------------------------------------------------------------------


def _link(project: Path) -> dict[str, Any]:
    try:
        data = json.loads((Path(project) / LINK_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def previous_project(project: Path) -> Path | None:
    """Dự án mà `project` làm tiếp, hoặc None (phần đầu, hay dự án trước đã bị xoá/dời)."""
    value = str(_link(project).get("previous") or "")
    if not value:
        return None
    # Ghi tương đối với thư mục thư viện khi hai dự án cùng thư viện: dời cả thư viện vẫn nối được.
    candidate = Path(value) if Path(value).is_absolute() else Path(project).resolve().parent / value
    return candidate.resolve() if is_project(candidate) else None


def part_number(project: Path) -> int:
    try:
        return max(1, int(_link(project).get("part") or 1))
    except (TypeError, ValueError):
        return 1


def chain_of(project: Path) -> list[Path]:
    """Các phần của cuốn tới `project`, phần đầu trước. Dừng ở vòng lặp hay mắt xích mất."""
    chain = [Path(project).resolve()]
    while True:
        previous = previous_project(chain[0])
        if previous is None or previous in chain:
            return chain
        chain.insert(0, previous)


def series_of(project: Path) -> tuple[Path, int] | None:
    """Phần nối tiếp (phần 2 trở đi) -> (phần đầu, thứ tự phần theo chuỗi `continues.json`); phần đầu hay dự án lẻ: None -
    giao diện tự nhận phần đầu là sách mà phần khác trỏ về. Danh sách Dự án và Thư viện nghe gom các phần theo chuỗi này,
    không theo tên (soát UX 29-09, N10: đổi tên một phần làm mất nhóm trong khi "Làm tiếp" vẫn nối; dự án lạ tên
    "X · Phần 2" bị gom vào X). Chỉ đọc vài file continues.json ngược về phần đầu - không quét cả thư viện."""
    chain = chain_of(project)
    return (chain[0], len(chain)) if len(chain) > 1 else None


def _write_link(source: Path, target: Path) -> None:
    try:
        previous = os.path.relpath(source, target.parent) if source.parent == target.parent else str(source)
    except ValueError:  # hai ổ đĩa khác nhau trên Windows
        previous = str(source)
    payload = {"previous": Path(previous).as_posix(), "part": part_number(source) + 1, "seededAt": time.time()}
    temporary = target / f".{LINK_FILE}.tmp"
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, target / LINK_FILE)


def base_title(title: str) -> str:
    """Tên cuốn không có hậu tố phần ("Tên · Phần 2" -> "Tên")."""
    return PART_SUFFIX.sub("", str(title)).strip() or str(title).strip()


def continued_title(title: str, part: int) -> str:
    """"Tên · Phần 3" cho phần kế tiếp, không chồng hậu tố cũ."""
    return f"{base_title(title)} · Phần {part}"


def latest_part(project: Path, candidates: Iterable[Path]) -> Path:
    """Phần mới nhất của cuốn mà `project` thuộc về, trong số `candidates` (các dự án của thư viện): chuỗi dài nhất đi qua
    `project`. Bấm "Làm tiếp" ở phần 1 khi đã có phần 2 thì phải nối từ phần 2 - không thì phần mới làm lại đúng các
    chương phần 2 đã làm. Không phần nào nối sau thì là chính nó."""
    here = Path(project).resolve()
    best, length = here, len(chain_of(here))
    for candidate in candidates:
        try:
            chain = chain_of(candidate)
        except OSError:
            continue
        if here in chain and len(chain) > length:
            best, length = chain[-1], len(chain)
    return best


def series_parts(project: Path, candidates: Iterable[Path]) -> list[Path]:
    """Mọi phần của cuốn mà `project` thuộc về, phần đầu trước: lần ngược `previous` về phần 1, rồi đi xuôi theo các dự án
    của thư viện (`candidates`) nối tiếp nó - chuỗi dài nhất đi qua `project` (`latest_part`). Phần lẻ: chỉ chính nó."""
    here = Path(project).resolve()
    chain = chain_of(latest_part(here, candidates))
    return chain if here in chain else chain_of(here)


def _input_paths(project: Path) -> list[Path]:
    with closing(_read_only(project)) as connection:
        return [Path(str(row[0])) for row in _rows(connection, "SELECT input_path FROM chapters ORDER BY chapter_index")
                if row[0]]


def next_chapters(project: Path) -> list[Path]:
    """Các file .txt kế tiếp sau chương cuối đã làm của cả chuỗi, theo thứ tự thư mục (như trình tạo sách xếp).

    Chỉ lấy file ĐỨNG SAU chương cuối: chương đứng trước chương đầu (lời tựa, chương bỏ qua) là người dùng đã không chọn.
    """
    done: set[Path] = set()
    folders: list[Path] = []
    for part in chain_of(project):
        for path in _input_paths(part):
            done.add(path.resolve())
            if path.parent.is_dir() and path.parent.resolve() not in folders:
                folders.append(path.parent.resolve())
    files = sorted({found.resolve() for folder in folders for found in discover_txt_files(folder)},
                   key=lambda path: natural_key(path.name))
    last = max((index for index, path in enumerate(files) if path in done), default=-1)
    return [path for path in files[last + 1:] if path not in done]


# ---- tên: gộp cách viết của cùng một người ------------------------------------------------------------------------


def _source_text(connection: sqlite3.Connection) -> str:
    """Như `character_registry._source_text`, qua kết nối chỉ-đọc: mọi .txt cùng thư mục với các chương."""
    paths = {Path(str(row[0])) for row in _rows(connection, "SELECT input_path FROM chapters") if row[0]}
    folders = {path.parent for path in paths if path.parent.is_dir()}
    files = sorted({found for folder in folders for found in folder.glob("*.txt")})
    chunks: list[str] = []
    for path in files or sorted(path for path in paths if path.is_file()):
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(chunks)


def _present(name: str, folded_source: str) -> bool:
    """`character_registry.source_occurrences(name) > 0`, dừng ở chỗ khớp NGUYÊN CHỮ đầu tiên thay vì đếm hết."""
    from .character_registry import fold_for_source_search

    needle = fold_for_source_search(name).strip()
    if not needle or not folded_source:
        return False
    start, width, size = 0, len(needle), len(folded_source)
    while True:
        index = folded_source.find(needle, start)
        if index < 0:
            return False
        end = index + width
        if (index == 0 or not folded_source[index - 1].isalnum()) and (end == size or not folded_source[end].isalnum()):
            return True
        start = index + 1


def _fold_to_book_spelling(names: list[str], folded_source: str, weight: dict[str, int],
                           presence: dict[str, bool] | None = None) -> dict[str, str]:
    """`character_registry.fold_to_source_spelling` cho ra CÙNG kết quả, trên phần tên có thể đổi kết quả.

    Luật ấy chỉ trỏ tên VẮNG khỏi sách, và chỉ về tên có mặt lệch nó một-hai ký tự; nhưng nó đếm mọi lần xuất hiện của
    MỌI tên trong cả cuốn - trên bản sao lô 18 (cuốn 2, ~640 nhân vật) mất 9 giây, gần hết thời gian gieo sau phần ghi.
    Nên: không tên nào vắng thì không có gì để trỏ; có thì chỉ đưa vào tên vắng + mọi tên có thể là ứng viên của chúng
    (lệch một/hai ký tự, hay lệch một với chữ đầu) - kể cả điều kiện "một đích duy nhất" của luật lệch hai vẫn xét trên
    đúng tập ứng viên ấy."""
    from .character_registry import (
        _within_one_edit,
        _within_two_edits,
        fold_for_source_search,
        fold_to_source_spelling,
    )

    if not folded_source:
        return {}  # không đọc được sách thì luật tự tắt, như `fold_to_source_spelling`
    presence = {} if presence is None else presence
    for name in names:
        if name not in presence:
            presence[name] = _present(name, folded_source)
    absent = [fold_for_source_search(name).strip() for name in names if not presence[name]]
    if not absent:
        return {}
    firsts = [text.split()[0] for text in absent if text.split()]

    def related(name: str) -> bool:
        text = fold_for_source_search(name).strip()
        return text in absent or any(_within_one_edit(other, text) or _within_two_edits(other, text) for other in absent)             or any(_within_one_edit(first, text) for first in firsts)

    return fold_to_source_spelling([name for name in names if related(name)], folded_source, weight)


def _fold_names(names: list[str], folded_source: str, weight: dict[str, int] | None = None,
                presence: dict[str, bool] | None = None) -> dict[str, str]:
    """{tên thua: tên thắng} theo hai luật của sổ nhân vật, hợp thành: rơi dấu trước (bản nhiều dấu thắng - THU LÃNH về
    THỦ LÃNH), rồi cách viết có trong sách thắng cách viết không có (SELNE về Selene). Hợp thành chứ không gộp hai dict:
    A -> B theo dấu rồi B -> C theo sách thì A phải về C."""
    from .character_registry import merge_dropped_mark_variants

    weight = dict(weight or {})
    by_marks = merge_dropped_mark_variants({name: name for name in names}, Counter(weight))
    survivors = [name for name in names if name not in by_marks]
    by_source = _fold_to_book_spelling(survivors, folded_source, weight, presence)
    folded: dict[str, str] = {}
    for name in names:
        winner = name
        for _ in range(len(names) + 1):
            following = by_marks.get(winner) or by_source.get(winner)
            if not following or following == winner:
                break
            winner = following
        if winner != name:
            folded[name] = winner
    return folded


# ---- sổ cộng dồn -------------------------------------------------------------------------------------------------


def _dialogue_lines_by_chapter(connection: sqlite3.Connection) -> dict[str, Counter[str]]:
    """{tiêu đề chương: {tên: số câu thoại}}, đã gộp cách viết rơi dấu. Theo tiêu đề vì id chương là của riêng dự án."""
    from .character_registry import merge_dropped_mark_variants

    raw: dict[str, dict[str, int]] = {}
    for row in _rows(
        connection,
        """
        SELECT ch.title AS title, c.canonical_name AS name, count(*) AS n
        FROM segments s
          JOIN characters c ON c.id = s.canonical_character_id
          JOIN chapters ch ON ch.id = s.chapter_id
        WHERE s.kind = 'dialogue'
          AND c.canonical_name NOT LIKE 'NPC/_%' ESCAPE '/'
          AND upper(c.canonical_name) NOT LIKE 'ANONYMOUS%'
        GROUP BY ch.id, c.id
        """,
    ):
        raw.setdefault(str(row["title"]), {})[str(row["name"])] = int(row["n"])
    by_title: dict[str, Counter[str]] = {}
    for title, counts in raw.items():
        folded = merge_dropped_mark_variants({name: name for name in counts}, Counter(counts))
        merged: Counter[str] = Counter()
        for name, lines in counts.items():
            merged[folded.get(name, name)] += lines
        by_title[title] = merged
    return by_title


def _read_ledger(connection: sqlite3.Connection) -> dict[str, tuple[int, int]]:
    return {
        str(row[0]): (int(row[1] or 0), int(row[2] or 0))
        for row in _rows(connection, f"SELECT canonical_name, dialogue_lines, batches FROM {LEDGER_TABLE}")
    }


def book_exposure(chain: list[Path]) -> dict[str, tuple[int, int]]:
    """{tên: (số câu, số phần có tên ấy)} qua cả chuỗi, mỗi chương đếm MỘT lần (phần sau thắng, như khi ghép sách).

    Gộp với sổ sẵn có của phần cuối bằng max từng tên: dự án của dây chuyền lô mang sổ tính từ những lô mà chuỗi
    `continues.json` không biết tới. Lấy max chứ không cộng, để không bao giờ đếm đôi.
    """
    from .character_registry import merge_dropped_mark_variants

    winners: dict[str, tuple[int, Counter[str]]] = {}
    ledger: dict[str, tuple[int, int]] = {}
    for index, project in enumerate(chain):
        with closing(_read_only(project)) as connection:
            for title, counts in _dialogue_lines_by_chapter(connection).items():
                winners[title] = (index, counts)
            if index == len(chain) - 1:
                ledger = _read_ledger(connection)
    total: Counter[str] = Counter()
    parts: dict[str, set[int]] = {}
    for index, counts in winners.values():
        for name, lines in counts.items():
            total[name] += lines
            parts.setdefault(name, set()).add(index)
    # Gộp lần nữa TRÊN tổng: hai phần có thể viết cùng một tên theo hai cách.
    folded = merge_dropped_mark_variants({name: name for name in total}, total)
    exposure: dict[str, tuple[int, int]] = {}
    seen: dict[str, set[int]] = {}
    for name, lines in total.items():
        winner = folded.get(name, name)
        exposure[winner] = (exposure.get(winner, (0, 0))[0] + lines, 0)
        seen.setdefault(winner, set()).update(parts[name])
    exposure = {name: (lines, len(seen[name])) for name, (lines, _parts) in exposure.items()}
    for name, (lines, batches) in ledger.items():
        mine = exposure.get(name, (0, 0))
        exposure[name] = (max(mine[0], lines), max(mine[1], batches))
    return exposure


def _write_ledger(target: ProjectDB, exposure: dict[str, tuple[int, int]]) -> None:
    now = time.time()
    with target.transaction() as connection:
        connection.execute(LEDGER_DDL)  # `execute`, không `executescript`: cái sau tự COMMIT giao dịch đang mở
        connection.execute(f"DELETE FROM {LEDGER_TABLE}")
        connection.executemany(
            f"INSERT INTO {LEDGER_TABLE} (canonical_name, dialogue_lines, batches, updated_at) VALUES (?,?,?,?)",
            [(name, int(lines), int(batches), now) for name, (lines, batches) in sorted(exposure.items())],
        )


# ---- cách đọc tên ------------------------------------------------------------------------------------------------


def seed_pronunciations(source: sqlite3.Connection, target: ProjectDB) -> list[str]:
    """Mang mọi cách đọc ĐÃ KHOÁ sang (`normalize_name_pronunciations` bỏ qua tên đã khoá, nên tên ấy không bao giờ được
    hỏi lại model). Cách đọc người nghe chọn giữ nguồn `listener_choice` - thứ ngăn máy viết đè nó. Trả về tên đã mang."""
    with target.connect() as connection:
        already = {str(row[0]) for row in connection.execute(
            "SELECT normalized_surface FROM pronunciations WHERE locked=1")}
    carried: list[str] = []
    for row in _rows(source, "SELECT surface, normalized_surface, spoken_form, source, confidence FROM pronunciations"
                             " WHERE locked=1 ORDER BY normalized_surface"):
        key = str(row["normalized_surface"])
        if key in already:
            continue
        if str(row["source"]) == LISTENER_PRONUNCIATION_SOURCE:
            target.set_listener_pronunciation(surface=str(row["surface"]), normalized_surface=key,
                                              spoken_form=str(row["spoken_form"]), source=LISTENER_PRONUNCIATION_SOURCE)
        else:
            target.upsert_pronunciation(surface=str(row["surface"]), normalized_surface=key,
                                        spoken_form=str(row["spoken_form"]), confidence=float(row["confidence"] or 0.0),
                                        source=str(row["source"]), locked=True)
        carried.append(str(row["surface"]))
    return carried


# ---- giọng, nhân vật đã biết, ghim của người nghe -----------------------------------------------------------------


def _casting(source: sqlite3.Connection, folded_source: str, exposure: dict[str, int], log: Log,
             presence: dict[str, bool] | None = None) -> list[tuple[str, str, dict[str, Any]]]:
    """(tên, voice_key, hồ sơ giọng) cho mọi nhân vật có giọng ở dự án nguồn - `port_casting.read_casting`.

    Hai truy vấn vì mỗi cái một mình đều rơi người, theo hai hướng ngược nhau: chỉ hỏi ai NÓI trong dự án nguồn thì rơi
    người đã ghim mà im lặng (THEOSBANE, 156/478 chương, bị cấp giọng khác lần sau mở miệng); chỉ hỏi ai được GHIM thì rơi
    người mới cấp giọng ở dự án nguồn (bộ cấp giọng không ghi ghim). Bất đồng thì giọng đã NGHE thắng giọng đã ghim.
    """
    from .analysis import is_local_speaker

    rows = _rows(source, SPOKE_HERE_SQL)
    spoke = len(rows)
    rows += _rows(source, PINNED_SQL)
    folded = _fold_names([str(row["canonical_name"]) for row in rows], folded_source, presence=presence)
    for loser, winner in sorted(folded.items()):
        log(f"  gộp {loser} -> {winner} (cùng một người)")
    mentions: dict[str, int] = {}
    spoken: dict[str, int] = {}
    pinned: set[str] = set()
    for index, row in enumerate(rows):
        name = str(row["canonical_name"])
        if row["mentions_here"] is not None:
            mentions[name] = max(mentions.get(name, 0), int(row["mentions_here"]))
        # Sổ cộng dồn thắng `mention_count` (số của riêng một dự án) khi có - tra theo tên đã gộp.
        if folded.get(name, name) in exposure:
            mentions[name] = max(mentions.get(name, 0), int(exposure[folded.get(name, name)]))
        if index < spoke:
            spoken[name] = max(spoken.get(name, 0), int(row["lines_here"] or 0))
        else:
            pinned.add(name)
    # Cách viết bị gộp xếp SAU cách viết đúng, để "dòng đầu thắng" chọn giọng của cách viết đúng.
    ordered = sorted(enumerate(rows), key=lambda item: (str(item[1]["canonical_name"]) in folded, item[0]))
    candidates: list[tuple[str, str, dict[str, Any]]] = []
    seen: set[str] = set()
    for _index, row in ordered:
        name = folded.get(str(row["canonical_name"]), str(row["canonical_name"]))
        # NPC của một chương nguồn không là ai ở dự án mới; giọng người kể là CÀI ĐẶT dự án, không phải ghim của ai.
        if is_local_speaker(name) or name.strip().upper() == "NARRATOR" or name in seen:
            continue
        seen.add(name)
        candidates.append((name, str(row["voice_key"]), dict(row)))

    # Một giọng cho hai người: người được nghe nhiều nhất giữ (số câu cộng dồn -> số câu ở nguồn -> có ghim), người kia
    # được cấp lại. Hoà thì không có căn cứ - bỏ cả hai cho bộ cấp giọng chia lại.
    holders: dict[str, list[str]] = {}
    for name, voice_key, _profile in candidates:
        holders.setdefault(voice_key, []).append(name)
    kept: list[tuple[str, str, dict[str, Any]]] = []
    for name, voice_key, profile in candidates:
        sharing = holders[voice_key]
        if len(sharing) == 1:
            kept.append((name, voice_key, profile))
            continue
        rank = {other: (mentions.get(other, 0), spoken.get(other, 0), other in pinned) for other in sharing}
        best = max(rank.values())
        winners = [other for other in sharing if rank[other] == best]
        if len(winners) > 1:
            log(f"  bỏ {name}: giọng {voice_key} bị {', '.join(sorted(sharing))} dùng chung và ngang nhau")
            continue
        if name == winners[0]:
            log(f"  {name} giữ {voice_key}; cấp lại {', '.join(sorted(o for o in sharing if o != name))}")
            kept.append((name, voice_key, profile))
    return kept


def _known_characters(source: sqlite3.Connection, folded_source: str, exposure: dict[str, int],
                      presence: dict[str, bool] | None = None) -> list[dict[str, Any]]:
    """Mọi nhân vật dự án nguồn đã biết (tên, giới, tuổi, tính cách, số lần gặp), cho mục "Nhân vật đã biết" của prompt
    phân tích - `port_casting.read_known_characters`. Bỏ vai (NARRATOR/UNKNOWN), NPC một chương, nhóm ANONYMOUS."""
    from .analysis import RESERVED_SPEAKERS, is_local_speaker

    rows = _rows(source, """
        SELECT canonical_name, display_name, gender, age, personality, locked, locked_age,
               importance, mention_count, confidence
        FROM characters
        WHERE mention_count > 0 AND gender IN ('male','female')
        ORDER BY mention_count DESC
    """)
    counts = {str(row["canonical_name"]): int(row["mention_count"] or 0) for row in rows}
    folded = _fold_names(list(counts), folded_source, counts, presence)
    extra: Counter[str] = Counter()
    for loser, winner in folded.items():
        extra[winner] += counts.get(loser, 0)
    known: list[dict[str, Any]] = []
    for row in rows:
        name = str(row["canonical_name"])
        if name in folded or name.casefold() in RESERVED_SPEAKERS or is_local_speaker(name) \
                or name.upper().startswith("ANONYMOUS"):
            continue
        record = dict(row)
        record["mention_count"] = max(int(record["mention_count"] or 0) + extra[name], int(exposure.get(name, 0)))
        known.append(record)
    return known


def _listener_pins(source: sqlite3.Connection) -> list[sqlite3.Row]:
    """Mọi ghim giới/tuổi của NGƯỜI NGHE, kể cả người không nói câu nào ở dự án nguồn (ARTHUR DOYLE, lô 10: `locked=1`,
    0 lần nhắc - lọc `mention_count > 0` như danh sách "đã biết" là làm mất ghim, và mô hình lại được quyền đổi ý)."""
    return _rows(source, """
        SELECT canonical_name, gender, locked, locked_age FROM characters
        WHERE locked = 1 OR (locked_age IS NOT NULL AND locked_age <> '')
        ORDER BY canonical_name
    """)


def seed_casting(source: sqlite3.Connection, target: ProjectDB, folded_source: str,
                 exposure: dict[str, tuple[int, int]], log: Log = _quiet) -> dict[str, int]:
    """Giọng từng nhân vật (ghim `locked_voice_key` + chép hồ sơ giọng - hồ sơ là tất định nên chép là tái tạo đúng
    tiếng), nhân vật đã biết (KHÔNG khoá: máy nói cho máy, sách nói khác thì model vẫn được sửa), ghim của người nghe
    (khoá vĩnh viễn), rồi sổ cộng dồn."""
    from .character_registry import canonical_key

    lines = {name: count for name, (count, _parts) in exposure.items()}
    presence: dict[str, bool] = {}  # tên nào có trong sách - hai lượt gộp tên hỏi chung phần lớn các tên
    already = set(target.locked_character_voices())
    voices = 0
    for name, voice_key, profile in _casting(source, folded_source, lines, log, presence):
        if canonical_key(name) in already:
            continue
        target.upsert_voice_profile({
            "voice_key": voice_key,
            "engine": profile["engine"],
            "preset_name": profile["preset_name"],
            "description": profile["description"],
            "seed": profile["seed"],
            "pitch_semitones": profile["pitch_semitones"],
            "formant_ratio": profile["formant_ratio"],
            "status": "ready",
        })
        target.set_locked_character_voice(name, voice_key)
        voices += 1
    known = _known_characters(source, folded_source, lines, presence)
    for character in known:
        target.upsert_character(
            canonical_name=str(character["canonical_name"]),
            display_name=str(character["display_name"] or character["canonical_name"]),
            gender=str(character["gender"]),
            age=str(character["age"] or "unknown"),
            personality=str(character["personality"] or ""),
            mentions=int(character["mention_count"] or 0),
            importance=str(character["importance"] or "minor"),
            confidence=float(character["confidence"] or 0.5),
        )
    pins = 0
    for row in _listener_pins(source):
        name = str(row["canonical_name"])
        # Một giá trị không còn ghim được (dự án cũ, danh sách tuổi đã đổi) thì bỏ riêng nó - ProjectDB kiểm TRƯỚC khi
        # ghi, nên bỏ qua không để lại nửa dòng trong giao dịch chung.
        try:
            if int(row["locked"] or 0) and str(row["gender"]) in ("male", "female"):
                target.lock_character_gender(name, str(row["gender"]))
                pins += 1
            if str(row["locked_age"] or ""):
                target.lock_character_age(name, str(row["locked_age"]))
                pins += 1
        except ValueError as error:
            log(f"  bỏ ghim của {name}: {error}")
    if exposure:
        _write_ledger(target, exposure)
    return {"voices": voices, "known": len(known), "pins": pins, "ledger": len(exposure)}


# ---- phán quyết của người nghe trên audio -------------------------------------------------------------------------


def seed_acceptances(source: sqlite3.Connection, target: ProjectDB) -> int:
    """Phán quyết "nghe rồi, chấp nhận" gắn với (mã đoạn, băm audio, mã cảnh báo): gieo trước là vô hại - chỉ khớp khi
    đúng bản thu ấy xuất hiện lại (một chương làm lại), không bao giờ duyệt thay một bản thu chưa ai nghe."""
    with target.connect() as connection:
        already = {tuple(str(value) for value in row) for row in connection.execute(
            "SELECT segment_stable_id, wav_sha256, warning_code FROM listener_audio_acceptances")}
    seeded = 0
    for row in _rows(source, "SELECT segment_stable_id, wav_sha256, warning_code, note"
                             " FROM listener_audio_acceptances ORDER BY segment_stable_id"):
        key = (str(row[0]), str(row[1]), str(row[2]))
        if key in already:
            continue
        target.accept_segment_audio(segment_stable_id=key[0], wav_sha256=key[1], warning_code=key[2],
                                    note=str(row[3] or "") or "gieo từ phần trước")
        seeded += 1
    return seeded


# ---- cả lượt -----------------------------------------------------------------------------------------------------


def carried_summary(source: Path) -> dict[str, int]:
    """Đếm nhanh thứ phần kế tiếp sẽ mang theo, cho trình tạo sách hiện trước khi tạo (không gộp tên, không đọc sách)."""
    with closing(_read_only(source)) as connection:
        def count(sql: str, *params: Any) -> int:
            rows = _rows(connection, sql, *params)
            return int(rows[0][0] or 0) if rows else 0

        return {
            # Đúng luật của lượt gieo (ai nói + ai đã ghim, một giọng một người - bản sao lô 18: 395 người có giọng, 119
            # người giữ được), chỉ bỏ bước so tên với sách (đọc cả cuốn) - lệch vài tên là cùng.
            "voices": len(_casting(connection, "", {}, _quiet)),
            "pronunciations": count("SELECT COUNT(*) FROM pronunciations WHERE locked=1"),
            "listenerReadings": count("SELECT COUNT(*) FROM pronunciations WHERE locked=1 AND source=?",
                                      LISTENER_PRONUNCIATION_SOURCE),
            "pins": count("SELECT COUNT(*) FROM characters WHERE locked=1 OR (locked_age IS NOT NULL AND locked_age <> '')"),
            "aliases": len(aliases.load(source)),
            "bracket": bracket_rule.load(source),
            "names": len(renames.load(source)),
        }


def seed(source: Path, target: Path, log: Log = _quiet) -> dict[str, Any]:
    """Gieo `target` (vừa tạo, chưa chạy) từ `source` - thứ tự như `launch_batch.sh`: cách đọc tên, giọng + nhân vật đã
    biết + ghim + sổ, phán quyết. Ghi `continues.json`. Trả về số đếm từng phần."""
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target:
        raise ContinuationError("Không làm tiếp một dự án từ chính nó")
    for project in (source, target):
        if not is_project(project):
            raise ContinuationError(f"Không phải dự án của ABook: {project}")
    analysed = analysed_segments(target)
    if analysed:
        raise ContinuationError(
            f"Dự án mới đã phân tích {analysed} đoạn - chỉ gieo được sau khi tạo và trước khi chạy")
    exposure = book_exposure(chain_of(source))
    database = _SeedingDB(target / DB_NAME)
    with closing(_read_only(source)) as connection:
        from .character_registry import fold_for_source_search

        folded_source = fold_for_source_search(_source_text(connection))
        with database.batch():
            readings = seed_pronunciations(connection, database)
            log(f"cách đọc tên: {len(readings)}")
            casting = seed_casting(connection, database, folded_source, exposure, log)
            log(f"giọng nhân vật: {casting['voices']}, nhân vật đã biết: {casting['known']}, ghim: {casting['pins']}")
            acceptances = seed_acceptances(connection, database)
    # Bí danh người nghe đã gộp ("Thiên Biến Vạn Hóa" là Krai): file cạnh sổ, bước gom tên của phần sau tự áp.
    carried_aliases = aliases.carry(source, target)
    # Quy ước 『』 của cuốn ("lời trong 『』 là của X"): phần sau gán trước khi gom tên, như phần trước sau khi chọn.
    carried_bracket = bracket_rule.carry(source, target)
    # Tên hiển thị người nghe đã đặt cho nhân vật ("Đổi tên" ở tab Nhân vật): chỉ là chữ trên màn hình, đi theo cuốn.
    carried_names = renames.carry(source, target)
    _write_link(source, target)
    return {"from": str(source), "part": part_number(target), "pronunciations": len(readings), **casting,
            "acceptances": acceptances, "aliases": carried_aliases, "bracket": carried_bracket,
            "names": carried_names}
