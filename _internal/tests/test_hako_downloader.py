"""Bộ tải Hako (`scripts/corpus/hako.py`): nhịp theo header, hai đường IPv4/IPv6, DNS-over-HTTPS, chạy lại đúng chỗ, bình luận.

Viết bằng `unittest` để chạy được cả hai nơi: runtime/.venv (3.11, KHÔNG có lxml/cloudscraper -> phần phân tích HTML và tải
chương tự bỏ qua, ghi rõ lý do) và `py -m unittest tests.test_hako_downloader` (3.13, có lxml -> chạy đủ). Mọi lệnh mạng
đều là hàng giả: không test nào chạm Hako.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from requests.structures import CaseInsensitiveDict

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("hako_under_test", ROOT / "scripts" / "corpus" / "hako.py")
hako = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hako)

NEED_LXML = unittest.skipIf(hako.html is None, "venv này không có lxml - chạy bằng `py -m unittest` (3.13)")
SOURCES = hako.SOURCES
META = '<meta charset="utf-8">'  # trang thật có thẻ này; thiếu nó lxml đọc bytes theo latin-1


class FakeResponse:
    def __init__(self, status=200, headers=None, content=b"", url="", text=None):
        self.status_code = status
        self.headers = CaseInsensitiveDict(headers or {})
        self.content = content
        self.url = url
        self.text = text if text is not None else content.decode("utf-8", "replace")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return json.loads(self.content)


class FakeSession:
    """Phiên giả: ghi lại các yêu cầu, trả lời theo hàm `answer(method, url, data)`."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, None))
        return self.answer("GET", url, None)

    def post(self, url, data=None, **kwargs):
        self.calls.append(("POST", url, data))
        return self.answer("POST", url, data)

    def close(self):
        pass


def manager_with(session, **kwargs):
    manager = hako.SourceManager(SOURCES, **kwargs)
    manager.session = lambda source: session
    return manager


class RateTests(unittest.TestCase):
    def test_429_honours_retry_after_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "rate.json"
            manager = hako.SourceManager(SOURCES, state)
            manager.record_response(FakeResponse(429, {"Retry-After": "45", "X-RateLimit-Limit": "60",
                                                       "X-RateLimit-Remaining": "0"}), SOURCES[0])
            self.assertGreater(manager.global_blocked_until - time.monotonic(), 45)
            resumed = hako.SourceManager(SOURCES, state)
            self.assertGreater(resumed.global_blocked_until - time.monotonic(), 45)
            self.assertEqual(resumed.remaining, 0)

    def test_short_burst_limiter_slows_the_cadence_and_remembers_it(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "rate.json"
            manager = hako.SourceManager(SOURCES, state)
            self.assertEqual(manager.request_interval, hako.REQUEST_INTERVAL)
            manager.record_response(FakeResponse(429, {"Retry-After": "10"}), SOURCES[0])  # không có header hạn mức
            self.assertGreater(manager.request_interval, hako.REQUEST_INTERVAL)
            self.assertEqual(hako.SourceManager(SOURCES, state).request_interval, manager.request_interval)

    def test_quota_exhaustion_does_not_slow_the_cadence(self):
        manager = hako.SourceManager(SOURCES)
        manager.record_response(FakeResponse(429, {"Retry-After": "60", "X-RateLimit-Limit": "60"}), SOURCES[0])
        self.assertEqual(manager.request_interval, hako.REQUEST_INTERVAL)

    def test_503_rests_only_that_source(self):
        manager = hako.SourceManager(SOURCES)
        manager.record_response(FakeResponse(503), SOURCES[0])
        self.assertGreater(manager.blocked_until[SOURCES[0]], time.monotonic() + 50)
        self.assertEqual(manager.blocked_until[SOURCES[1]], 0)
        source, _ = manager.request_slot(0)
        self.assertNotEqual(source, SOURCES[0])

    def test_remaining_header_is_shared_by_all_threads_and_decrements_per_slot(self):
        manager = hako.SourceManager(SOURCES)
        manager.record_response(FakeResponse(200, {"X-RateLimit-Remaining": "12"}), SOURCES[0])
        _, probe = manager.request_slot(0)
        self.assertFalse(probe)
        self.assertEqual(manager.remaining, 11)
        self.assertLessEqual(manager.next_request - time.monotonic(), hako.REQUEST_INTERVAL)

    def test_exhausted_quota_allows_one_probe_then_recovers(self):
        manager = hako.SourceManager(SOURCES)
        manager.remaining = 0
        _, probe = manager.request_slot(0)
        self.assertTrue(probe)
        done = threading.Event()
        result = []

        def second():
            result.append(manager.request_slot(0))
            done.set()

        thread = threading.Thread(target=second, daemon=True)
        thread.start()
        self.assertFalse(done.wait(0.1))  # chờ: chỉ một yêu cầu dò đường được bay
        manager.record_response(FakeResponse(200, {"X-RateLimit-Remaining": "2"}), SOURCES[0], probe=True, reserved=True)
        self.assertTrue(done.wait(2))
        self.assertFalse(result[0][1])
        self.assertEqual(manager.remaining, 1)

    def test_a_stale_response_cannot_restore_reserved_quota(self):
        manager = hako.SourceManager(SOURCES)
        manager.remaining = 5
        manager.request_slot(0)
        manager.record_response(FakeResponse(200, {"X-RateLimit-Remaining": "59"}), SOURCES[0], reserved=True)
        self.assertEqual(manager.remaining, 4)


class FetchTests(unittest.TestCase):
    def test_connection_error_rests_that_source_and_tries_the_next_one(self):
        class Dead(hako.HttpConnectionError):
            pass

        def answer(method, url, data):
            if url.startswith(SOURCES[0]):
                raise Dead("refused")
            return FakeResponse(200, {"X-RateLimit-Remaining": "50"}, b"ok", url)

        session = FakeSession(answer)
        manager = manager_with(session)
        manager.request_interval = 0  # thử nhanh
        response, source = manager.fetch("/truyen/1-a/c2-b", 0)
        self.assertEqual(source, SOURCES[1])
        self.assertGreater(manager.blocked_until[SOURCES[0]], time.monotonic() + 50)
        self.assertEqual(manager.inflight, 0)

    def test_404_is_not_retried_and_a_redirect_to_another_book_is_refused(self):
        manager = manager_with(FakeSession(lambda m, url, d: FakeResponse(404, {}, b"", url)))
        manager.request_interval = 0
        with self.assertRaises(hako.PageNotFound):
            manager.fetch("/truyen/1-a", 0)
        manager = manager_with(FakeSession(lambda m, url, d: FakeResponse(200, {}, b"x", SOURCES[0] + "/truyen/2-b")))
        manager.request_interval = 0
        with self.assertRaises(ValueError):
            manager.fetch("/truyen/1-a", 0)
        manager = manager_with(FakeSession(lambda m, url, d: FakeResponse(200, {}, b"x", SOURCES[0] + "/truyen/1-renamed")))
        manager.request_interval = 0
        self.assertEqual(manager.fetch("/truyen/1-a", 0)[1], SOURCES[0])  # đổi đuôi tên thì vẫn là bộ ấy

    def test_a_list_page_redirected_elsewhere_is_refused(self):
        manager = manager_with(FakeSession(lambda m, url, d: FakeResponse(200, {}, b"x", SOURCES[0] + "/login")))
        manager.request_interval = 0
        with self.assertRaises(ValueError):
            manager.fetch("/danh-sach?truyendich=1&page=1", 0)

    @NEED_LXML
    def test_restricted_chapter_notice_is_unavailable_not_a_retry(self):
        body = (META + "<html><body><p>" + hako.RESTRICTED_CHAPTER_NOTICE + " bị rút. Về Trang Chủ</p></body></html>").encode()
        manager = manager_with(FakeSession(lambda m, url, d: FakeResponse(403, {}, body, url)))
        manager.request_interval = 0
        with self.assertRaises(hako.ChapterUnavailable):
            manager.fetch("/truyen/1-a/c2-b", 0)

    def test_post_fetches_the_csrf_token_once_per_session_then_posts_it(self):
        def answer(method, url, data):
            if method == "GET":
                return FakeResponse(200, {}, b"", url, text='<meta name="csrf-token" content="TOK123">')
            return FakeResponse(200, {}, b'{"status":"success","html":""}', url)

        session = FakeSession(answer)
        manager = manager_with(session)
        manager.request_interval = 0
        form = {"type": "series", "type_id": "5", "page": 2}
        manager.fetch("/comment/ajax_paging", 0, form)
        manager.fetch("/comment/ajax_paging", 0, {**form, "page": 3})
        self.assertEqual([call[0] for call in session.calls], ["GET", "POST", "POST"])
        self.assertTrue(session.calls[0][1].endswith("/"))
        self.assertEqual(session.calls[1][2]["_token"], "TOK123")
        self.assertEqual(session.calls[2][2]["page"], 3)

    def test_an_expired_csrf_token_is_dropped_so_the_next_try_refetches_it(self):
        session = FakeSession(lambda m, url, d: FakeResponse(419, {}, b"", url))
        session.ln_token = "OLD"
        manager = manager_with(session)
        manager.request_interval = 0
        with self.assertRaises(ValueError):
            manager.fetch("/comment/ajax_paging", 0, {"page": 2})
        self.assertIsNone(session.ln_token)


class DualStackTests(unittest.TestCase):
    def build(self, folder, ipv6):
        with patch.object(hako, "get_environ_proxies", return_value={}):
            return hako.DualStackManager(SOURCES, Path(folder) / "rate.json", ipv6_check=lambda sources: ipv6)

    def test_a_machine_without_ipv6_gets_one_ipv4_lane_and_never_waits_for_a_second(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = self.build(folder, False)
            self.assertEqual([lane.label for lane in manager.managers], ["IPv4"])
            with patch.object(hako.SourceManager, "fetch", autospec=True, return_value=("response", "source")) as fetch:
                self.assertEqual(manager.fetch("/truyen/1-a", 0), ("response", "source"))
                self.assertIs(fetch.call_args.args[0], manager.managers[0])

    def test_two_lanes_have_separate_state_and_the_waiting_lane_is_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = self.build(folder, True)
            ipv4, ipv6 = manager.managers
            self.assertNotEqual(ipv4.state_file, ipv6.state_file)
            ipv4.remaining, ipv6.remaining = 60, 3
            ipv6.global_blocked_until = time.monotonic() + 60
            with patch.object(hako.SourceManager, "fetch", autospec=True, return_value=("r", "s")) as fetch:
                manager.fetch("/truyen/1-a", 0)
                self.assertIs(fetch.call_args.args[0], ipv4)
            self.assertEqual(ipv6.remaining, 3)

    def test_a_lane_that_cannot_connect_falls_back_to_the_other(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = self.build(folder, True)
            calls = []

            def fetch(lane, path, attempt, form=None):
                calls.append(lane.label)
                if lane.label == "IPv4":
                    raise hako.HttpConnectionError("no route")
                return "response", "source"

            with patch.object(hako.SourceManager, "fetch", fetch):
                self.assertEqual(manager.fetch("/truyen/1-a", 0), ("response", "source"))
                manager.fetch("/truyen/1-b", 0)
            self.assertEqual(calls, ["IPv4", "IPv6", "IPv6"])  # lần hai không còn thử đường hỏng

    def test_ipv6_probe_is_false_when_nothing_resolves_or_only_loopback_does(self):
        with patch.object(hako, "system_addresses", return_value=[]), patch.object(hako, "host_addresses", return_value=[]):
            self.assertFalse(hako.ipv6_usable(SOURCES))
        with patch.object(hako, "system_addresses", return_value=["::1"]), patch.object(hako, "host_addresses", return_value=[]):
            self.assertFalse(hako.ipv6_usable(SOURCES))


class DnsTests(unittest.TestCase):
    def setUp(self):
        hako._doh_cache.clear()

    def doh(self, addresses):
        class Reply:
            def json(self_inner):
                return {"Answer": [{"type": 1, "data": a, "TTL": 120} for a in addresses]}
        return Reply()

    def test_a_sinkholed_name_is_resolved_over_https_and_cached(self):
        with patch.object(hako, "system_addresses", return_value=["127.0.0.1"]), \
                patch.object(hako.requests, "get", return_value=self.doh(["104.21.52.100"])) as get:
            self.assertEqual(hako.host_addresses("docln.net", socket.AF_INET), ["104.21.52.100"])
            self.assertEqual(hako.host_addresses("docln.net", socket.AF_INET), ["104.21.52.100"])
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.kwargs["params"], {"name": "docln.net", "type": "A"})
        self.assertEqual(get.call_args.kwargs["headers"], {"accept": "application/dns-json"})

    def test_a_working_system_resolver_is_left_alone(self):
        with patch.object(hako, "system_addresses", return_value=["104.21.47.104"]), \
                patch.object(hako.requests, "get") as get:
            self.assertEqual(hako.host_addresses("docln.sbs", socket.AF_INET), [])
        get.assert_not_called()

    def test_doh_failure_returns_nothing_so_the_system_path_reports_the_error(self):
        with patch.object(hako, "system_addresses", return_value=[]), \
                patch.object(hako.requests, "get", side_effect=OSError("offline")):
            self.assertEqual(hako.host_addresses("docln.net", socket.AF_INET), [])

    def test_loopback_answers_from_doh_are_ignored(self):
        with patch.object(hako, "system_addresses", return_value=[]), \
                patch.object(hako.requests, "get", return_value=self.doh(["127.0.0.1"])):
            self.assertEqual(hako.host_addresses("docln.net", socket.AF_INET), [])

    @unittest.skipIf(hako.HTTPSConnection is None, "không có urllib3")
    def test_the_connection_goes_to_the_doh_address_but_keeps_the_real_host_name(self):
        connection = hako.ResolvedHTTPSConnection("docln.net", 443)
        with patch.object(hako, "host_addresses", return_value=["104.21.52.100"]), \
                patch.object(hako.urllib3_connection, "create_connection", return_value="socket") as create:
            self.assertEqual(connection._new_conn(), "socket")
        self.assertEqual(create.call_args.args[0], ("104.21.52.100", 443))
        self.assertEqual(connection.host, "docln.net")  # SNI / Host / kiểm chứng chứng chỉ theo tên thật

    @unittest.skipIf(hako.HTTPSConnection is None, "không có urllib3")
    def test_the_ipv6_lane_asks_for_aaaa(self):
        connection = hako.ResolvedHTTPSConnection("docln.net", 443, source_address=("::", 0))
        with patch.object(hako, "host_addresses", return_value=["2606:4700::1"]) as lookup, \
                patch.object(hako.urllib3_connection, "create_connection", return_value="socket"):
            connection._new_conn()
        self.assertEqual(lookup.call_args.args[1], socket.AF_INET6)


class IdentityTests(unittest.TestCase):
    def test_route_identity_knows_all_three_collections_and_ignores_title_changes(self):
        for collection in ("truyen", "ai-dich", "sang-tac"):
            self.assertEqual(hako.route_identity(f"/{collection}/12-old/c34-x"), (collection, "12", "34"))
            self.assertEqual(hako.route_identity(f"/{collection}/12-new/c34-y"), hako.route_identity(f"/{collection}/12-old/c34-x"))
        self.assertIsNone(hako.route_identity("/thao-luan/5-x"))
        self.assertIsNone(hako.route_identity("/danh-sach?page=2"))

    def test_series_id_keeps_the_old_form_for_truyen_and_prefixes_the_others(self):
        self.assertEqual(hako.series_id("/truyen/767-x"), "767")
        self.assertEqual(hako.series_id("https://docln.net/truyen/767-x"), "767")
        self.assertEqual(hako.series_id("/ai-dich/767-x"), "ai-dich:767")
        self.assertEqual(hako.series_id("/sang-tac/9-x"), "sang-tac:9")
        self.assertEqual(hako.series_id("/thao-luan/9-x"), "")

    def test_known_and_complete_ids(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(hako, "FULL", Path(folder)):
            for name, data in {"a": {"path": "/truyen/1-a", "comments_complete": True},
                               "b": {"path": "/truyen/2-b"},  # tải bằng bản cũ: chưa có bình luận
                               "c": {"url": "https://docln.net/sang-tac/3-c", "comments_complete": True}}.items():
                (Path(folder) / name).mkdir()
                (Path(folder) / name / "metadata.json").write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(hako.known_ids(), {"1", "2", "sang-tac:3"})
            self.assertEqual(hako.complete_ids(), {"1", "sang-tac:3"})

    def test_fetch_all_defaults_download_everything(self):
        import inspect
        defaults = inspect.signature(hako.fetch_all).parameters
        self.assertEqual(defaults["kinds"].default, ("truyendich", "convert", "sangtac"))
        self.assertEqual(defaults["exclude_tags"].default, ())
        self.assertEqual(hako.EXCLUDE_TAGS, ())


class FilesTests(unittest.TestCase):
    def test_atomic_write_is_lf_and_leaves_no_part_file(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "a.txt"
            hako.atomic_write(target, "một\nhai\n")
            self.assertEqual(target.read_bytes(), "một\nhai\n".encode("utf-8"))
            self.assertEqual([item.name for item in Path(folder).iterdir()], ["a.txt"])

    def test_valid_text_needs_the_title_line_and_a_body(self):
        self.assertTrue(hako.valid_text("Chương 1\n\nNội dung\n", "Chương 1"))
        self.assertFalse(hako.valid_text("Chương 1\n\n", "Chương 1"))
        self.assertFalse(hako.valid_text("Chương 2\n\nNội dung", "Chương 1"))

    def test_verify_book_detects_a_changed_file(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            text = "Một\n\nNội dung\n"
            (directory / "000.txt").write_text(text, encoding="utf-8")
            manifest = {"version": hako.MANIFEST_VERSION, "novel_path": "/truyen/1-a", "complete": True,
                        "chapters": [{"filename": "000.txt", "title": "Một", "sha256": hako.digest(text)}]}
            hako.write_json(directory / hako.MANIFEST_NAME, manifest)
            self.assertTrue(hako.verify_book(directory, "/truyen/1-a"))
            self.assertFalse(hako.verify_book(directory, "/truyen/2-b"))
            (directory / "000.txt").write_text("Một\n\nSửa\n", encoding="utf-8")
            self.assertFalse(hako.verify_book(directory, "/truyen/1-a"))

    def test_a_series_folder_is_named_after_its_link(self):
        self.assertEqual(hako.series_folder("/truyen/259-con-nhen"), "truyen-259-con-nhen")
        self.assertEqual(hako.series_folder("https://docln.net/ai-dich/77-mot-bo"), "ai-dich-77-mot-bo")
        self.assertEqual(hako.series_folder("/sang-tac/5-ten/c9-chuong"), "sang-tac-5-ten")
        with self.assertRaises(ValueError):
            hako.series_folder("/tim-kiem?keywords=x")

    def test_an_old_folder_of_the_same_series_is_renamed_to_the_link(self):
        with tempfile.TemporaryDirectory() as root:
            full = Path(root)
            old = full / "Ten Cu"
            old.mkdir()
            hako.write_json(old / "metadata.json", {"url": "https://docln.net/truyen/259-ten-cu-tren-web"})
            (old / "000.txt").write_text("Một\n\nA\n", encoding="utf-8")
            info = {"title": "T", "chapters": [{"path": "/truyen/259-ten-moi/c1-x", "title": "Một", "filename": "000.txt"}]}
            with patch.object(hako, "FULL", full):
                folder = hako.download("/truyen/259-ten-moi", None, 1, Mock(), info, comments=False)
            self.assertEqual(folder.name, "truyen-259-ten-moi")
            self.assertEqual(sorted(p.name for p in full.iterdir()), ["truyen-259-ten-moi"])
            self.assertEqual((folder / "000.txt").read_text(encoding="utf-8"), "Một\n\nA\n")

    def test_a_tools_folder_is_renamed_in_place_even_with_repeated_titles(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            for name, text in {"00.txt": "Chương 1\n\nA\n", "01.txt": "Chương 1\n\nB\n", "02.txt": "Chương 2\n\nC\n"}.items():
                (directory / name).write_text(text, encoding="utf-8")
            chapters = [{"path": "/truyen/1-a/c1-x", "title": "Chương 1", "filename": "000.txt"},
                        {"path": "/truyen/1-a/c2-y", "title": "Chương 1", "filename": "001.txt"},
                        {"path": "/truyen/1-a/c3-z", "title": "Chương 2", "filename": "002.txt"}]
            result = hako.download_chapters("/truyen/1-a", directory, chapters, 1, Mock())
            self.assertTrue(result["complete"])
            self.assertEqual(sorted(p.name for p in directory.glob("*.txt")), ["000.txt", "001.txt", "002.txt"])
            self.assertEqual([(directory / n).read_text(encoding="utf-8").split("\n\n")[1] for n in ("000.txt", "001.txt", "002.txt")],
                             ["A\n", "B\n", "C\n"])


# ---------------------------------------------------------------------------------------------- bình luận (không cần lxml)

class CrawlTests(unittest.TestCase):
    def comments(self, *ids, on="series"):
        return [{"id": str(i), "parent": str(i), "text": f"c{i}", "on": on} for i in ids]

    def state(self):
        return {"comments": [], "comment_pages": {}, "comments_complete": False, "title": "T",
                "comment_type": "series", "comment_typeid": "5"}

    def test_first_pages_are_taken_for_free_and_the_rest_is_fetched_until_the_last_page(self):
        metadata = self.state()
        threads = [("series:5", "series", "5", None), ("chapter:9", "chapter", "9", {"title": "Ch9", "path": "/truyen/5-a/c9-b"})]
        pages = {("series", 2): (self.comments(3, 4), False), ("chapter", 1): (self.comments(7, on="chapter"), False)}
        asked = []

        def fake_page(manager, kind, type_id, page):
            asked.append((kind, page))
            return pages[(kind, page)]

        first = {"series:5": (self.comments(1, 2), True)}
        with patch.object(hako, "comment_page", fake_page):
            hako.crawl_comments(None, metadata, threads, first, lambda: None)
        self.assertEqual(asked, [("series", 2), ("chapter", 1)])  # trang 1 của bộ không bị lấy lại
        self.assertEqual([c["id"] for c in metadata["comments"]], ["1", "2", "3", "4", "7"])
        self.assertEqual(metadata["comment_pages"], {"series:5": 0, "chapter:9": 0})
        self.assertTrue(metadata["comments_complete"])
        self.assertEqual(metadata["comments"][-1]["chapter"]["title"], "Ch9")  # bình luận chương nhớ nó ở chương nào

    def test_a_failure_stops_the_crawl_and_the_rerun_continues_from_the_saved_page(self):
        metadata = self.state()
        threads = [("series:5", "series", "5", None)]
        saves = []

        def flaky(manager, kind, type_id, page):
            if page == 3:
                raise RuntimeError("mạng đứt")
            return self.comments(page * 10), True

        with patch.object(hako, "comment_page", flaky):
            hako.crawl_comments(None, metadata, threads, {}, lambda: saves.append(1))
        self.assertFalse(metadata["comments_complete"])
        self.assertEqual(metadata["comment_pages"]["series:5"], 3)
        self.assertTrue(saves)
        asked = []

        def healthy(manager, kind, type_id, page):
            asked.append(page)
            return self.comments(page * 10), page < 4

        with patch.object(hako, "comment_page", healthy):
            hako.crawl_comments(None, metadata, threads, {}, lambda: None)
        self.assertEqual(asked, [3, 4])  # không lấy lại trang 1-2
        self.assertTrue(metadata["comments_complete"])

    def test_a_comment_pushed_down_a_page_by_a_new_one_is_not_stored_twice(self):
        metadata = self.state()
        replies = {1: (self.comments(1, 2), True), 2: (self.comments(2, 3), False)}  # 2 bị đẩy sang trang sau
        with patch.object(hako, "comment_page", lambda m, k, t, page: replies[page]):
            hako.crawl_comments(None, metadata, [("series:5", "series", "5", None)], {}, lambda: None)
        self.assertEqual([c["id"] for c in metadata["comments"]], ["1", "2", "3"])

    def test_no_comments_option_keeps_only_the_free_first_pages_and_never_downgrades_a_finished_book(self):
        metadata = self.state()
        threads = [("series:5", "series", "5", None)]
        with patch.object(hako, "comment_page", side_effect=AssertionError("không được gọi")):
            hako.crawl_comments(None, metadata, threads, {"series:5": (self.comments(1), True)}, lambda: None, crawl=False)
        self.assertEqual(metadata["comment_pages"], {"series:5": 2})
        self.assertFalse(metadata["comments_complete"])
        metadata["comments_complete"] = True
        hako.crawl_comments(None, metadata, threads, {}, lambda: None, crawl=False)
        self.assertTrue(metadata["comments_complete"])

    def test_threads_cover_the_series_then_every_chapter(self):
        threads = hako.comment_threads({"comment_type": "series", "comment_typeid": "5"},
                                       [{"path": "/truyen/5-a/c11-x", "title": "A"}, {"path": "/truyen/5-a/c12-y", "title": "B"}])
        self.assertEqual([t[0] for t in threads], ["series:5", "chapter:11", "chapter:12"])
        self.assertEqual(threads[1][1:3], ("chapter", "11"))

    def test_comment_page_reads_json_and_retries_a_failed_status(self):
        calls = []

        class Manager:
            def fetch(self, path, attempt, form=None):
                calls.append((path, attempt, dict(form)))
                if attempt == 0:
                    return FakeResponse(200, {}, b'{"status":"error","message":"x"}'), "s"
                return FakeResponse(200, {}, json.dumps({"status": "success", "html": ""}).encode()), "s"

        if hako.html is None:
            self.skipTest("cần lxml để đọc html của trang bình luận")
        with patch.object(hako.time, "sleep"):
            items, more = hako.comment_page(Manager(), "series", "5", 2)
        self.assertEqual((items, more), ([], False))
        self.assertEqual(calls[0][2], {"type": "series", "type_id": "5", "page": 2})
        self.assertEqual(len(calls), 2)


# ---------------------------------------------------------------------------------------------------- cần lxml

MENU = (META + '<span class="series-name">Bo A</span><ul class="list-chapters">'
        '<li><a href="/truyen/1-bo-a/c10-mot">Mot</a></li><li><a href="/truyen/1-bo-a/c11-hai">Hai</a></li></ul>').encode()


def chapter_page(body, comments=""):
    return (f'{META}<div id="chapter-content"><p>{body}</p></div>{comments}').encode()


def comment_html(cid, parent, text, user="Nam", on="chapter"):
    return (f'<div class="ln-comment-group"><div id="ln-comment-{cid}" class="ln-comment-item" data-comment="{cid}" '
            f'data-parent="{parent}" data-type="{on}" data-typeid="10"><a class="ln-username" href="/thanh-vien/7">{user}</a>'
            f'<div class="ln-comment-content"><div data-comment-content>{text}</div></div>'
            f'<time datetime="2026-01-02T03:04:05+07:00">x</time><span class="likecount">3</span></div></div>')


class FakeManager:
    def __init__(self, pages):
        self.pages = pages
        self.asked = []
        self.closed = 0

    def fetch(self, path, attempt, form=None):
        self.asked.append(path)
        page = self.pages[path]
        if isinstance(page, Exception):
            raise page
        return FakeResponse(200, {}, page, "https://docln.net" + path), "https://docln.net"

    def close(self):
        self.closed += 1


@NEED_LXML
class ParseTests(unittest.TestCase):
    def test_menu_skips_illustrations_duplicates_and_other_books_and_numbers_from_zero(self):
        content = (META + '<section class="volume-list"><header>Minh họa</header><ul class="list-chapters">'
                   '<li><a href="/truyen/1-a/c1-x">Quyển 1</a></li></ul></section>'
                   '<section class="volume-list"><header>Tập 1</header><ul class="list-chapters">'
                   '<li><a href="/truyen/1-a/c2-m">Chương  1</a></li><li><a href="/truyen/1-a/c2-m">Lặp</a></li>'
                   '<li><a href="/truyen/9-z/c3-n">Bộ khác</a></li><li><a href="/truyen/1-renamed/c4-q">Chương 2</a></li>'
                   '</ul></section>').encode()
        chapters = hako.parse_menu(content, "/truyen/1-a")
        self.assertEqual([c["title"] for c in chapters], ["Chương 1", "Chương 2"])  # khoảng trắng gọn lại
        self.assertEqual([c["filename"] for c in chapters], ["000.txt", "001.txt"])

    def test_a_menu_with_no_text_chapter_is_an_empty_menu_not_a_success(self):
        with self.assertRaises(hako.EmptyMenu):
            hako.parse_menu(b"<html>Login</html>", "/truyen/1-a")

    def test_sang_tac_and_ai_dich_menus_parse(self):
        for collection in ("sang-tac", "ai-dich"):
            content = f'<ul class="list-chapters"><li><a href="/{collection}/5-a/c6-b">Ch</a></li></ul>'.encode()
            self.assertEqual(len(hako.parse_menu(content, f"/{collection}/5-a")), 1)

    def test_chapter_text_plain_hidden_encrypted_and_image_only(self):
        self.assertEqual(hako.parse_chapter('<div id="chapter-content"><p>Hello <b>world</b></p>'
                                            '<p style="display: none">ẩn</p></div>'.encode()), "Hello world")
        key = b"secret"
        payload = '<p>Tiếng Việt</p><p style="display:none">Ẩn</p><p>Đoạn hai</p>'.encode()
        chunks = []
        for index, part in enumerate([payload[:25], payload[25:]]):
            encoded = bytes(b ^ key[i % len(key)] for i, b in enumerate(part))
            chunks.append(f"{index:04}" + base64.b64encode(encoded).decode().rstrip("="))
        page = f'<div id="chapter-c-protected" data-k="secret" data-c=\'{json.dumps(chunks[::-1])}\'></div>'.encode()
        self.assertEqual(hako.parse_chapter(page), "Tiếng Việt\n\nĐoạn hai")
        with self.assertRaises(hako.ImageOnlyChapter) as found:
            hako.parse_chapter(b'<div id="chapter-content"><p><img src="a.jpg"><img src="b.jpg"></p></div>')
        self.assertEqual(found.exception.image_count, 2)
        with self.assertRaises(ValueError):
            hako.parse_chapter(b"<html>Access denied</html>")

    def test_series_page_gives_counts_rating_views_comment_totals_and_full_comments(self):
        long_text = "x" * 900
        page = (META + '<span class="series-name">Bộ A</span>'
                '<div class="statistic-item"><div>Đánh giá</div><div>4,88 / 32</div></div>'
                '<div class="statistic-item"><div>Lượt xem</div><div>20.314.941</div></div>'
                '<div class="statistic-item"><div>Số từ</div><div>854.049</div></div>'
                '<span class="sect-title tab-title">Tổng bình luận <span class="comments-count">(22627)</span></span>'
                '<section class="ln-comment"><header><h3>1965 Bình luận </h3></header>'
                + comment_html(1, 1, "dòng một<br>dòng hai") + comment_html(2, 1, long_text, "Lan")
                + '<a class="paging_item paging_prevnext next" href="?page=2">Sau</a></section>'
                + '<script>var comment_type = \'series\'; var comment_typeid = \'259\';</script>'
                + '<ul class="list-chapters"><li><a href="/truyen/259-a/c1-b">Ch</a></li></ul>').encode()
        info = hako.parse_series(page, "/truyen/259-a")
        self.assertEqual((info["rating"], info["views"], info["words"]), ("4,88 / 32", 20314941, 854049))
        self.assertEqual((info["comment_count"], info["comment_threads"]), (22627, 1965))
        self.assertEqual((info["comment_type"], info["comment_typeid"], info["comments_more"]), ("series", "259", True))
        first, second = info["comments"]
        self.assertEqual(first["text"], "dòng một\ndòng hai")
        self.assertEqual(len(second["text"]), 900)  # không cắt ngắn
        self.assertEqual((second["author"], second["author_id"], first["likes"], first["id"], first["parent"]), ("Lan", "7", 3, "1", "1"))
        self.assertEqual(first["time"], "2026-01-02T03:04:05+07:00")

    def test_a_reply_is_flat_with_a_different_parent(self):
        tree = hako.html.fromstring("<div>" + comment_html(5, 5, "gốc") + comment_html(6, 5, "trả lời") + "</div>")
        found = hako.parse_comments(tree)
        self.assertEqual([(c["id"], c["parent"]) for c in found], [("5", "5"), ("6", "5")])

    def test_a_series_page_without_a_title_is_not_a_series_page(self):
        with self.assertRaises(ValueError):
            hako.parse_series(b"<html><body>Cloudflare</body></html>", "/truyen/1-a")


@NEED_LXML
class DownloadTests(unittest.TestCase):
    def run_download(self, folder, pages, path="/truyen/1-bo-a", **kwargs):
        manager = FakeManager(pages)
        info = hako.parse_series(MENU, path)
        with patch.object(hako, "FULL", Path(folder)), patch.object(hako.time, "sleep"):
            result = hako.download(path, "Sách", 2, manager, info, **kwargs)
        return result, manager

    def pages(self, **extra):
        return {"/truyen/1-bo-a/c10-mot": chapter_page("Nội dung một", comment_html(100, 100, "hay")),
                "/truyen/1-bo-a/c11-hai": chapter_page("Nội dung hai"), **extra}

    def test_a_book_is_saved_with_url_and_comments_in_metadata_and_nothing_else_extra(self):
        with tempfile.TemporaryDirectory() as folder:
            result, manager = self.run_download(folder, self.pages(), comments=False)
            self.assertEqual(sorted(p.name for p in result.iterdir()), [".download_manifest.json", "000.txt", "001.txt", "metadata.json"])
            self.assertEqual((result / "000.txt").read_text(encoding="utf-8"), "Mot\n\nNội dung một\n")
            meta = json.loads((result / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["url"], "https://docln.net/truyen/1-bo-a")
            self.assertEqual(meta["path"], "/truyen/1-bo-a")
            self.assertTrue(meta["complete"])
            self.assertEqual(meta["comments"][0]["text"], "hay")  # trang bình luận đầu của chương lấy từ chính trang chương
            self.assertEqual(meta["comments"][0]["chapter"]["title"], "Mot")
            self.assertFalse(meta["comments_complete"])  # --no-comments: chưa đi hết các trang

    def test_a_rerun_downloads_no_chapter_again_and_a_resumed_comment_crawl_skips_finished_threads(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(hako, "comment_page", lambda m, k, t, page: ([], False)):
                result, first = self.run_download(folder, self.pages())
                meta = json.loads((result / "metadata.json").read_text(encoding="utf-8"))
                self.assertTrue(meta["comments_complete"])
                _, second = self.run_download(folder, self.pages())
            self.assertEqual(second.asked, [])
            self.assertTrue(hako.verify_book(result, "/truyen/1-bo-a"))
            meta = json.loads((result / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(len(meta["comments"]), 1)
            self.assertTrue(meta["comments_complete"])

    def test_a_folder_left_by_the_old_engine_is_picked_up_by_position_without_downloading(self):
        with tempfile.TemporaryDirectory() as folder:
            book = Path(folder) / "Sách"
            book.mkdir()
            (book / "000.txt").write_bytes("Mot\r\n\r\nBản cũ một\r\n".encode("utf-8"))  # bản cũ ghi CRLF
            (book / "metadata.json").write_text(json.dumps({"path": "/truyen/1-bo-a"}), encoding="utf-8")
            result, manager = self.run_download(folder, self.pages(), comments=False)
            self.assertEqual(manager.asked, ["/truyen/1-bo-a/c11-hai"])
            self.assertIn("Bản cũ một", (result / "000.txt").read_text(encoding="utf-8"))
            self.assertTrue(hako.verify_book(result, "/truyen/1-bo-a"))
            self.assertFalse((result / ".download_backups").exists())

    def test_a_withdrawn_chapter_is_recorded_without_retry_and_an_image_chapter_is_not_a_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            pages = self.pages()
            pages["/truyen/1-bo-a/c10-mot"] = hako.ChapterUnavailable("HTTP 403: bị rút")
            pages["/truyen/1-bo-a/c11-hai"] = b'<div id="chapter-content"><p><img src="a.jpg"></p></div>'
            result, manager = self.run_download(folder, pages, comments=False)
            meta = json.loads((result / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(manager.asked.count("/truyen/1-bo-a/c10-mot"), 1)
            self.assertEqual([u["filename"] for u in meta["unavailable"]], ["000.txt"])
            self.assertEqual(meta["image_only"], [{"filename": "001.txt", "title": "Hai", "image_count": 1}])
            self.assertEqual(meta["missing"], [])
            self.assertFalse(meta["complete"])

    def test_a_different_book_with_the_same_title_gets_its_own_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            first, _ = self.run_download(folder, self.pages(), comments=False)
            other_menu = MENU.replace(b"/truyen/1-bo-a", b"/truyen/2-bo-b")
            manager = FakeManager({"/truyen/2-bo-b/c10-mot": chapter_page("Khác"), "/truyen/2-bo-b/c11-hai": chapter_page("Khác nữa")})
            with patch.object(hako, "FULL", Path(folder)), patch.object(hako.time, "sleep"):
                second = hako.download("/truyen/2-bo-b", "Sách", 1, manager, hako.parse_series(other_menu, "/truyen/2-bo-b"), comments=False)
            self.assertNotEqual(first, second)
            self.assertIn("Nội dung một", (first / "000.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
