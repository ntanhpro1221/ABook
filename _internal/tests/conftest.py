"""Đếm xem bộ test ngồi chờ bao lâu — và **không** bỏ chờ, vì bỏ chờ làm nó chậm đi.

`docs/OPTIMISATION_QUEUE.md` đề xuất một fixture `autouse` monkeypatch `time.sleep` thành
no-op, với lý do đường ống lùi dần bằng `time.sleep(min(8, 2**attempt))` và mỗi giây ấy là một
giây thật của người phát triển. Tôi đã làm đúng thế, rồi đo, và **đề xuất ấy sai**:

```
test_successful_confirmation_decode_clears_initial_asr_false_negative
   ngủ thật     5,09 giây
   ngủ giả     89,65 giây      <- chậm gấp 17 lần
   49.598.670 lần gọi time.sleep trong một module
```

Vì `pipeline._wait_for_resources` **chờ một điều kiện theo thời gian**: nó ngủ 2 giây rồi hỏi
lại bộ điều tiết, và bộ điều tiết chỉ nhả khi `stable_for` vượt `idle_seconds_before_ramp`
(20 giây) tính bằng `time.monotonic()`. Bỏ ngủ không rút ngắn 20 giây ấy — nó chỉ biến một
vòng **chờ** thành một vòng **quay tít**, đốt trọn một lõi CPU để tới cùng một mốc thời gian.

Bài học rộng hơn cái test này: `time.sleep` trong bộ test không phải lúc nào cũng là lãng phí.
Chỗ nào ngủ để *nhường lượt*, bỏ đi thì nhanh hơn; chỗ nào ngủ để *đợi đồng hồ*, bỏ đi thì chậm
hơn và ồn hơn. Nhìn từ ngoài hai chỗ giống hệt nhau.

Nên fixture này chỉ **đếm rồi ngủ thật**. Cái nó mua không phải tốc độ mà là **khả năng nhìn**:
ngày 2026-09-08 tôi giết hai lượt chạy vì tưởng bộ test treo — `time.sleep` không tốn CPU nên
CPU phẳng trông y hệt deadlock. Một dòng tổng kết nói bộ test đã ngồi chờ bao lâu phân biệt được
hai thứ ấy mà không phải đoán, và một con số nhảy vọt là dấu hiệu ai đó vừa thêm một vòng chờ.

Số thật, đo trên cả bộ ngày 2026-09-09:

```
2.521 test xanh trong 519 giây;  ngồi chờ 246 giây trong 102 lần time.sleep   (47%)
```

**Đừng nhầm với con số của chế độ bỏ ngủ**: ở đó nó ra 826 giây trong 11.724 lần, gấp trăm lần
số lượt gọi. Chênh lệch ấy không phải sai số đo — nó **chính là** bằng chứng cho kết luận ở
trên: khi `sleep` là no-op, vòng `_wait_for_resources` quay tít và gọi `sleep` hàng nghìn lần
để tới cùng một mốc đồng hồ mà một lần ngủ thật 2 giây đã tới.

Đặt `EBOOK_TESTS_REAL_SLEEP_OFF=1` để thật sự bỏ ngủ — chỉ dùng khi muốn đo lại kết luận trên,
đừng dùng để chạy bộ test nhanh hơn, vì nó không nhanh hơn.
"""
from __future__ import annotations

import os
import time
from collections.abc import Iterator

import pytest

_REAL_SLEEP = time.sleep
_TOTAL_SECONDS = 0.0
_CALLS = 0


def _counting_sleep(seconds: float) -> None:
    global _TOTAL_SECONDS, _CALLS
    _TOTAL_SECONDS += float(seconds)
    _CALLS += 1
    _REAL_SLEEP(seconds)


def _skipping_sleep(seconds: float) -> None:
    global _TOTAL_SECONDS, _CALLS
    _TOTAL_SECONDS += float(seconds)
    _CALLS += 1


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "real_sleep: test này cần time.sleep nguyên bản, đừng bọc nó",
    )


@pytest.fixture(autouse=True, scope="session")
def _app_data_in_a_temporary_folder(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Dữ liệu của app mà test không tự chỉ chỗ - nhất là khoá mã sách (webui/library.book_id: `book_ids.key` cạnh
    preferences.json, tạo lần đầu cần tới) - nằm trong thư mục tạm của phiên test, không bao giờ ở %LOCALAPPDATA%/ABook
    thật của người chạy test. Test tự đặt biến này (monkeypatch) thì theo test."""
    if os.environ.get("ABOOK_PREFERENCES"):
        yield
        return
    os.environ["ABOOK_PREFERENCES"] = str(tmp_path_factory.mktemp("app-data") / "preferences.json")
    try:
        yield
    finally:
        os.environ.pop("ABOOK_PREFERENCES", None)


@pytest.fixture(autouse=True, scope="session")
def _no_cast_discovery() -> Iterator[None]:
    """App không tìm loa / TV (webui/cast.py - M-SEARCH multicast ra mọi card mạng) trong bài thử: không gửi gì ra mạng
    của người chạy test, và một TV thật trong nhà không lọt vào danh sách máy mà bài thử đếm. Thử DLNA thì dùng loa giả
    (scripts/fake_renderer.py, tests/test_cast.py)."""
    previous = os.environ.get("ABOOK_CAST_DISCOVERY")
    os.environ["ABOOK_CAST_DISCOVERY"] = "0"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("ABOOK_CAST_DISCOVERY", None)
        else:
            os.environ["ABOOK_CAST_DISCOVERY"] = previous


@pytest.fixture(autouse=True, scope="session")
def _no_music_model_download() -> Iterator[None]:
    """Bộ phân tích nhạc chỉ-nghe (webui/music_student.py) không tải gói model từ Hugging Face trong bài thử: bài cần model
    trỏ ABOOK_MUSIC_STUDENT_DIR vào gói có sẵn, còn lại thì bài nhập ở trạng thái "chưa phân tích" như máy chưa tải gói."""
    previous = os.environ.get("ABOOK_MUSIC_STUDENT_DOWNLOAD")
    os.environ["ABOOK_MUSIC_STUDENT_DOWNLOAD"] = "0"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("ABOOK_MUSIC_STUDENT_DOWNLOAD", None)
        else:
            os.environ["ABOOK_MUSIC_STUDENT_DOWNLOAD"] = previous


@pytest.fixture(autouse=True, scope="session")
def _no_ffmpeg_download() -> Iterator[None]:
    """Bộ đọc nhạc (webui/ffmpeg_setup.py) không tải ffmpeg từ PyPI trong bài thử: máy thử có imageio_ffmpeg nên không cần tải;
    bài thử nào cần đường tải thì thay studio_setup.download bằng bản giả."""
    previous = os.environ.get("ABOOK_FFMPEG_DOWNLOAD")
    os.environ["ABOOK_FFMPEG_DOWNLOAD"] = "0"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("ABOOK_FFMPEG_DOWNLOAD", None)
        else:
            os.environ["ABOOK_FFMPEG_DOWNLOAD"] = previous


@pytest.fixture(autouse=True)
def _count_sleeping(request: pytest.FixtureRequest) -> Iterator[None]:
    """Bọc `time.sleep` để đếm. Vẫn ngủ thật, trừ khi có người bật công tắc đo.

    Vá thẳng vào module `time` chứ không vá `abook.pipeline.time`, vì hai cái là **một
    đối tượng**: `import time` trong pipeline trỏ tới chính module ấy. Ghi ra đây để lần sau
    không ai tưởng mình đang vá hẹp hơn thực tế.
    """
    if request.node.get_closest_marker("real_sleep") is not None:
        yield
        return
    if os.environ.get("EBOOK_TESTS_REAL_SLEEP_OFF"):
        time.sleep = _skipping_sleep
    else:
        time.sleep = _counting_sleep
    try:
        yield
    finally:
        time.sleep = _REAL_SLEEP


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:  # noqa: ANN001
    if not _CALLS:
        return
    skipped = bool(os.environ.get("EBOOK_TESTS_REAL_SLEEP_OFF"))
    terminalreporter.write_line("")
    terminalreporter.write_line(
        f"[conftest] {'BỎ QUA' if skipped else 'ngồi chờ'} {_TOTAL_SECONDS:.0f} giây "
        f"trong {_CALLS} lần time.sleep."
        + ("  (đây là phép đo, không phải cách chạy nhanh hơn)" if skipped else "")
    )
