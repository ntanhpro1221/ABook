"""Bộ ví dụ DÙNG CHUNG cho "Tìm bìa trên mạng" (webui/cover_search.py, docs/EDITING.md P4): pytest và test JVM của app Android
(CoverSearchTest.kt) cùng đọc `tests/fixtures/cover_search/cases.json` - bản Python chạy từng ca với lời đáp của ba nguồn đã
đóng khuôn sẵn; bản Kotlin (CoverSearch.kt) phải hỏi ĐÚNG những địa chỉ ấy và ra ĐÚNG kết quả ấy.

    cases.json   {"search": [{name, query, responses: {địa chỉ: JSON | {"$error": ...}}, requested: [địa chỉ đã hỏi, xếp tên],
                              expected: {query, results, failed}}],
                  "allowed": [{url, allowed}],         allowed_image_url
                  "refusal": "câu báo khi địa chỉ ảnh không thuộc nguồn nào"}

Sinh lại (chỉ khi cố ý đổi hành vi):  runtime/.venv/Scripts/python.exe -m tests.cover_search_fixtures
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest import mock

FIXTURES = Path(__file__).parent / "fixtures" / "cover_search"
FILE = FIXTURES / "cases.json"
ERROR = "$error"


def _itunes(count: int, *, art: bool = True) -> list[dict[str, Any]]:
    return [{"collectionName": f"Sách {n}", "artistName": f"Tác giả {n}",
             **({"artworkUrl100": f"https://is1-ssl.mzstatic.com/image/thumb/Features/v4/{n}/100x100bb.jpg"} if art else {})}
            for n in range(count)]


def _open_library(count: int) -> list[dict[str, Any]]:
    return [{"title": f"Open {n}", "author_name": [f"Người {n}"], "cover_i": 1000 + n} for n in range(count)]


def canned(case: str) -> Any:
    """Lời đáp đóng khuôn của một ca: hàm (địa chỉ) -> JSON, hay {"$error"} khi nguồn ấy hỏng."""
    fail_google = case in {"google_down", "all_down"}
    fail_ebook = case in {"itunes_ebook_down", "all_down"}
    fail_open = case == "all_down"

    def answer(url: str) -> Any:
        if "itunes.apple.com" in url:
            if "media=ebook" in url and fail_ebook:
                return {ERROR: "429"}
            if case == "mixed":
                if "media=audiobook" in url:
                    return {"results": [
                        {"collectionName": "Kuma Kuma Kuma Bear", "artistName": "Kumanano",
                         "artworkUrl100": "https://is5-ssl.mzstatic.com/image/thumb/Publication/v4/ab/100x100bb.jpg"},
                        {"trackName": "Chỉ có tên bài", "artworkUrl100": "https://is2-ssl.mzstatic.com/image/thumb/x/60x60bb.jpg"},
                        {"collectionName": "Không có ảnh", "artistName": "Ai đó"},
                        {"collectionName": "Ảnh trống", "artworkUrl100": ""},
                        {"collectionName": "Host lạ", "artworkUrl100": "https://evil.example/100x100bb.jpg"},
                    ]}
                return {"results": [
                    {"collectionName": "Kuma Kuma Kuma Bear", "artistName": "Kumanano",
                     "artworkUrl100": "https://is5-ssl.mzstatic.com/image/thumb/Publication/v4/ab/100x100bb.jpg"},
                    {"collectionName": "Quyển 2", "artistName": "Kumanano",
                     "artworkUrl100": "https://is3-ssl.mzstatic.com/image/thumb/Publication/v4/cd/200x300bb.jpg"},
                ]}
            return {"results": _itunes(1) if case == "google_down" else []}
        if "openlibrary.org" in url:
            if fail_open:
                return {ERROR: "timeout"}
            if case == "mixed":
                return {"docs": [
                    {"title": "Kuma Kuma Kuma Bear, Vol. 1", "author_name": ["Kumanano", "Non"], "cover_i": 8675309},
                    {"title": "Không bìa", "author_name": ["Ai đó"]},
                    {"title": "Bìa số 0", "cover_i": 0},
                    {"title": "Nhiều tác giả", "cover_i": 42,
                     "author_name": ["Nguyễn Nhật Ánh", "Trần Đăng Khoa", "Nguyễn Huy Thiệp", "Xuân Quỳnh", "Hoàng Phủ Ngọc Tường"]},
                    {"title": "Không tên tác giả", "cover_i": 43},
                ]}
            if case == "thirty_cap":
                return {"docs": _open_library(40)}
            return {"docs": []}
        if "googleapis.com" in url:
            if fail_google:
                return {ERROR: "quota"}
            if case == "mixed":
                return {"items": [
                    {"volumeInfo": {"title": "Kuma Bear", "authors": ["Kumanano"], "imageLinks": {
                        "thumbnail": "http://books.google.com/books/content?id=AAA&printsec=frontcover&img=1&zoom=1&edge=curl&source=gbs_api",
                        "smallThumbnail": "http://books.google.com/books/content?id=AAA&zoom=5"}}},
                    {"volumeInfo": {"title": "Chỉ ảnh nhỏ", "imageLinks": {
                        "smallThumbnail": "https://books.google.com/books/content?id=BBB&img=1&zoom=5"}}},
                    {"volumeInfo": {"title": "Không ảnh", "authors": ["Ai đó"]}},
                    {"volumeInfo": {"title": "Host lạ", "imageLinks": {"thumbnail": "https://evil.example/x.jpg"}}},
                    {"volumeInfo": {"title": "Cùng ảnh với iTunes", "imageLinks": {
                        "thumbnail": "https://books.googleusercontent.com/books/content?id=CCC&zoom=3"}}},
                    {},
                ]}
            return {"items": []}
        raise AssertionError(url)

    return answer


SEARCHES: dict[str, str] = {
    "mixed": "Kuma Kuma Kuma Bear",
    "google_down": "Overlord",
    "itunes_ebook_down": "Re:Zero",
    "all_down": "Tắt đèn",
    "vietnamese_query": "  Đắc   nhân\ttâm  ~a*b?c&d=e+f/g ",
    "long_query": "😀" * 80 + "ệ" * 80,
    "thirty_cap": "Cap",
    "too_short": " x ",
    "empty": "",
}


def run_search(case: str, query: str) -> dict[str, Any]:
    from abook.webui import cover_search

    answer = canned(case)
    seen: dict[str, Any] = {}

    def get_json(url: str) -> Any:
        reply = answer(url)
        seen[url] = reply
        if isinstance(reply, dict) and ERROR in reply:
            raise OSError(reply[ERROR])
        return reply

    with mock.patch.object(cover_search, "_get_json", get_json):
        expected = cover_search.search(query)
    return {"name": case, "query": query, "responses": dict(sorted(seen.items())), "requested": sorted(seen),
            "expected": expected}


ALLOWED_URLS = [
    "https://is1-ssl.mzstatic.com/image/thumb/x/1000x1000bb.jpg",
    "https://is12-ssl.mzstatic.com/image/thumb/x/1000x1000bb.jpg",
    "https://is-ssl.mzstatic.com/x.jpg",
    "https://covers.openlibrary.org/b/id/42-L.jpg",
    "https://covers.openlibrary.org:443/b/id/42-L.jpg",
    "HTTPS://COVERS.OPENLIBRARY.ORG/b/id/42-L.jpg",
    "https://books.google.com/books/content?id=1&zoom=0",
    "https://books.googleusercontent.com/books/content?id=1",
    "https://www.google.com/x.jpg",
    "http://covers.openlibrary.org/b/id/42-L.jpg",
    "https://127.0.0.1/x.jpg",
    "https://evil.example/x.jpg",
    "https://covers.openlibrary.org.evil.example/x.jpg",
    "https://evil.example/https://covers.openlibrary.org/x.jpg",
    "https://covers.openlibrary.org@evil.example/x.jpg",
    "file:///C:/Windows/win.ini",
    "ftp://covers.openlibrary.org/x.jpg",
    "//covers.openlibrary.org/x.jpg",
    "covers.openlibrary.org/x.jpg",
    "",
]


def build() -> dict[str, Any]:
    from abook.webui import cover_search, covers

    try:
        cover_search.download_image("http://192.168.1.1/admin.png")
    except covers.CoverError as exc:
        refusal = str(exc)
    else:  # pragma: no cover - the whole point of the allow-list
        raise AssertionError("download_image accepted a foreign host")
    return {"search": [run_search(case, query) for case, query in SEARCHES.items()],
            "allowed": [{"url": url, "allowed": cover_search.allowed_image_url(url)} for url in ALLOWED_URLS],
            "refusal": refusal}


def dumps(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    FILE.write_bytes(dumps(build()))


if __name__ == "__main__":
    main()
