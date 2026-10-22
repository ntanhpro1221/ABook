"""Tìm ảnh bìa trên mạng theo tên sách (Smart AudioBook Player có "cover art downloader"; Audiobookshelf "match" bìa
qua Open Library, Google Books, Audible, iTunes).

Ba nguồn công khai, không cần khoá: iTunes Search (bìa sách/sách nói, ảnh lớn), Open Library, Google Books. Truyện
mạng dịch thường KHÔNG có trên các nguồn này - nên đây là gợi ý để người dùng chọn, không bao giờ tự đặt.

An toàn: máy chủ chỉ tải ảnh từ đúng các tên miền ảnh của ba nguồn ấy qua HTTPS (`ALLOWED_IMAGE_HOSTS`). Giao diện
gửi lên một URL; nếu cho tải URL bất kỳ thì trang web nào lừa được người dùng cũng khiến máy chủ gọi vào mạng nội bộ.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any, Callable

from . import covers

log = logging.getLogger(__name__)

TIMEOUT = 8  # mỗi thao tác socket; một nguồn nhỏ giọt từng byte không bị cắt bởi nó, nên còn hạn tổng ở dưới
SEARCH_DEADLINE = 12  # giây cho CẢ lượt tìm (mọi nguồn): quá hạn thì trả những gì đã có
DOWNLOAD_DEADLINE = 30  # giây cho một ảnh bìa
JSON_LIMIT = 2 * 1024 * 1024
DOWNLOAD_FAILED = "Chưa tải được ảnh này, bạn thử lại hoặc chọn ảnh khác"
USER_AGENT = "ABook/1 (cover search)"
ALLOWED_IMAGE_HOSTS = re.compile(
    r"^(is\d+-ssl\.mzstatic\.com|covers\.openlibrary\.org|books\.google\.com|books\.googleusercontent\.com)$"
)


def _read_within(response: Any, limit: int, seconds: float) -> bytes:
    """Đọc tối đa `limit` byte (+1 để biết là vượt) trong `seconds` giây tính từ giờ - nguồn nhỏ giọt thì bỏ, không để luồng treo mãi."""
    deadline = time.monotonic() + seconds
    chunks: list[bytes] = []
    total = 0
    while total <= limit:
        if time.monotonic() > deadline:
            raise TimeoutError("quá hạn đọc")
        chunk = response.read(min(64 * 1024, limit + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)


def _get_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 - URL cố định theo nguồn ở dưới
        return json.loads(_read_within(response, JSON_LIMIT, SEARCH_DEADLINE).decode("utf-8"))


def _itunes(query: str) -> list[dict[str, Any]]:
    found = []
    for media in ("audiobook", "ebook"):
        data = _get_json("https://itunes.apple.com/search?" + urllib.parse.urlencode(
            {"term": query, "media": media, "limit": 8}))
        for item in data.get("results", []):
            art = str(item.get("artworkUrl100") or "")
            if not art:
                continue
            found.append({
                "provider": "iTunes",
                "title": item.get("collectionName") or item.get("trackName") or "",
                "author": item.get("artistName") or "",
                "thumb": art,
                # Ảnh iTunes đổi cỡ theo tên file: 100x100bb -> 1000x1000bb là cùng ảnh, nét hơn.
                "url": re.sub(r"/\d+x\d+bb\.", "/1000x1000bb.", art),
            })
    return found


def _open_library(query: str) -> list[dict[str, Any]]:
    data = _get_json("https://openlibrary.org/search.json?" + urllib.parse.urlencode(
        {"q": query, "limit": 10, "fields": "title,author_name,cover_i"}))
    found = []
    for doc in data.get("docs", []):
        cover_id = doc.get("cover_i")
        if not cover_id:
            continue
        found.append({
            "provider": "Open Library",
            "title": doc.get("title") or "",
            "author": ", ".join(doc.get("author_name") or [])[:80],
            "thumb": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg",
            "url": f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg",
        })
    return found


def _google_books(query: str) -> list[dict[str, Any]]:
    data = _get_json("https://www.googleapis.com/books/v1/volumes?" + urllib.parse.urlencode(
        {"q": query, "maxResults": 10, "printType": "books"}))
    found = []
    for item in data.get("items", []):
        info = item.get("volumeInfo") or {}
        links = info.get("imageLinks") or {}
        thumb = str(links.get("thumbnail") or links.get("smallThumbnail") or "").replace("http://", "https://")
        if not thumb:
            continue
        found.append({
            "provider": "Google Books",
            "title": info.get("title") or "",
            "author": ", ".join(info.get("authors") or [])[:80],
            "thumb": thumb,
            # zoom=0 xin ảnh lớn nhất Google có cho cuốn ấy (có khi vẫn nhỏ).
            "url": re.sub(r"([?&])zoom=\d", r"\g<1>zoom=0", thumb).replace("&edge=curl", ""),
        })
    return found


PROVIDERS: list[Callable[[str], list[dict[str, Any]]]] = [_itunes, _open_library, _google_books]


def search(query: str) -> dict[str, Any]:
    """Kết quả từ mọi nguồn (nguồn lỗi/mất mạng thì bỏ qua và ghi tên vào `failed`, không làm hỏng cả lượt tìm)."""
    query = " ".join((query or "").split())[:120]
    if len(query) < 2:
        return {"query": query, "results": [], "failed": []}
    results: list[dict[str, Any]] = []
    failed: list[str] = []
    # Không dùng `with ThreadPoolExecutor`: thoát khối ấy là chờ mọi luồng xong, một nguồn treo kéo cả lượt tìm treo theo.
    pool = ThreadPoolExecutor(max_workers=len(PROVIDERS))
    try:
        futures = {pool.submit(provider, query): provider.__name__.strip("_") for provider in PROVIDERS}
        wait(futures, timeout=SEARCH_DEADLINE)
        for future, name in futures.items():
            try:
                if not future.done():
                    raise TimeoutError(name)
                results += future.result()
            except Exception:  # noqa: BLE001 - một nguồn hỏng không được làm hỏng các nguồn khác
                failed.append(name)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    seen: set[str] = set()
    unique = []
    for item in results:
        if item["url"] in seen or not allowed_image_url(item["url"]):
            continue
        seen.add(item["url"])
        unique.append(item)
    return {"query": query, "results": unique[:30], "failed": failed}


def allowed_image_url(url: str) -> bool:
    parts = urllib.parse.urlsplit(url or "")
    return parts.scheme == "https" and bool(ALLOWED_IMAGE_HOSTS.match(parts.hostname or ""))


def download_image(url: str) -> bytes:
    if not allowed_image_url(url):
        raise covers.CoverError("Chỉ lấy ảnh từ iTunes, Open Library hoặc Google Books")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT * 2) as response:  # noqa: S310 - đã kiểm tên miền
            data = _read_within(response, covers.MAX_UPLOAD_BYTES, DOWNLOAD_DEADLINE)
    except OSError as exc:  # gồm URLError, HTTPError, TimeoutError
        # Người dùng chỉ cần biết "chưa được, thử lại": `HTTP Error 503` / `<urlopen error ...>` đi vào nhật ký, không lên màn hình.
        log.warning("Không tải được ảnh bìa %s: %s", url, exc)
        raise covers.CoverError(DOWNLOAD_FAILED) from exc
    if len(data) > covers.MAX_UPLOAD_BYTES:
        raise covers.CoverError("Ảnh quá lớn")
    return data
