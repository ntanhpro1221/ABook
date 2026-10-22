"""a96 V4: every low-resource measurement is durable and readable by Studio."""
from types import SimpleNamespace

import pytest

from abook.config import build_settings
from abook.models import ResourceLevel
from abook.pipeline import BookPipeline
from abook.resource_manager import AdaptiveResourceManager, ResourceSnapshot


def test_low_disk_gate_shows_every_measurement_logs_once_then_clears(tmp_path, monkeypatch):
    settings = build_settings()
    manager = AdaptiveResourceManager(settings, tmp_path)
    samples = iter([8, 9, 40])
    manager.snapshot = lambda **kwargs: ResourceSnapshot(20, 16, next(samples), 0, 60, 6000, 8000, 0, 0, 60)
    # Resource hysteresis remains production policy; advance only its idle clock.
    manager._last_pressure_at = -1000
    pipeline = BookPipeline.__new__(BookPipeline)
    pipeline.settings, pipeline.resources = settings, manager
    pipeline.resource_updates = None
    pipeline._wait_pause_or_stop = lambda: 0
    pipeline._last_resource_level = ResourceLevel.MAXIMUM
    pipeline.paths = SimpleNamespace(root=tmp_path)
    pipeline.tts = SimpleNamespace(unload_all=lambda: None, unload_idle_models=lambda **kwargs: None)
    events, notices, writes = [], [], []
    pipeline.emit = lambda *args: events.append(args)
    pipeline.log = lambda text: None
    pipeline.notifier = SimpleNamespace(notify=lambda *args, **kwargs: notices.append(args))
    pipeline.db = SimpleNamespace(event=lambda *args: writes.append(args))
    sleeps = []
    def sleep(seconds):
        sleeps.append(seconds)
        manager._last_pressure_at = -1000
    monkeypatch.setattr("abook.pipeline.time.sleep", sleep)
    pipeline._resource_gate("analysis")
    # Trang nhận MỌI lần đo; sổ chỉ ghi khi loại thiếu đổi hay mỗi 60 giây (cổng đo lại mỗi 2 giây).
    waits = [args for args in writes if args[1] == "RESOURCE_WAIT"]
    assert len(waits) == 1 and waits[0][3]["disk_free_gb"] == 8
    shown = [args[1] for args in events if args[0] == "resource_wait" and args[1]]
    assert len(shown) == 2
    for details, free in zip(shown, [8, 9]):
        assert details["disk_path"] == str(tmp_path.resolve())
        assert details["disk_free_gb"] == free
        assert details["disk_threshold_gb"] == 12
        assert details["disk_to_free_gb"] == pytest.approx(12 - free)
        assert str(12 - free) in details["reason"]
    assert writes[-1][1] == "RESOURCE_READY"
    assert sleeps == [2, 2]
    assert len(notices) == 1


def test_critical_disk_reason_names_shortage_and_path(tmp_path):
    manager = AdaptiveResourceManager(build_settings(), tmp_path)
    decision = manager.decide(ResourceSnapshot(20, 16, 4, 0, 60, 6000, 8000, 0, 0, 60))
    assert decision.critical
    assert "thiếu dung lượng đĩa" in decision.reason.casefold()
    assert str(tmp_path.resolve()) in decision.reason
    assert "5.0 GB" in decision.reason


def test_resource_wait_survives_new_store_reader_and_clears(tmp_path):
    from abook.project import create_or_open_project
    from abook.webui import store
    source = tmp_path / "chapter.txt"
    source.write_text("Nội dung thử trạng thái chờ.", encoding="utf-8")
    paths, db, _settings = create_or_open_project([source], tmp_path / "books", build_settings(), "Test")
    db.update_book(status="analyzing", stage="analysis")
    details = AdaptiveResourceManager(build_settings(), paths.root).waiting_details(
        ResourceSnapshot(20, 16, 8, 0, 60, 6000, 8000, 0, 0, 60)
    )
    db.event("warning", "RESOURCE_WAIT", details["reason"], details)
    first = store.summarize(paths.root, running=True)
    assert first["resourceWait"] == details
    assert first["statusLabel"] == details["reason"]
    assert "giải phóng thêm hơn 4.0 GB" in first["statusLabel"]
    assert store.summarize(paths.root, running=True)["resourceWait"] == details
    assert any(item["text"] == details["reason"] for item in store.activity(paths.root))
    assert store.summarize(paths.root, running=False)["resourceWait"] is None
    db.event("info", "RESOURCE_READY", "Đã đủ tài nguyên; đang làm tiếp.")
    assert store.summarize(paths.root, running=True)["resourceWait"] is None
    db.event("warning", "RESOURCE_WAIT", details["reason"], details)
    db.update_book(status="analyzing", stage="analysis")
    assert store.summarize(paths.root, running=True)["resourceWait"] is None


def test_ram_wait_details_update_with_measurement(tmp_path):
    manager = AdaptiveResourceManager(build_settings(), tmp_path)
    details = manager.waiting_details(ResourceSnapshot(20, 1, 100, 0, 60, 6000, 8000, 0, 0, 60))
    assert details["ram_free_gb"] == 1
    assert details["ram_to_free_gb"] == details["ram_threshold_gb"] - 1
    assert "RAM còn 1.0 GB" in details["reason"]
