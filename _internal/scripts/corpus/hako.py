r"""Khảo sát và tải truyện từ Hako (docln) vào kho dữ liệu `D:/Novels/ABook/Corpus/`.

Chạy bằng Python của máy có `cloudscraper` + `lxml` (`py`, 3.13) - KHÔNG phải runtime/.venv của dây chuyền.

    py scripts/corpus/hako.py survey --pages 5                 # xếp hạng truyện dịch (người) đã hoàn thành
    py scripts/corpus/hako.py survey --kind convert            # mục AI dịch (/ai-dich)
    py scripts/corpus/hako.py survey --kind sangtac            # sáng tác gốc tiếng Việt (/sang-tac)
    py scripts/corpus/hako.py download /truyen/259-toi-la-nhen-thi-sao --title "Kumo Desu Ga Nani Ka"
    py scripts/corpus/hako.py fetch-all                        # tải dần MỌI bộ (cả ba loại) chưa có trong _full

Tải là tải CẢ BỘ, vào `Corpus/_full/<tên>` (chủ sách 06-10: "đã tải là tải hết"; tìm thật nhiều truyện rồi tải dần
để lúc cần không phải tải - mạng thì dư). `fetch-all` mặc định lấy CẢ BA loại (truyendich, convert, sangtac) và
KHÔNG lọc nhãn nào (`--exclude-tags` rỗng): lọc thể loại / nguồn / chất lượng là việc của bước sau, đọc từ
`metadata.json` (địa chỉ `url`, nhãn, điểm đánh giá, lượt xem, tổng bình luận, TOÀN BỘ bình luận độc giả). Chọn chương cho
một việc cũng là việc của bước sau, không phải của bộ tải. Mỗi bộ: tải chương trước, bình luận sau; cả hai chạy lại
được đúng chỗ (bình luận nhớ trang kế trong chính `metadata.json`). `--no-comments` bỏ phần bình luận.

Động cơ tải lấy NGUYÊN từ `D:/Novels/Tools/NovelDownloader_Docln.py` của chủ sách (chỉ tham khảo, không sửa bản ấy):
  - giới hạn nhịp theo header: Hako gửi `X-RateLimit-Limit: 60` + `X-RateLimit-Remaining`; hạn mức dùng chung cho mọi
    luồng, nhịp gửi bắt đầu 0,55 s/yêu cầu và tự chậm lại khi gặp giới hạn ngắn (429 không kèm header hạn mức);
    429 thì chờ `Retry-After` / `X-RateLimit-Reset`, 503 thì nghỉ riêng nguồn đó 60 s, hết hạn mức thì chỉ một yêu cầu
    dò đường; trạng thái nhịp lưu ở `_full/.docln_rate_*.json` nên chạy lại vẫn nhớ;
  - IPv4 và IPv6 có hạn mức riêng (DualStackManager); máy không có IPv6 thì tự rút về IPv4, không chờ không kẹt;
  - 403 "chương có nội dung không phù hợp" ghi là chương bị trang rút (không thử lại); chương chỉ có ảnh ghi vào
    `metadata.json` (`image_only`) chứ không tính là lỗi; kiểm tra tuyến (bộ/chương) sau chuyển hướng, kiểm tra
    chương hợp lệ (`valid_text`), ghi file nguyên tử, sổ `.download_manifest.json` + kiểm sha256 để chạy lại đúng chỗ.
Khác bản gốc ở những chỗ một kho dữ liệu cần:
  - tham số dòng lệnh thay vì sửa hằng số trong file; không có bộ giám sát nền (chạy lại là làm tiếp);
  - nguồn không kết nối được (vd. docln.net, ln.hako.vn bị DNS về 127.0.0.1) bị nghỉ riêng 60 s, không kéo cả đường;
  - tên file chương = thứ tự trong mục lục (NNN.txt, đánh số từ 000, không đánh số lại khi thiếu chương); thư mục cũ
    chưa có sổ thì nhận lại file theo số thứ tự / tiêu đề;
  - `metadata.json` cạnh truyện: địa chỉ truyện trên Hako (`url`), thể loại, số từ, đánh giá, lượt xem, tổng bình luận,
    danh sách chương, chương thiếu / bị rút / chỉ có ảnh, bình luận (phẳng: mỗi bình luận có `id`, `parent` - trả lời
    thì `parent` khác `id` - tác giả, giờ, nội dung đầy đủ, lượt thích, chương nó nằm), lúc tải;
  - bình luận lấy qua `POST /comment/ajax_paging` (mỗi trang ~10 bình luận gốc, ~36 KB; GET `?page=N` KHÔNG phân trang):
    cần mã CSRF của đúng phiên HTTP đó, lấy một lần từ trang chủ; trả lời lồng trong nhóm thì lấy luôn, nút "xem thêm
    trả lời" (nếu có) không bấm;
  - DNS: mạng có bộ phân giải đẩy docln.net / ln.hako.vn về 127.0.0.1 (router/ISP) thì trong CHÍNH tiến trình này tra
    địa chỉ qua DNS-over-HTTPS của Cloudflare rồi nối thẳng tới IP, giữ SNI/Host là tên thật (không đụng DNS/hosts hệ thống).
Giải mã nội dung bảo vệ (`chapter-c-protected`: base64 + XOR theo `data-k`) theo bản gốc.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import ipaddress
import json
import logging
import os
import re
import socket
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

# cloudscraper + lxml chỉ có ở `py`; runtime/.venv thiếu cả hai -> nạp mềm để phần logic thuần (nhịp, sổ, phân tích
# mục lục khi có lxml) vẫn import và thử được.
try:
    import cloudscraper
except ImportError:  # pragma: no cover - phụ thuộc môi trường
    cloudscraper = None
try:
    from lxml import html
except ImportError:  # pragma: no cover
    html = None
try:
    import requests
    from requests.exceptions import ConnectionError as HttpConnectionError
    from requests.utils import get_environ_proxies
except ImportError:  # pragma: no cover
    requests = None

    class HttpConnectionError(OSError):
        pass

    def get_environ_proxies(url):
        return {}
try:
    from urllib3.connection import HTTPSConnection
    from urllib3.connectionpool import HTTPSConnectionPool
    from urllib3.util import connection as urllib3_connection
except ImportError:  # pragma: no cover
    HTTPSConnection = HTTPSConnectionPool = urllib3_connection = None

SOURCES = ("https://docln.net", "https://docln.sbs", "https://ln.hako.vn")
HAKO_URL = SOURCES[0]  # địa chỉ ghi vào metadata `url`
CORPUS = Path("D:/Novels/ABook/Corpus")
FULL = CORPUS / "_full"
STOP_FILE = FULL / "STOP_FETCH"  # tạo file này để `fetch-all` dừng sau bộ đang tải
# Khảo sát nằm CÙNG kho (repo riêng tư, xem scripts/corpus/manifest.py): có bình luận người đọc chép từ Hako.
SURVEY_DIR = CORPUS / "_survey"
# Bộ lọc của trang danh sách Hako: truyện dịch bởi người, AI dịch ("convert"), sáng tác tiếng Việt.
KINDS = ("truyendich", "convert", "sangtac")
STATUSES = ("hoanthanh", "dangtienhanh", "tamngung")
# Chủ sách 06-10: tải TẤT CẢ, lọc sau từ metadata -> không nhãn nào bị loại mặc định.
EXCLUDE_TAGS: tuple[str, ...] = ()
COLLECTIONS = ("truyen", "ai-dich", "sang-tac")

# --- nhịp tải: các hằng số của NovelDownloader_Docln.py, giữ nguyên ---
REQUEST_TIMEOUT = (10, 30)
MAX_ATTEMPTS = 6
SOURCE_COOLDOWN = 60
DEFAULT_RATE_LIMIT = 60
# Drain the 60-request quota well within its reset period, while avoiding the separate short-burst limiter seen
# with simultaneous requests.
REQUEST_INTERVAL = 0.55
RATE_STATE_NAME = ".docln_rate.json"
RATE_SAFETY_MARGIN = 2
MANIFEST_NAME = ".download_manifest.json"
MANIFEST_VERSION = 1
PROGRESS_INTERVAL = 25
DEFAULT_WORKERS = 12
ILLUSTRATION_LABELS = ("minh họa", "minh hoạ")
LOGGER = logging.getLogger("hako")
RESTRICTED_CHAPTER_NOTICE = "Chương này có chứa nội dung không phù hợp"


class ChapterUnavailable(Exception):
    """The site explicitly withdrew this chapter; retries cannot fix it."""


class ImageOnlyChapter(Exception):
    def __init__(self, image_count):
        self.image_count = image_count
        super().__init__(f"Trang chỉ có {image_count} ảnh, không có văn bản")


class PageNotFound(Exception):
    """HTTP 404: thử lại chỉ tốn hạn mức."""


class EmptyMenu(ValueError):
    """Trang truyện có thật nhưng mục lục không có chương văn bản."""


def configure_logging() -> None:
    if LOGGER.handlers:
        return
    LOGGER.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
    LOGGER.addHandler(console)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_write(path, text):
    temporary = path.with_name(path.name + ".part")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path, data):
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def valid_text(text, title):
    lines = text.splitlines()
    return bool(lines and lines[0].strip() == title and "\n".join(lines[1:]).strip())


def route_identity(path):
    """Titles in URLs can change; collection and numeric IDs identify content."""
    parts = unquote(urlparse(path).path).strip("/").split("/")
    if len(parts) not in (2, 3) or parts[0] not in COLLECTIONS:
        return None
    book_id = parts[1].partition("-")[0]
    if not book_id.isdecimal():
        return None
    chapter_id = None
    if len(parts) == 3:
        if not parts[2].startswith("c"):
            return None
        chapter_id = parts[2][1:].partition("-")[0]
        if not chapter_id.isdecimal():
            return None
    return parts[0], book_id, chapter_id


def verify_book(directory, novel_path):
    directory = Path(directory)
    manifest = read_json(directory / MANIFEST_NAME)
    if (manifest.get("version") != MANIFEST_VERSION
            or manifest.get("novel_path") != novel_path
            or not manifest.get("complete") or not manifest.get("chapters")):
        return False
    for chapter in manifest["chapters"]:
        try:
            text = (directory / chapter["filename"]).read_text(encoding="utf-8-sig")
            if not valid_text(text, chapter["title"]) or digest(text) != chapter.get("sha256"):
                return False
        except (OSError, KeyError, UnicodeError):
            return False
    return True


# --- DNS: bộ phân giải của router/ISP có thể đẩy docln.net / ln.hako.vn về 127.0.0.1 ---
DOH_ENDPOINTS = ("https://cloudflare-dns.com/dns-query", "https://1.1.1.1/dns-query")
DOH_TTL_CAP = 300
_doh_cache: dict[tuple[str, int], tuple[float, list[str]]] = {}
_doh_lock = threading.Lock()


def _unusable(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.partition("%")[0])
    except ValueError:
        return True
    return ip.is_loopback or ip.is_unspecified


def system_addresses(host: str, family: int) -> list[str]:
    try:
        return [info[4][0] for info in socket.getaddrinfo(host, 443, family, socket.SOCK_STREAM)]
    except OSError:
        return []


def doh_lookup(host: str, family: int) -> list[str]:
    """Tra A / AAAA qua DNS-over-HTTPS (không qua hạn mức Hako); lỗi thì trả rỗng. Có nhớ tạm theo TTL."""
    key = (host, family)
    with _doh_lock:
        cached = _doh_cache.get(key)
        if cached and cached[0] > time.monotonic():
            return list(cached[1])
    if requests is None:
        return []
    record = 28 if family == socket.AF_INET6 else 1
    for endpoint in DOH_ENDPOINTS:
        try:
            reply = requests.get(endpoint, params={"name": host, "type": "AAAA" if record == 28 else "A"},
                                 headers={"accept": "application/dns-json"}, timeout=8)
            answers = [item for item in reply.json().get("Answer", []) if item.get("type") == record]
        except (OSError, ValueError):
            continue
        addresses = [item["data"] for item in answers if not _unusable(item.get("data", ""))]
        if addresses:
            ttl = min([DOH_TTL_CAP, *(int(item.get("TTL", 60)) for item in answers)])
            with _doh_lock:
                _doh_cache[key] = (time.monotonic() + max(30, ttl), addresses)
            return list(addresses)
    return []


def host_addresses(host: str, family: int) -> list[str]:
    """Hệ thống phân giải ra địa chỉ dùng được thì để hệ thống lo (trả rỗng); không (rỗng / loopback) thì DoH."""
    if any(not _unusable(address) for address in system_addresses(host, family)):
        return []
    return doh_lookup(host, family)


if HTTPSConnection is not None:
    class ResolvedHTTPSConnection(HTTPSConnection):
        """Nối tới IP do DoH tra khi DNS hệ thống vô dụng; SNI/Host/kiểm chứng chứng chỉ vẫn theo tên thật."""

        def _new_conn(self):
            family = socket.AF_INET6 if (self.source_address or ("",))[0] == "::" else socket.AF_INET
            addresses = host_addresses(self._dns_host, family)
            if not addresses:
                return super()._new_conn()
            error = None
            for address in addresses:
                try:
                    return urllib3_connection.create_connection(
                        (address, self.port), self.timeout, source_address=self.source_address,
                        socket_options=self.socket_options)
                except OSError as exc:
                    error = exc
            raise error

    class ResolvedHTTPSConnectionPool(HTTPSConnectionPool):
        ConnectionCls = ResolvedHTTPSConnection


class SourceManager:
    """Each thread owns its HTTP sessions; rate limiting is shared."""
    def __init__(self, sources, state_file=None, source_address=None, label="mặc định"):
        self.sources = list(sources)
        self.source_address = source_address
        self.label = label
        self.local = threading.local()
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.blocked_until = {source: 0 for source in self.sources}
        self.next_request = 0
        self.sessions = []
        self.state_file = state_file
        state = read_json(state_file) if state_file else {}
        self.global_blocked_until = time.monotonic() + max(0, state.get("resume_at", 0) - time.time())
        self.remaining = state.get("remaining")
        self.rate_limit = state.get("limit", DEFAULT_RATE_LIMIT)
        self.request_interval = max(REQUEST_INTERVAL, min(2.0, state.get("request_interval", REQUEST_INTERVAL)))
        self.inflight = 0
        self.probe_inflight = False
        self.quota_logged = False

    def persist_rate(self):
        if self.state_file:
            resume_at = max(self.next_request, self.global_blocked_until)
            write_json(self.state_file, {"resume_at": time.time() + max(0, resume_at - time.monotonic()),
                                         "remaining": self.remaining, "limit": self.rate_limit,
                                         "request_interval": self.request_interval})

    def record_response(self, response, source, probe=False, reserved=False):
        with self.lock:
            if reserved:
                self.inflight -= 1
            if probe:
                self.probe_inflight = False
            try:
                self.rate_limit = int(response.headers.get("X-RateLimit-Limit", DEFAULT_RATE_LIMIT))
            except ValueError:
                pass
            if response.status_code == 429:
                if "X-RateLimit-Limit" not in response.headers:
                    # The short-burst limiter has no quota headers. Learn its acceptable cadence and retain it
                    # across books/restarts.
                    self.request_interval = min(2.0, self.request_interval * 1.5)
                    self.next_request = max(self.next_request, time.monotonic() + self.request_interval)
                    LOGGER.info("Giới hạn ngắn %s: điều chỉnh nhịp gửi thành %.2fs/yêu cầu", self.label, self.request_interval)
                retry_after = response.headers.get("Retry-After", str(SOURCE_COOLDOWN))
                try:
                    delay = float(retry_after)
                except ValueError:
                    try:
                        delay = parsedate_to_datetime(retry_after).timestamp() - time.time()
                    except (ValueError, TypeError):
                        delay = SOURCE_COOLDOWN
                self.global_blocked_until = max(self.global_blocked_until, time.monotonic() + max(1, delay) + RATE_SAFETY_MARGIN)
                self.remaining = 0
                LOGGER.warning("HTTP 429 (%s, %s): đường này chờ %.1fs; limit=%s, remaining=%s, reset=%s",
                               self.label, source, max(1, delay) + RATE_SAFETY_MARGIN,
                               response.headers.get("X-RateLimit-Limit", "?"),
                               response.headers.get("X-RateLimit-Remaining", "?"),
                               response.headers.get("X-RateLimit-Reset", "?"))
            elif response.status_code == 503:
                self.blocked_until[source] = time.monotonic() + SOURCE_COOLDOWN
            try:
                remaining = max(0, int(response.headers["X-RateLimit-Remaining"]))
                if response.status_code == 429:
                    self.remaining = 0
                elif self.remaining is None or probe:
                    self.remaining = max(0, remaining - self.inflight)
                else:
                    # Responses may arrive out of order. Never restore quota from a stale response while other
                    # requests are reserved.
                    self.remaining = min(self.remaining, remaining)
                if not self.quota_logged:
                    LOGGER.info("Quota %s: %s lượt còn lại, hạn mức %s", self.label, self.remaining, self.rate_limit)
                    self.quota_logged = True
            except (KeyError, ValueError):
                if probe and response.status_code != 429:
                    self.remaining = None
            if self.remaining == 0:
                try:
                    reset = float(response.headers["X-RateLimit-Reset"]) - time.time()
                    self.global_blocked_until = max(self.global_blocked_until, time.monotonic() + max(0, reset) + RATE_SAFETY_MARGIN)
                except (KeyError, ValueError):
                    pass
            self.persist_rate()
            self.condition.notify_all()

    def request_slot(self, attempt):
        with self.condition:
            while True:
                now = time.monotonic()
                rotation = self.sources[attempt % len(self.sources):] + self.sources[:attempt % len(self.sources)]
                source = min(rotation, key=lambda item: max(now, self.blocked_until[item]))
                scheduled = max(now, self.next_request, self.blocked_until[source], self.global_blocked_until)
                delay = scheduled - now
                probe = self.remaining is not None and self.remaining <= 0
                if delay <= 0 and not (probe and (self.inflight or self.probe_inflight)):
                    self.inflight += 1
                    if self.remaining is not None:
                        self.remaining = max(0, self.remaining - 1)
                    self.probe_inflight = probe
                    self.next_request = now + self.request_interval
                    self.persist_rate()
                    return source, probe
                self.condition.wait(timeout=min(max(delay, REQUEST_INTERVAL), 1))

    def session(self, source):
        if cloudscraper is None:
            raise RuntimeError("thiếu gói cloudscraper - chạy bằng `py` (3.13) của máy, không phải runtime/.venv")
        if not hasattr(self.local, "sessions"):
            self.local.sessions = {}
        if source not in self.local.sessions:
            session = cloudscraper.create_scraper()
            # Keep cloudscraper's TLS adapter; only the connection class changes (DoH fallback, see above).
            pool_manager = session.get_adapter(source).poolmanager
            if HTTPSConnection is not None:
                pool_manager.pool_classes_by_scheme = {**pool_manager.pool_classes_by_scheme,
                                                       "https": ResolvedHTTPSConnectionPool}
            if self.source_address:
                # Binding its connections to one IP family without process-wide DNS monkeypatching.
                pool_manager.connection_pool_kw["source_address"] = self.source_address
            self.local.sessions[source] = session
            with self.lock:
                self.sessions.append(session)
        return self.local.sessions[source]

    def close(self):
        with self.lock:
            sessions, self.sessions = self.sessions, []
        for session in sessions:
            session.close()

    def fetch(self, path, attempt, form=None):
        """Một yêu cầu (GET; có `form` thì POST ajax); nguồn không kết nối được bị nghỉ riêng rồi thử ngay nguồn kế
        (không tốn một lượt thử). POST cần mã CSRF của đúng phiên: lần đầu của phiên tốn một lượt lấy mã (trả None)."""
        last_error = RuntimeError("không lấy được mã CSRF")
        for _ in range(len(self.sources) + 1):
            try:
                result = self._fetch_once(path, attempt, form)
                if result is not None:
                    return result
            except HttpConnectionError as error:
                last_error = error
                with self.lock:
                    now = time.monotonic()
                    if all(self.blocked_until[source] > now for source in self.sources):
                        break
        raise last_error

    def _fetch_once(self, path, attempt, form=None):
        source, probe = self.request_slot(attempt)
        recorded = False
        try:
            session = self.session(source)
            if form is None:
                response = session.get(source + path, timeout=REQUEST_TIMEOUT)
            elif getattr(session, "ln_token", None) is None:
                # Mã CSRF gắn với cookie của phiên này: lấy từ trang chủ (nhẹ hơn trang truyện), lượt kế mới POST.
                response = session.get(source + "/", timeout=REQUEST_TIMEOUT)
                recorded = True
                self.record_response(response, source, probe=probe, reserved=True)
                response.raise_for_status()
                found = re.search(r"""csrf-token" content="([^"]+)|var token = '([^']+)""", response.text)
                if not found:
                    raise ValueError("Trang chủ không có mã CSRF")
                session.ln_token = found.group(1) or found.group(2)
                return None
            else:
                response = session.post(source + path, data={**form, "_token": session.ln_token},
                                        headers={"X-Requested-With": "XMLHttpRequest"}, timeout=REQUEST_TIMEOUT)
            recorded = True
            self.record_response(response, source, probe=probe, reserved=True)
            if response.status_code == 419:
                session.ln_token = None  # phiên hết hạn: lượt thử sau lấy mã mới
                raise ValueError(f"HTTP 419 ({source}): mã CSRF hết hạn")
            if response.status_code == 404:
                raise PageNotFound(f"HTTP 404 ({source}{path})")
            if response.status_code == 403:
                tree = html.fromstring(response.content)
                for element in tree.xpath('//script | //style'):
                    element.drop_tree()
                message = " ".join(tree.text_content().split())[-600:]
                if RESTRICTED_CHAPTER_NOTICE in message:
                    message = message[message.index(RESTRICTED_CHAPTER_NOTICE):].split("Về Trang Chủ")[0].strip()
                    raise ChapterUnavailable(f"HTTP 403 ({source}): {message}")
                raise ValueError(f"HTTP 403 ({source}): {message}")
            response.raise_for_status()
            expected_identity = route_identity(path)
            if expected_identity is None:
                # Trang danh sách: chỉ cần vẫn là đúng trang ấy (không bị đẩy sang trang đăng nhập/chặn).
                if urlparse(response.url).path != urlparse(path).path:
                    raise ValueError(f"Chuyển hướng sang {response.url}")
            elif route_identity(response.url) != expected_identity:
                raise ValueError(f"Chuyển hướng sang {response.url}")
            return response, source
        except Exception as error:
            if not recorded:
                with self.condition:
                    self.inflight = max(0, self.inflight - 1)
                    self.probe_inflight = False
                    if isinstance(error, HttpConnectionError):
                        self.blocked_until[source] = time.monotonic() + SOURCE_COOLDOWN
                    self.condition.notify_all()
                broken = getattr(self.local, "sessions", {}).pop(source, None)
                if broken:
                    broken.close()
                    with self.lock:
                        if broken in self.sessions:
                            self.sessions.remove(broken)
            raise


def ipv6_usable(sources) -> bool:
    """Máy có đường IPv6 thật tới một nguồn không: AAAA phân giải ra địa chỉ không phải loopback VÀ có tuyến tới nó."""
    for source in sources:
        host = urlparse(source).hostname
        for address in system_addresses(host, socket.AF_INET6) + host_addresses(host, socket.AF_INET6):
            if _unusable(address):
                continue
            try:
                with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as probe:
                    probe.connect((address, 443))  # UDP: không gửi gì, chỉ hỏi bảng định tuyến
                return True
            except OSError:
                continue
    return False


class DualStackManager:
    """Use independent IPv4/IPv6 budgets, with connection-error fallback.

    Máy không có IPv6 (không AAAA / chỉ loopback / không tuyến) thì chỉ dựng đường IPv4: không có đường thứ hai để
    chờ hay thử.
    """

    def __init__(self, sources, state_file, ipv6_check=ipv6_usable):
        self.selection_lock = threading.Lock()
        self.unavailable_until = {}
        self.next_lane = 0
        proxies = get_environ_proxies(sources[0])
        if proxies.get("https") or proxies.get("all"):
            self.managers = [SourceManager(sources, state_file)]
            return
        state_file = Path(state_file)
        v4_state = state_file.with_name(".docln_rate_ipv4.json")
        self.managers = [SourceManager(sources, v4_state, ("0.0.0.0", 0), "IPv4")]
        if ipv6_check(sources):
            self.managers.append(SourceManager(sources, state_file.with_name(".docln_rate_ipv6.json"), ("::", 0), "IPv6"))
        else:
            LOGGER.info("Máy không có IPv6 tới Hako: chỉ dùng IPv4")

    def fetch(self, path, attempt, form=None):
        tried = set()
        last_error = None
        while len(tried) < len(self.managers):
            with self.selection_lock:
                now = time.monotonic()
                ordered = self.managers[self.next_lane:] + self.managers[:self.next_lane]
                candidates = [manager for manager in ordered if manager not in tried]
                connected = [manager for manager in candidates if self.unavailable_until.get(manager.label, 0) <= now]
                if connected:
                    candidates = connected

                def ready_at(manager):
                    with manager.lock:
                        ready = max(now, manager.next_request, manager.global_blocked_until,
                                    self.unavailable_until.get(manager.label, 0))
                        if manager.remaining == 0 and manager.inflight:
                            ready = max(ready, now + 1)
                        return ready

                manager = min(candidates, key=ready_at)
                self.next_lane = (self.managers.index(manager) + 1) % len(self.managers)
            tried.add(manager)
            try:
                return manager.fetch(path, attempt, form)
            except HttpConnectionError as error:
                last_error = error
                with self.selection_lock:
                    self.unavailable_until[manager.label] = time.monotonic() + SOURCE_COOLDOWN
                LOGGER.warning("Kết nối %s lỗi; thử đường còn lại: %s", manager.label, error)
        raise last_error

    def close(self):
        for manager in self.managers:
            manager.close()


def make_manager() -> DualStackManager:
    FULL.mkdir(parents=True, exist_ok=True)
    return DualStackManager(SOURCES, FULL / RATE_STATE_NAME)


# ---------------------------------------------------------------- phân tích trang

def _require_lxml():
    if html is None:
        raise RuntimeError("thiếu gói lxml - chạy bằng `py` (3.13) của máy, không phải runtime/.venv")


def parse_menu_tree(tree, novel_path):
    chapters = []
    seen = set()
    tags = tree.xpath('//ul[contains(concat(" ", normalize-space(@class), " "), " list-chapters ")]//a')
    book_identity = route_identity(novel_path)
    for tag in tags:
        title = " ".join(tag.text_content().split())
        path = urlparse(tag.get("href") or "").path
        volumes = tag.xpath('ancestor::section[contains(concat(" ", normalize-space(@class), " "), " volume-list ")][1]')
        volume_title = " ".join(volumes[0].xpath('./header//text()')).strip() if volumes else ""
        normalized_title = unicodedata.normalize("NFC", title).casefold()
        normalized_volume = unicodedata.normalize("NFC", volume_title).casefold().strip()
        image_volume = (normalized_volume == "manga"
                        or normalized_volume.startswith(("illustration", "fanart")))
        if image_volume or any(label in normalized_title or label in normalized_volume for label in ILLUSTRATION_LABELS):
            continue
        identity = route_identity(path)
        if not identity or not book_identity or identity[:2] != book_identity[:2] or identity[2] is None or not title:
            continue
        if path in seen:
            continue
        seen.add(path)
        chapters.append({"path": path, "title": title})
    if not chapters:
        raise EmptyMenu("Mục lục không có chương văn bản; không đánh dấu hoàn tất")
    digits = max(3, len(str(len(chapters))))
    for index, chapter in enumerate(chapters):
        chapter["filename"] = f"{index:0{digits}}.txt"
    return chapters


def parse_menu(content, novel_path):
    _require_lxml()
    return parse_menu_tree(html.fromstring(content), novel_path)


def decode_encrypted_content(data_k, data_c_str):
    chunks = json.loads(data_c_str)
    chunks.sort(key=lambda item: int(item[:4]))
    key = data_k.encode("utf-8")
    if not key or not chunks:
        raise ValueError("Nội dung mã hóa rỗng")
    decoded_html = bytearray()
    for chunk in chunks:
        payload = chunk[4:]
        payload += "=" * (-len(payload) % 4)
        raw = base64.b64decode(payload, validate=True)
        decoded_html.extend(byte ^ key[index % len(key)] for index, byte in enumerate(raw))
    return extract_paragraphs(html.fromstring("<div>" + decoded_html.decode("utf-8") + "</div>"))


def extract_paragraphs(element):
    paragraphs = []
    for paragraph in element.xpath(".//p"):
        hidden = any(
            "display:none" in (ancestor.get("style") or "").replace(" ", "").lower()
            for ancestor in [paragraph, *paragraph.iterancestors()]
        )
        if not hidden and paragraph.text_content().strip():
            paragraphs.append(paragraph.text_content().strip())
    if not paragraphs:
        # Inspect the decoded chapter body, not its title or page sidebar. Empty/error pages without visible images
        # must remain real failures.
        visible = copy.deepcopy(element)
        for node in list(visible.iterdescendants()):
            style = (node.get("style") or "").replace(" ", "").lower()
            if node.tag in ("script", "style") or node.get("hidden") is not None or "display:none" in style:
                if node.getparent() is not None:
                    node.drop_tree()
        images = visible.xpath('.//img[@src or @data-src or @data-lazy-src]')
        if images and not visible.text_content().strip():
            raise ImageOnlyChapter(len(images))
    return "\n\n".join(paragraphs)


def parse_chapter(content):
    _require_lxml()
    tree = html.fromstring(content)
    protected = tree.xpath('//div[@id="chapter-c-protected"]')
    if protected:
        key, chunks = protected[0].get("data-k"), protected[0].get("data-c")
        if not key or not chunks:
            raise ValueError("Thiếu dữ liệu nội dung mã hóa")
        text = decode_encrypted_content(key, chunks)
    else:
        containers = tree.xpath('//div[@id="chapter-content"]')
        text = extract_paragraphs(containers[0]) if containers else ""
    if not text:
        raise ValueError("Trang không có nội dung chương")
    return text


def _number(text: str) -> int:
    return int(re.sub(r"\D", "", text or "") or 0)


def _comment_text(node) -> str:
    """Nội dung bình luận giữ xuống dòng (`<br>` thành dòng mới); ảnh/emoji hình không có chữ thì bỏ."""
    node = copy.deepcopy(node)
    for br in node.xpath(".//br"):
        br.tail = "\n" + (br.tail or "")
    return "\n".join(line.strip() for line in node.text_content().splitlines()).strip()


def parse_comments(tree) -> list[dict]:
    """Mọi bình luận trong `tree` (gốc + trả lời lồng trong nhóm), phẳng: trả lời có `parent` khác `id`."""
    found = []
    for item in tree.xpath('//div[contains(@class,"ln-comment-item")]'):
        content = item.xpath('.//div[@data-comment-content]') or item.xpath('.//*[contains(@class,"ln-comment-content")]')
        text = _comment_text(content[0]) if content else ""
        if not text:
            continue
        author = item.xpath('.//a[contains(@class,"ln-username")]')
        when = item.xpath(".//time/@datetime")
        likes = "".join(item.xpath('.//span[contains(@class,"likecount")]//text()')).strip()
        # Dòng "chương nào" ngay trên nội dung: bình luận chương hiện ở trang bộ kèm tên chương.
        context = item.xpath('.//div[contains(@class,"flex-col")]/span[contains(@class,"text-sm")]/a')
        record = {
            "id": item.get("data-comment"),
            "parent": item.get("data-parent"),
            "author": " ".join(author[0].text_content().split()) if author else "",
            "author_id": (author[0].get("href") or "").rpartition("/")[2] if author else "",
            "time": when[0] if when else "",
            "text": text,
            "likes": _number(likes),
            "on": item.get("data-type") or "",
        }
        if context:
            record["chapter"] = {"title": " ".join(context[0].text_content().split()),
                                 "path": urlparse(context[0].get("href") or "").path}
        if item.get("data-spoiler") == "1":
            record["spoiler"] = True
        found.append(record)
    return found


def parse_series(content: bytes, path: str) -> dict:
    _require_lxml()
    tree = html.fromstring(content)
    title = " ".join(tree.xpath('string(//span[contains(@class,"series-name")])').split())
    if not title:
        raise ValueError("Không phải trang truyện (không có tên truyện)")
    chapters = parse_menu_tree(tree, path)
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
    last = tree.xpath('//div[contains(@class,"statistic-item")][.//div[normalize-space(.)="Lần cuối"]]//time/@datetime')
    # Bình luận trang đầu (~10 gốc mới nhất, kèm trả lời): độc giả hay nói "drop rồi à", khen chê, chỉ chỗ đọc raw/bản
    # Anh. Các trang sau do `crawl_comments` lấy. "Tổng bình luận (N)" là số của cả bộ (kể cả trả lời / bình luận chương).
    comments = parse_comments(tree)
    total = re.search(r"Tổng bình luận\s*\(([\d.,\s]+)\)", " ".join(tree.xpath('//*[contains(@class,"tab-title")]//text()')))
    kind = re.search(r"var comment_type = '(\w+)'", content.decode("utf-8", "replace"))
    type_id = re.search(r"var comment_typeid = '(\d+)'", content.decode("utf-8", "replace"))
    threads = re.match(r"\s*([\d.,]+)\s*Bình luận", tree.xpath('string(//section[contains(@class,"ln-comment")]/header)'))
    return {
        "path": path,
        "title": title,
        "genres": [" ".join(a.text_content().split()) for a in tree.xpath('//div[contains(@class,"series-gernes")]//a')],
        "status": info.get("Tình trạng", ""),
        "author": info.get("Tác giả", ""),
        "words": _number(stats.get("Số từ", "0")),
        "rating": stats.get("Đánh giá", ""),
        "views": _number(stats.get("Lượt xem", "0")),
        "comment_count": _number(total.group(1)) if total else None,
        "comment_threads": _number(threads.group(1)) if threads else None,
        "comment_type": kind.group(1) if kind else "series",
        "comment_typeid": type_id.group(1) if type_id else series_id(path).rpartition(":")[2],
        "chapters": chapters,
        "last_update": last[0] if last else "",
        "comments": comments,
        "comments_more": has_next_comment_page(tree),
        "summary": " ".join(" ".join(x.text_content().split()) for x in tree.xpath('//div[contains(@class,"summary-content")]'))[:600],
    }


# ---------------------------------------------------------------- tải

def fetch_parsed(manager, path, parse=lambda content: content):
    """Lấy một trang qua `manager` và phân tích; lỗi tạm thời thử lại tối đa MAX_ATTEMPTS lượt, đổi nguồn mỗi lượt."""
    errors = []
    for attempt in range(MAX_ATTEMPTS):
        try:
            response, _ = manager.fetch(path, attempt)
            return parse(response.content)
        except (PageNotFound, EmptyMenu, ChapterUnavailable):
            raise
        except Exception as error:  # noqa: BLE001 - mạng/Cloudflare/trang lạ: thử lại
            errors.append(str(error))
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(min(attempt + 1, len(SOURCES)))
    raise RuntimeError(f"không tải được {path}: " + " | ".join(dict.fromkeys(errors)))


def series_info(manager, path: str) -> dict:
    return fetch_parsed(manager, path, lambda content: parse_series(content, path))


def survey(pages: int, sort: str, kind: str = "truyendich", status: str = "hoanthanh") -> list[dict]:
    _require_lxml()
    manager = make_manager()
    try:
        found: dict[str, str] = {}
        for page in range(1, pages + 1):
            tree = fetch_parsed(manager, f"/danh-sach?{kind}=1&{status}=1&sapxep={sort}&page={page}", html.fromstring)
            for anchor in tree.xpath('//div[contains(@class,"series-title")]/a'):
                found.setdefault(urlparse(anchor.get("href")).path, anchor.get("title") or anchor.text_content().strip())
        results = []
        for index, path in enumerate(found, 1):
            try:
                info = series_info(manager, path)
            except Exception as exc:  # noqa: BLE001 - một truyện hỏng không làm hỏng cả bảng
                print(f"  bỏ {path}: {exc}", file=sys.stderr)
                continue
            info["chapter_count"] = len(info.pop("chapters"))
            results.append(info)
            print(f"  [{index}/{len(found)}] {info['title'][:50]:50} {info['words']:>9,} từ  {info['chapter_count']:>4} ch  {', '.join(info['genres'][:4])}")
    finally:
        manager.close()
    target = SURVEY_DIR / (f"hako_survey_{kind}.json" if status == "hoanthanh" else f"hako_survey_{kind}_{status}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(target, json.dumps(results, ensure_ascii=False, indent=1))
    print(f"ghi {target}")
    return results


def save_chapter(directory, filename, text):
    target = directory / filename
    if target.exists():
        if target.read_text(encoding="utf-8-sig") == text:
            return
        backup = directory / ".download_backups"
        backup.mkdir(exist_ok=True)
        old_bytes = target.read_bytes()
        backup_file = backup / (filename + "." + hashlib.sha256(old_bytes).hexdigest()[:12] + ".bak")
        if not backup_file.exists():
            backup_file.write_bytes(old_bytes)
    atomic_write(target, text)


def preserve_chapter_filenames(chapters, previous):
    """Filtering image volumes must not renumber already downloaded chapters."""
    old_chapters = previous.get("chapters", []) + previous.get("nontext", [])
    if not old_chapters:
        return
    old_by_identity = {route_identity(chapter["path"]): chapter for chapter in old_chapters}
    used = set()
    unassigned = []
    valid_names = [chapter.get("filename", "") for chapter in old_chapters]
    valid_names = [name for name in valid_names if Path(name).name == name
                   and Path(name).suffix == ".txt" and Path(name).stem.isdecimal()]
    for chapter in chapters:
        old = old_by_identity.get(route_identity(chapter["path"]), {})
        name = old.get("filename")
        if name in valid_names and name not in used:
            chapter["filename"] = name
            used.add(name)
        else:
            unassigned.append(chapter)
    next_index = max((int(Path(name).stem) for name in valid_names), default=-1) + 1
    digits = max([3, len(str(next_index + len(unassigned))),
                  *(len(Path(name).stem) for name in valid_names)])
    for chapter in unassigned:
        chapter["filename"] = f"{next_index:0{digits}}.txt"
        next_index += 1


def download_chapters(novel_path, directory, chapters, workers, manager):
    """Phần giữa của NovelDownloader_Docln._download_book: sổ + chạy lại đúng chỗ + tải song song. `chapters` là mục
    lục đã phân tích (path, title, filename). Trả về dict kết quả; `complete` chỉ đúng khi đủ chương và kiểm lại đạt."""
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / MANIFEST_NAME
    previous = read_json(manifest_path)
    preserve_chapter_filenames(chapters, previous)
    known_images = {route_identity(chapter["path"]): chapter for chapter in previous.get("nontext", [])
                    if chapter.get("kind") == "image_only" and isinstance(chapter.get("image_count"), int)
                    and chapter["image_count"] > 0}
    nontext = []
    text_candidates = []
    for chapter in chapters:
        old_image = known_images.get(route_identity(chapter["path"]))
        if (previous.get("novel_path") == novel_path and old_image
                and old_image.get("title") == chapter["title"]):
            nontext.append({**old_image, **chapter})
        else:
            text_candidates.append(chapter)
    chapters = text_candidates
    previous_by_path = {chapter["path"]: chapter for chapter in previous.get("chapters", [])}
    previous_by_identity = {route_identity(chapter["path"]): chapter for chapter in previous.get("chapters", [])}
    existing = {}
    by_name = {}
    for file in directory.glob("*.txt"):
        try:
            text = file.read_text(encoding="utf-8-sig")
            title = text.splitlines()[0].strip()
            if valid_text(text, title):
                existing.setdefault(title, []).append((file.name, text))
                by_name[file.name] = (title, text)
        except (OSError, UnicodeError, IndexError):
            continue
    first_pages = {}
    pending = []
    title_counts = {}
    for chapter in chapters:
        title_counts[chapter["title"]] = title_counts.get(chapter["title"], 0) + 1
    for chapter in chapters:
        old = previous_by_path.get(chapter["path"]) or previous_by_identity.get(route_identity(chapter["path"]))
        candidates = existing.get(chapter["title"], [])
        chosen = chosen_name = None
        if old:
            chosen = next((text for name, text in candidates
                           if name == old.get("filename") and digest(text) == old.get("sha256")), None)
        elif not previous.get("chapters") and by_name.get(chapter["filename"], ("",))[0] == chapter["title"]:
            # Thư mục tải bằng bản cũ (chưa có sổ): file NNN.txt đã đúng chỗ theo thứ tự mục lục thì nhận lại.
            chosen = by_name[chapter["filename"]][1]
        elif len(candidates) == 1 and title_counts[chapter["title"]] == 1:
            chosen_name, chosen = candidates[0]
        elif not previous.get("chapters"):
            # Tên trùng nhau ("Chương 01 ..." ở hai tập): Tools cũng đánh số theo thứ tự mục lục, chỉ khác số chữ số.
            chosen_name, chosen = next(((name, text) for name, text in candidates
                                        if Path(name).stem.isdigit() and Path(chapter["filename"]).stem.isdigit()
                                        and int(Path(name).stem) == int(Path(chapter["filename"]).stem)), (None, None))
        if chosen is not None:
            target = directory / chapter["filename"]
            if chosen_name and chosen_name != chapter["filename"] and not target.exists():
                # Bộ chuyển từ Tools đặt tên khác (vd 2 chữ số "05.txt"): ĐỔI TÊN file cũ sang tên theo mục lục, không
                # chép thành bản thứ hai cạnh nó (06-10: lần chạy thử đầu nhân đôi cả bộ). Nội dung giữ nguyên từng byte.
                os.replace(directory / chosen_name, target)
                existing[chapter["title"]] = [item for item in candidates if item[0] != chosen_name]
            else:
                save_chapter(directory, chapter["filename"], chosen)
            chapter["sha256"] = digest(chosen)
            chapter["source"] = "existing"
        else:
            pending.append(chapter)
    manifest = {"version": MANIFEST_VERSION, "novel_path": novel_path,
                "complete": False, "chapters": chapters, "nontext": nontext}
    write_json(manifest_path, manifest)
    completed = len(chapters) - len(pending)
    LOGGER.info("%s: có sẵn %s/%s, cần tải %s, %s luồng", directory.name, completed, len(chapters), len(pending), workers)

    def download(chapter):
        errors = []
        for attempt in range(MAX_ATTEMPTS):
            try:
                response, source = manager.fetch(chapter["path"], attempt)
                text = chapter["title"] + "\n\n" + parse_chapter(response.content) + "\n"
            except ImageOnlyChapter as image_page:
                return {"kind": "image_only", "image_count": image_page.image_count,
                        "reason": str(image_page), "source": source, "checked_at": time.time()}
            except ChapterUnavailable as error:
                return {"error": str(error), "unavailable": True}
            except PageNotFound as error:
                return {"error": str(error)}
            except Exception as error:  # noqa: BLE001
                errors.append(str(error))
                if attempt + 1 < MAX_ATTEMPTS:
                    time.sleep(min(attempt + 1, len(SOURCES)))
                continue
            save_chapter(directory, chapter["filename"], text)
            try:  # trang chương đã tải rồi: trang bình luận đầu của chương nằm sẵn trong đó, khỏi tốn thêm yêu cầu
                tree = html.fromstring(response.content)
                first = (parse_comments(tree), has_next_comment_page(tree))
            except Exception:  # noqa: BLE001 - bình luận lỗi không làm hỏng chương
                first = None
            return {"sha256": digest(text), "source": source, "first_comments": first}
        return {"error": " | ".join(dict.fromkeys(errors))}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(download, chapter): chapter for chapter in pending}
        for future in as_completed(futures):
            chapter = futures[future]
            try:
                chapter.update(future.result())
            except Exception as error:  # noqa: BLE001
                chapter["error"] = f"Lỗi lưu/giải mã: {error}"
            first = chapter.pop("first_comments", None)  # không đưa vào sổ (ghi lại sau mỗi chương)
            if first:
                first_pages[chapter_key(chapter["path"])] = first
            if chapter.get("kind") == "image_only":
                chapters.remove(chapter)
                nontext.append(chapter)
                LOGGER.info("BỎ QUA TRANG ẢNH: %s / %s / %s: %s", directory.name,
                            chapter["filename"], chapter["title"], chapter["reason"])
            elif chapter.get("sha256"):
                completed += 1
                if completed % PROGRESS_INTERVAL == 0 or completed == len(chapters):
                    LOGGER.info("%s: %s/%s", directory.name, completed, len(chapters))
            else:
                LOGGER.error("%s / %s / %s: %s", directory.name, chapter["filename"], chapter["title"], chapter["error"])
            write_json(manifest_path, manifest)
    manager.close()  # đóng kết nối của các luồng đã xong; luồng chính dùng lại được
    failed = [chapter for chapter in chapters if not chapter.get("sha256")]
    manifest["complete"] = bool(chapters) and not failed
    write_json(manifest_path, manifest)
    if manifest["complete"] and not verify_book(directory, novel_path):
        manifest["complete"] = False
        write_json(manifest_path, manifest)
        return {"complete": False, "store": directory.name, "error": "Kiểm tra file sau tải thất bại",
                "chapters": chapters, "nontext": nontext, "failed": [], "downloaded": completed,
                "first_pages": first_pages}
    LOGGER.info("%s: %s/%s chương; %s", directory.name, completed, len(chapters), "HOÀN TẤT" if manifest["complete"] else "CHƯA ĐỦ")
    result = {"complete": manifest["complete"], "store": directory.name, "downloaded": completed,
              "total": len(chapters), "failed": failed, "nontext": nontext, "chapters": chapters,
              "first_pages": first_pages}
    if not chapters:
        result["error"] = "Mục lục chỉ có trang ảnh, không có chương văn bản"
    return result


def folder_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip().rstrip(".")


COMMENT_FLUSH_PAGES = 20
COMMENT_MAX_PAGES = 5000
NEXT_PAGE_XPATH = ('//a[contains(@class,"paging_prevnext") and contains(concat(" ", normalize-space(@class), " "), " next ")'
                   ' and not(contains(@class,"disabled"))]')


def has_next_comment_page(tree) -> bool:
    return bool(tree.xpath(NEXT_PAGE_XPATH))


def comment_page(manager, kind: str, type_id: str, page: int) -> tuple[list[dict], bool]:
    """Một trang bình luận qua ajax: (các bình luận, còn trang sau). Lỗi tạm thời thử lại như trang thường."""
    errors = []
    form = {"type": kind, "type_id": type_id, "page": page}
    for attempt in range(MAX_ATTEMPTS):
        try:
            response, _ = manager.fetch("/comment/ajax_paging", attempt, form)
            data = response.json()
            if data.get("status") != "success":
                raise ValueError(f"trả lời {data.get('status')}: {str(data.get('message'))[:100]}")
            tree = html.fromstring("<div>" + data.get("html", "") + "</div>")
            return parse_comments(tree), has_next_comment_page(tree)
        except PageNotFound:
            raise
        except Exception as error:  # noqa: BLE001 - mạng/phiên hết hạn/trang lạ: thử lại
            errors.append(str(error))
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(min(attempt + 1, len(SOURCES)))
    raise RuntimeError(f"không lấy được trang bình luận {page}: " + " | ".join(dict.fromkeys(errors)))


def chapter_key(path: str) -> str:
    """Khoá luồng bình luận của một chương (số chương trong đường dẫn)."""
    identity = route_identity(path)
    return f"chapter:{identity[2]}" if identity and identity[2] else ""


def comment_threads(metadata: dict, chapters: list[dict]) -> list[tuple[str, str, str, dict | None]]:
    """Các luồng bình luận của một bộ: luồng của bộ trước, rồi luồng của từng chương (chương văn bản + chương ảnh).
    Mỗi luồng: (khoá, loại ajax, số, chương gắn vào). Bình luận chương là phần lớn bình luận của bộ ("Tổng bình luận")."""
    kind = metadata.get("comment_type", "series")
    type_id = str(metadata.get("comment_typeid", ""))
    threads = [(f"{kind}:{type_id}", kind, type_id, None)]
    for chapter in chapters:
        key = chapter_key(chapter["path"])
        if key:
            threads.append((key, "chapter", key.partition(":")[2], {"title": chapter["title"], "path": chapter["path"]}))
    return threads


def crawl_comments(manager, metadata: dict, threads, first_pages: dict, save, crawl: bool = True) -> None:
    """Đi hết các trang bình luận của bộ (luồng bộ rồi luồng từng chương). Trạng thái nằm trong `metadata`:
    `comments` (phẳng), `comment_pages` (khoá luồng -> trang kế cần lấy, 0 = luồng xong) và `comments_complete`;
    `save()` ghi định kỳ, nên đứt giữa chừng chạy lại thì làm tiếp từ trang đã nhớ. `first_pages` = trang đầu có sẵn
    trong trang bộ / trang chương vừa tải (khỏi tốn yêu cầu). Bình luận mới nhất đứng trước: bình luận mới đẩy trang
    xuống làm vài bình luận lặp lại, bỏ bằng `id`. `crawl=False` (`--no-comments`) chỉ nhận trang đầu có sẵn."""
    comments, pages = metadata["comments"], metadata["comment_pages"]
    known = {comment["id"] for comment in comments}
    unsaved = 0

    def add(items, context):
        fresh = [comment for comment in items if comment["id"] not in known]
        for comment in fresh:
            if context and comment.get("on") == "chapter":
                comment.setdefault("chapter", context)
        comments.extend(fresh)
        known.update(comment["id"] for comment in fresh)

    for key, kind, type_id, context in threads:
        if key not in pages and key in first_pages:
            items, more = first_pages[key]
            add(items, context)
            pages[key] = 2 if more else 0
        if not crawl:
            continue
        page = pages.get(key, 1)
        while page:
            try:
                items, more = comment_page(manager, kind, type_id, page)
            except Exception as error:  # noqa: BLE001 - dừng, chạy lại sẽ làm tiếp từ trang này
                LOGGER.error("%s: bình luận dừng ở %s trang %s: %s", metadata.get("title", ""), key, page, error)
                save()
                return
            add(items, context)
            page = page + 1 if more and items and page < COMMENT_MAX_PAGES else 0
            pages[key] = page
            unsaved += 1
            if unsaved >= COMMENT_FLUSH_PAGES:
                unsaved = 0
                save()
                LOGGER.info("%s: bình luận %s: %s bình luận", metadata.get("title", ""), key, len(comments))
    if crawl:
        metadata["comments_complete"] = all(pages.get(thread[0]) == 0 for thread in threads)
    save()


def download(path: str, title: str | None, workers: int, manager=None, info: dict | None = None,
             comments: bool = True) -> Path:
    own_manager = manager is None
    manager = manager or make_manager()
    try:
        info = info or series_info(manager, path)
        name = title or info["title"]
        # Tên thư mục = link truyện (chủ sách 06-10): "truyen-259-toi-la-nhen-thi-sao", "ai-dich-...", "sang-tac-...".
        # Bộ đã có trong kho dưới tên khác (bộ chuyển từ Tools, vd "Kumo Desu ga"; hay Hako đổi đuôi tên) được nhận theo
        # số truyện rồi ĐỔI TÊN sang link hiện tại - không bao giờ hai thư mục cho một bộ.
        folder = FULL / series_folder(path)
        if not folder.exists():
            old = folder_of_series(path)
            if old is not None:
                LOGGER.info("%s -> %s", old.name, folder.name)
                os.replace(old, folder)
        folder.mkdir(parents=True, exist_ok=True)
        result = download_chapters(path, folder, info["chapters"], workers, manager)
        chapters = result.get("chapters", [])
        nontext = result.get("nontext", [])
        missing = [f"{c['filename'].split('.')[0]} {c['title']}" for c in result.get("failed", [])
                   if not c.get("unavailable")]
        previous = read_json(folder / "metadata.json")
        resumed = previous.get("path") == path and "comment_pages" in previous
        metadata = {
            **{key: value for key, value in info.items() if key not in ("chapters", "comments", "comments_more")},
            "chapters": [c["title"] for c in sorted([*chapters, *nontext], key=lambda c: c["filename"])],
            "source": "hako",
            "url": f"{HAKO_URL}{path}",
            "folder": str(folder),
            "missing": sorted(missing),
            "unavailable": [{"filename": c["filename"], "title": c["title"], "reason": c.get("error", "")}
                            for c in result.get("failed", []) if c.get("unavailable")],
            "image_only": [{"filename": c["filename"], "title": c["title"], "image_count": c.get("image_count")}
                           for c in nontext],
            "complete": bool(result.get("complete")),
            "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            # Bình luận: trang 1 đã có sẵn trong trang truyện; trang sau lấy ở `crawl_comments`.
            "comments": previous["comments"] if resumed else [],
            "comment_pages": previous["comment_pages"] if resumed else {},
            "comments_complete": bool(previous.get("comments_complete")) if resumed else False,
        }
        for key, value in previous.items():  # giữ dấu vết cũ (tools_folder, moved_at, ...) của bộ chuyển từ Tools
            metadata.setdefault(key, value)

        def save():
            write_json(folder / "metadata.json", metadata)

        save()
        LOGGER.info("%s: %s chương văn bản, thiếu %s, bị rút %s, chỉ có ảnh %s -> %s", name, len(chapters) + len(nontext),
                    len(missing), len(metadata["unavailable"]), len(nontext), folder)
        threads = comment_threads(metadata, [*chapters, *nontext])
        first_pages = {**result.get("first_pages", {}),
                       threads[0][0]: (info.get("comments", []), bool(info.get("comments_more")))}
        crawl_comments(manager, metadata, threads, first_pages, save, comments)
        if comments:
            LOGGER.info("%s: %s bình luận (%s)", name, len(metadata["comments"]),
                        "đủ" if metadata["comments_complete"] else "CHƯA ĐỦ")
    finally:
        manager.close()
    return folder


def series_id(path_or_url: str) -> str:
    """Số truyện - cùng một bộ dù tên miền hay đuôi tên đổi. `/truyen/<số>` -> "<số>" (như trước, khớp `--skip-ids`
    của máy khác); `/ai-dich/<số>`, `/sang-tac/<số>` có dãy số RIÊNG nên mang tiền tố: "ai-dich:<số>"."""
    found = re.search(r"/(truyen|ai-dich|sang-tac)/(\d+)", path_or_url)
    if not found:
        return ""
    return found.group(2) if found.group(1) == "truyen" else f"{found.group(1)}:{found.group(2)}"


def series_folder(path_or_url: str) -> str:
    """Tên thư mục của bộ: phần link sau tên miền, "/" thành "-". Số truyện ở trong tên nên hai bộ không thể trùng."""
    found = re.search(r"/(truyen|ai-dich|sang-tac)/(\d+[^/?#]*)", path_or_url)
    if not found:
        raise ValueError(f"không phải link truyện Hako: {path_or_url}")
    return folder_name(f"{found.group(1)}-{found.group(2)}")


def folder_of_series(path: str) -> Path | None:
    """Thư mục trong `_full` đã mang bộ này (khớp số truyện ở `path` hoặc `url` của metadata), không có thì None."""
    wanted = series_id(path)
    if not wanted:
        return None
    for meta in sorted(FULL.glob("*/metadata.json")):
        data = read_json(meta)
        if series_id(str(data.get("path") or data.get("url") or "")) == wanted:
            return meta.parent
    return None


def known_ids() -> set[str]:
    """Bộ đã có trong `_full` (bản tải từ Hako ghi `path`; bản chuyển từ Tools ghi `url` docln)."""
    ids = set()
    for meta in FULL.glob("*/metadata.json"):
        data = read_json(meta)
        for key in ("path", "url"):
            if series_id(str(data.get(key) or "")):
                ids.add(series_id(str(data[key])))
    return ids


def complete_ids() -> set[str]:
    """Bộ đã tải XONG cả chương lẫn bình luận (`comments_complete`): `fetch-all` chỉ bỏ qua những bộ này, còn bộ mới
    có chương mà dở bình luận (hoặc tải bằng bản cũ, chưa có bình luận) thì làm tiếp - chương đã có không tải lại."""
    ids = set()
    for meta in FULL.glob("*/metadata.json"):
        data = read_json(meta)
        if data.get("comments_complete") and series_id(str(data.get("path") or data.get("url") or "")):
            ids.add(series_id(str(data.get("path") or data.get("url"))))
    return ids


def fetch_all(workers: int, pause: float, max_pages: int, kinds: tuple[str, ...] = KINDS,
              skip_ids: Path | None = None, statuses: tuple[str, ...] = STATUSES,
              exclude_tags: tuple[str, ...] = EXCLUDE_TAGS, comments: bool = True) -> None:
    """Đi hết các trang danh sách Hako, tải CẢ BỘ (chương rồi bình luận) mọi truyện chưa xong trong `_full`. Chạy lại =
    làm tiếp. `comments=False` (`--no-comments`): chỉ chương, và bộ đã có chương là xong.

    Mỗi bộ xong ghi một dòng vào `_full/_fetch_log.tsv`; `STOP_FILE` có mặt thì dừng sau bộ đang tải.
    Mặc định tải CẢ BA loại và KHÔNG bỏ nhãn nào (chủ sách 06-10: tải hết, lọc sau từ metadata); `exclude_tags` khác
    rỗng thì bộ mang nhãn đó bị bỏ và ghi vào `_full/_fetch_skipped.tsv` để chạy lại khỏi mở trang của nó lần nữa
    (bộ không có chương văn bản cũng ghi vào đấy). Hai máy chia việc bằng `statuses`
    (06-10: máy nhà hoanthanh, Mac dangtienhanh + tamngung); `skip_ids` = số truyện máy kia đã có (`known-ids`).
    """
    _require_lxml()
    manager = make_manager()
    have = complete_ids() if comments else known_ids()
    if skip_ids:
        have |= set(skip_ids.read_text(encoding="utf-8").split())
    log = FULL / "_fetch_log.tsv"
    skipped_log = FULL / "_fetch_skipped.tsv"
    if skipped_log.exists():
        have |= {line.split("\t")[1] for line in skipped_log.read_text(encoding="utf-8").splitlines() if "\t" in line}

    def skip(number: str, reason: str, title: str) -> None:
        have.add(number)
        with skipped_log.open("a", encoding="utf-8", newline="\n") as out:
            out.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{number}\t{reason}\t{title}\n")

    fetched = 0
    try:
        for kind, status in [(kind, status) for kind in kinds for status in statuses]:
            for page in range(1, max_pages + 1):
                tree = fetch_parsed(manager, f"/danh-sach?{kind}=1&{status}=1&sapxep=top&page={page}", html.fromstring)
                paths = [urlparse(a.get("href")).path for a in tree.xpath('//div[contains(@class,"series-title")]/a')]
                if not paths:
                    break
                for path in paths:
                    if STOP_FILE.exists():
                        LOGGER.info("gặp STOP_FETCH - dừng")
                        return
                    number = series_id(path)
                    if not number or number in have:
                        continue
                    try:
                        info = series_info(manager, path)
                        excluded = sorted(set(info["genres"]) & set(exclude_tags))
                        if excluded:
                            skip(number, ",".join(excluded), info["title"])
                            continue
                        folder = download(path, None, workers, manager, info, comments)
                    except EmptyMenu as exc:
                        skip(number, "không có chương văn bản", path)
                        LOGGER.info("  bỏ %s: %s", path, exc)
                        continue
                    except Exception as exc:  # noqa: BLE001 - một bộ hỏng không dừng cả lượt
                        LOGGER.error("  bỏ %s: %s", path, exc)
                        continue
                    have.add(number)
                    fetched += 1
                    files = len(list(folder.glob("*.txt")))
                    with log.open("a", encoding="utf-8", newline="\n") as out:
                        out.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{kind}\t{status}\t{path}\t{files}\t{folder.name}\n")
                    LOGGER.info("[%s] %s/%s trang %s: %s (%s chương)", fetched, kind, status, page, folder.name, files)
                    time.sleep(pause)
        LOGGER.info("hết danh sách: tải %s bộ mới", fetched)
    finally:
        manager.close()


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    configure_logging()
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
    d.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    d.add_argument("--out", type=Path, help="thư mục bộ đầy đủ (mặc định Corpus/_full)")
    d.add_argument("--no-comments", action="store_true", help="chỉ tải chương, không đi các trang bình luận")
    f = sub.add_parser("fetch-all")
    f.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    f.add_argument("--pause", type=float, default=5.0, help="giây nghỉ giữa hai bộ")
    f.add_argument("--max-pages", type=int, default=1000)
    f.add_argument("--kinds", default=",".join(KINDS), help="loại danh sách, cách nhau dấu phẩy: " + ",".join(KINDS))
    f.add_argument("--statuses", default=",".join(STATUSES), help="tình trạng, cách nhau dấu phẩy: " + ",".join(STATUSES))
    f.add_argument("--exclude-tags", default=",".join(EXCLUDE_TAGS), help="bỏ bộ mang một trong các nhãn này (mặc định '' = tải hết)")
    f.add_argument("--out", type=Path, help="thư mục bộ đầy đủ (mặc định Corpus/_full) - máy khác ngoài máy nhà")
    f.add_argument("--no-comments", action="store_true", help="chỉ tải chương, không đi các trang bình luận")
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
                  tuple(tag.strip() for tag in args.exclude_tags.split(",") if tag.strip()), not args.no_comments)
    elif args.command == "known-ids":
        print("\n".join(sorted(known_ids(), key=lambda value: (value.partition(":")[0] if ":" in value else "",
                                                               int(value.rpartition(":")[2])))))
    else:
        path = urlparse(args.path).path  # nhận cả địa chỉ đầy đủ
        identity = route_identity(path)
        if not identity or identity[2] is not None:
            parser.error(f"cần đường dẫn trang truyện (/truyen/<số>-<tên>, /ai-dich/..., /sang-tac/...), không phải {args.path!r}")
        download(path, args.title, args.workers, comments=not args.no_comments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
