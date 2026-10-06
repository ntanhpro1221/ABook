r"""Khảo sát và tải truyện dịch từ Hako (docln) vào kho dữ liệu `D:/Novels/ABook/Corpus/`.

Chạy bằng Python của máy có `cloudscraper` + `lxml` (`py`, 3.13) - KHÔNG phải runtime/.venv của dây chuyền.

    py scripts/corpus/hako.py survey --pages 5                 # xếp hạng truyện dịch (người) đã hoàn thành
    py scripts/corpus/hako.py survey --kind convert            # mục AI dịch (/ai-dich)
    py scripts/corpus/hako.py survey --kind sangtac            # sáng tác gốc tiếng Việt (/sang-tac)
    py scripts/corpus/hako.py download /truyen/259-toi-la-nhen-thi-sao --title "Kumo Desu Ga Nani Ka"
    py scripts/corpus/hako.py fetch-all                        # tải dần MỌI bộ trong danh sách chưa có trong _full

Tải là tải CẢ BỘ, vào `Corpus/_full/<tên>` (chủ sách 06-10: "đã tải là tải hết"; tìm thật nhiều truyện rồi tải dần
để lúc cần không phải tải - mạng thì dư). Chọn chương cho một việc là việc của bước sau, không phải của bộ tải.

Viết lại từ `D:/Novels/Tools/NovelDownloader_Docln_MultiThread_MultiSource.py` của chủ sách (chỉ tham khảo,
không sửa bản ấy - 19-09). Khác bản gốc ở những chỗ một kho dữ liệu cần:
  - tham số dòng lệnh thay vì sửa hằng số trong file;
  - ÍT luồng (mặc định 6, bản gốc 64) và nghỉ giữa các yêu cầu: tải để làm dữ liệu không vội, và không
    nên dội tải lên một trang cộng đồng;
  - chạy lại thì BỎ QUA chương đã có, nên đứt giữa chừng cứ chạy lại;
  - không đánh số lại khi thiếu chương: số file = thứ tự trong mục lục, chương không tải được ghi vào
    `metadata.json` (`missing`) chứ không bị lấp bằng chương sau - để số file vẫn khớp mục lục;
  - `metadata.json` cạnh truyện: nguồn, thể loại, số từ, danh sách chương, lúc tải.
Giải mã nội dung bảo vệ (`chapter-c-protected`: base64 + XOR theo `data-k`) giữ nguyên thuật toán bản gốc.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import cloudscraper
from lxml import html

SOURCES = ("https://docln.net", "https://docln.sbs", "https://ln.hako.vn")
CORPUS = Path("D:/Novels/ABook/Corpus")
FULL = CORPUS / "_full"
STOP_FILE = FULL / "STOP_FETCH"  # tạo file này để `fetch-all` dừng sau bộ đang tải
# Khảo sát nằm CÙNG kho (repo riêng tư, xem scripts/corpus/manifest.py): có bình luận người đọc chép từ Hako.
SURVEY_DIR = CORPUS / "_survey"
# Bộ lọc của trang danh sách Hako: truyện dịch bởi người, AI dịch ("convert"), sáng tác tiếng Việt.
KINDS = ("truyendich", "convert", "sangtac")
PAUSE_SECONDS = 0.4
BLOCK_SECONDS = 90


class Sources:
    """Xoay vòng các tên miền; tên miền trả lỗi thì nghỉ BLOCK_SECONDS."""

    def __init__(self, bases: tuple[str, ...] = SOURCES) -> None:
        self._lock = threading.Lock()
        self._local = threading.local()
        self.bases = list(bases)
        self.blocked_until = {base: 0.0 for base in bases}

    def session(self):
        if not hasattr(self._local, "session"):
            self._local.session = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "desktop": True}
            )
        return self._local.session

    def pick(self) -> str:
        while True:
            now = time.time()
            with self._lock:
                ready = [base for base in self.bases if self.blocked_until[base] <= now]
                if ready:
                    return ready[0]
                wait = min(self.blocked_until.values()) - now
            time.sleep(max(1.0, wait))

    def block(self, base: str) -> None:
        with self._lock:
            self.blocked_until[base] = time.time() + BLOCK_SECONDS

    def get(self, path: str, attempts: int = 8) -> bytes:
        for _ in range(attempts):
            base = self.pick()
            try:
                response = self.session().get(base + path, timeout=25)
            except Exception:  # noqa: BLE001 - mạng/Cloudflare: đổi nguồn và thử lại
                self.block(base)
                continue
            if response.status_code == 200:
                time.sleep(PAUSE_SECONDS)
                return response.content
            if response.status_code == 404:
                raise FileNotFoundError(base + path)
            self.block(base)
        raise RuntimeError(f"không tải được {path} sau {attempts} lần")


def decode_protected(data_k: str, data_c: str) -> str:
    chunks = json.loads(data_c)
    chunks.sort(key=lambda chunk: int(chunk[:4]))
    key = data_k.encode("utf-8")
    raw = bytearray()
    for chunk in chunks:
        payload = chunk[4:]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        try:
            decoded = base64.b64decode(payload)
        except Exception:  # noqa: BLE001 - chunk hỏng: bỏ, như bản gốc
            continue
        raw.extend(byte ^ key[index % len(key)] for index, byte in enumerate(decoded))
    tree = html.fromstring(f"<div>{raw.decode('utf-8', errors='replace')}</div>")
    return "\n\n".join(p.text_content().strip() for p in tree.xpath(".//p") if p.text_content().strip())


def chapter_text(page: bytes) -> str:
    tree = html.fromstring(page)
    protected = tree.xpath('//div[@id="chapter-c-protected"]')
    if protected and protected[0].get("data-k") and protected[0].get("data-c"):
        try:
            text = decode_protected(protected[0].get("data-k"), protected[0].get("data-c"))
            if text:
                return text
        except (ValueError, json.JSONDecodeError):
            pass
    content = tree.xpath('//div[@id="chapter-content"]')
    if not content:
        return ""
    paragraphs = content[0].xpath('.//p[not(contains(@style,"display: none"))]')
    return "\n\n".join(p.text_content().strip() for p in paragraphs if p.text_content().strip())


def series_info(sources: Sources, path: str) -> dict:
    tree = html.fromstring(sources.get(path))
    title = " ".join(tree.xpath('string(//span[contains(@class,"series-name")])').split())
    stats = {}
    for item in tree.xpath('//div[contains(@class,"statistic-item")]'):
        parts = [" ".join(x.text_content().split()) for x in item.xpath("./*")]
        if len(parts) >= 2:
            stats[parts[0]] = parts[1]
    info = {}
    for item in tree.xpath('//div[contains(@class,"info-item")]'):
        text = " ".join(item.text_content().split())
        if ":" in text:
            name, _, value = text.partition(":")
            info[name.strip()] = value.strip()
    chapters = []
    for anchor in tree.xpath('//ul[contains(@class,"list-chapters")]//a'):
        name = " ".join(anchor.text_content().split())
        if re.search(r"minh h[oọ]a", name, re.IGNORECASE):
            continue
        chapters.append({"path": urlparse(anchor.get("href")).path, "title": name})
    words = int(re.sub(r"\D", "", stats.get("Số từ", "0")) or 0)
    last = tree.xpath('//div[contains(@class,"statistic-item")][.//div[normalize-space(.)="Lần cuối"]]//time/@datetime')
    # Bình luận trang đầu (~10 cái mới nhất): độc giả hay nói "drop rồi à", khen chê, chỉ chỗ đọc raw/bản Anh.
    comments = []
    for item in tree.xpath('//div[contains(@class,"ln-comment-item")]'):
        text = " ".join(item.xpath('string(.//*[contains(@class,"ln-comment-content")])').split())
        when = item.xpath('.//time/@datetime')
        if text:
            comments.append({"time": when[0] if when else "", "text": text[:500]})
    return {
        "path": path,
        "title": title,
        "genres": [" ".join(a.text_content().split()) for a in tree.xpath('//div[contains(@class,"series-gernes")]//a')],
        "status": info.get("Tình trạng", ""),
        "author": info.get("Tác giả", ""),
        "words": words,
        "rating": stats.get("Đánh giá", ""),
        "views": int(re.sub(r"\D", "", stats.get("Lượt xem", "0")) or 0),
        "chapters": chapters,
        "last_update": last[0] if last else "",
        "comments": comments,
        "summary": " ".join(" ".join(x.text_content().split()) for x in tree.xpath('//div[contains(@class,"summary-content")]'))[:600],
    }


def survey(pages: int, sort: str, kind: str = "truyendich", status: str = "hoanthanh") -> list[dict]:
    sources = Sources()
    found: dict[str, str] = {}
    for page in range(1, pages + 1):
        tree = html.fromstring(sources.get(f"/danh-sach?{kind}=1&{status}=1&sapxep={sort}&page={page}"))
        for anchor in tree.xpath('//div[contains(@class,"series-title")]/a'):
            found.setdefault(urlparse(anchor.get("href")).path, anchor.get("title") or anchor.text_content().strip())
    results = []
    for index, path in enumerate(found, 1):
        try:
            info = series_info(sources, path)
        except Exception as exc:  # noqa: BLE001 - một truyện hỏng không làm hỏng cả bảng
            print(f"  bỏ {path}: {exc}", file=sys.stderr)
            continue
        info["chapter_count"] = len(info.pop("chapters"))
        results.append(info)
        print(f"  [{index}/{len(found)}] {info['title'][:50]:50} {info['words']:>9,} từ  {info['chapter_count']:>4} ch  {', '.join(info['genres'][:4])}")
    target = SURVEY_DIR / (f"hako_survey_{kind}.json" if status == "hoanthanh" else f"hako_survey_{kind}_{status}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ghi {target}")
    return results


def download(path: str, title: str | None, workers: int, sources: Sources | None = None, info: dict | None = None) -> Path:
    sources = sources or Sources()
    info = info or series_info(sources, path)
    name = title or info["title"]
    folder = FULL / re.sub(r'[<>:"/\\|?*]', "_", name).strip().rstrip(".")
    folder.mkdir(parents=True, exist_ok=True)
    chapters = info["chapters"]
    digits = max(3, len(str(len(chapters))))
    missing: list[str] = []
    lock = threading.Lock()
    done = [0]

    def one(item: tuple[int, dict]) -> None:
        index, chapter = item
        target = folder / f"{index:0{digits}}.txt"
        if target.is_file() and target.stat().st_size > 0:
            return
        try:
            text = chapter_text(sources.get(chapter["path"]))
        except Exception as exc:  # noqa: BLE001
            text = ""
            print(f"  lỗi {index}: {exc}", file=sys.stderr)
        with lock:
            if not text:
                missing.append(f"{index:0{digits}} {chapter['title']}")
                return
            target.write_text(f"{chapter['title']}\n\n{text}\n", encoding="utf-8")
            done[0] += 1
            if done[0] % 25 == 0:
                print(f"  {done[0]} chương mới / {len(chapters)}", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, enumerate(chapters)))
    metadata = {
        **{key: value for key, value in info.items() if key != "chapters"},
        "chapters": [chapter["title"] for chapter in chapters],
        "source": "hako",
        "url": f"https://docln.net{path}",
        "folder": str(folder),
        "missing": sorted(missing),
        "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (folder / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{name}: {len(chapters)} chương trong mục lục, thiếu {len(missing)} -> {folder}")
    return folder


def series_id(path_or_url: str) -> str:
    """Số truyện trong `/truyen/<số>-<tên>` - cùng một bộ dù tên miền hay đuôi tên đổi."""
    found = re.search(r"/truyen/(\d+)", path_or_url)
    return found.group(1) if found else ""


def known_ids() -> set[str]:
    """Bộ đã có trong `_full` (bản tải từ Hako ghi `path`; bản chuyển từ Tools ghi `url` docln)."""
    ids = set()
    for meta in FULL.glob("*/metadata.json"):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for key in ("path", "url"):
            if series_id(str(data.get(key) or "")):
                ids.add(series_id(str(data[key])))
    return ids


STATUSES = ("hoanthanh", "dangtienhanh", "tamngung")
# Hako gắn nhãn nguồn cho truyện Hàn/Trung/Anh; LN Nhật KHÔNG có nhãn nào. Bộ phân tích nhắm LN Nhật > Hàn, Trung gần
# như không đọc, văn Việt gốc không phải mục tiêu (bộ nhớ analysis-diversity) -> mặc định bỏ Trung + Anh.
EXCLUDE_TAGS = ("Chinese Novel", "English Novel")


def fetch_all(workers: int, pause: float, max_pages: int, kinds: tuple[str, ...] = ("truyendich",),
              skip_ids: Path | None = None, statuses: tuple[str, ...] = STATUSES,
              exclude_tags: tuple[str, ...] = EXCLUDE_TAGS) -> None:
    """Đi hết các trang danh sách Hako, tải CẢ BỘ mọi truyện chưa có trong `_full`. Chạy lại = làm tiếp.

    Mỗi bộ xong ghi một dòng vào `_full/_fetch_log.tsv`; `STOP_FILE` có mặt thì dừng sau bộ đang tải.
    Mặc định chỉ truyện NGƯỜI dịch, bỏ bộ mang nhãn `exclude_tags` (chủ sách 06-10 hỏi "không filter gì à?"); bộ bị
    bỏ ghi vào `_full/_fetch_skipped.tsv` để chạy lại khỏi mở trang của nó lần nữa. Hai máy chia việc bằng `statuses`
    (06-10: máy nhà hoanthanh, Mac dangtienhanh + tamngung); `skip_ids` = số truyện máy kia đã có (`known-ids`).
    """
    sources = Sources()
    have = known_ids()
    if skip_ids:
        have |= set(skip_ids.read_text(encoding="utf-8").split())
    log = FULL / "_fetch_log.tsv"
    skipped_log = FULL / "_fetch_skipped.tsv"
    if skipped_log.exists():
        have |= {line.split("\t")[1] for line in skipped_log.read_text(encoding="utf-8").splitlines() if "\t" in line}
    fetched = 0
    for kind, status in [(kind, status) for kind in kinds for status in statuses]:
        for page in range(1, max_pages + 1):
            tree = html.fromstring(sources.get(f"/danh-sach?{kind}=1&{status}=1&sapxep=top&page={page}"))
            paths = [urlparse(a.get("href")).path for a in tree.xpath('//div[contains(@class,"series-title")]/a')]
            if not paths:
                break
            for path in paths:
                if STOP_FILE.exists():
                    print("gặp STOP_FETCH - dừng", flush=True)
                    return
                number = series_id(path)
                if not number or number in have:
                    continue
                try:
                    info = series_info(sources, path)
                    excluded = sorted(set(info["genres"]) & set(exclude_tags))
                    if excluded:
                        have.add(number)
                        with skipped_log.open("a", encoding="utf-8") as out:
                            out.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{number}\t{','.join(excluded)}\t{info['title']}\n")
                        continue
                    folder = download(path, None, workers, sources, info)
                except Exception as exc:  # noqa: BLE001 - một bộ hỏng không dừng cả lượt
                    print(f"  bỏ {path}: {exc}", file=sys.stderr, flush=True)
                    continue
                have.add(number)
                fetched += 1
                files = len(list(folder.glob("*.txt")))
                with log.open("a", encoding="utf-8") as out:
                    out.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{kind}\t{status}\t{path}\t{files}\t{folder.name}\n")
                print(f"[{fetched}] {kind}/{status} trang {page}: {folder.name} ({files} chương)", flush=True)
                time.sleep(pause)
    print(f"hết danh sách: tải {fetched} bộ mới", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("survey")
    s.add_argument("--pages", type=int, default=3)
    s.add_argument("--sort", default="top", help="top | topthang | theodoi | sotu | capnhat")
    s.add_argument("--kind", default="truyendich", choices=KINDS)
    # tamngung = "Tạm ngưng": bộ bị bỏ dở - thứ chủ sách muốn tìm (19-09).
    s.add_argument("--status", default="hoanthanh", choices=("hoanthanh", "tamngung", "dangtienhanh"))
    d = sub.add_parser("download")
    d.add_argument("path", help="đường dẫn truyện, vd /truyen/259-toi-la-nhen-thi-sao")
    d.add_argument("--title")
    d.add_argument("--workers", type=int, default=6)
    f = sub.add_parser("fetch-all")
    f.add_argument("--workers", type=int, default=6)
    f.add_argument("--pause", type=float, default=5.0, help="giây nghỉ giữa hai bộ")
    f.add_argument("--max-pages", type=int, default=1000)
    f.add_argument("--kinds", default="truyendich", help="loại danh sách, cách nhau dấu phẩy: " + ",".join(KINDS))
    f.add_argument("--statuses", default=",".join(STATUSES), help="tình trạng, cách nhau dấu phẩy: " + ",".join(STATUSES))
    f.add_argument("--exclude-tags", default=",".join(EXCLUDE_TAGS), help="bỏ bộ mang một trong các nhãn này ('' = không bỏ)")
    f.add_argument("--out", type=Path, help="thư mục bộ đầy đủ (mặc định Corpus/_full) - máy khác ngoài máy nhà")
    f.add_argument("--skip-ids", type=Path, help="file số truyện (mỗi dòng một số) đã có ở máy khác")
    sub.add_parser("known-ids", help="in số truyện đã có trong _full, mỗi dòng một số")
    args = parser.parse_args(argv)
    global FULL, STOP_FILE
    if getattr(args, "out", None):
        FULL = args.out
        STOP_FILE = FULL / "STOP_FETCH"
    if args.command == "survey":
        survey(args.pages, args.sort, args.kind, args.status)
    elif args.command == "fetch-all":
        kinds = tuple(kind for kind in args.kinds.split(",") if kind)
        statuses = tuple(status for status in args.statuses.split(",") if status)
        unknown = (set(kinds) - set(KINDS)) | (set(statuses) - set(STATUSES))
        if unknown:
            parser.error(f"loại / tình trạng không có: {sorted(unknown)}")
        FULL.mkdir(parents=True, exist_ok=True)
        fetch_all(args.workers, args.pause, args.max_pages, kinds, args.skip_ids, statuses,
                  tuple(tag.strip() for tag in args.exclude_tags.split(",") if tag.strip()))
    elif args.command == "known-ids":
        print("\n".join(sorted(known_ids(), key=int)))
    else:
        download(args.path, args.title, args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
