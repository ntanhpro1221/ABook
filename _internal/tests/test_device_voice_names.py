from abook.readaloud import windows


def test_windows_preserves_supplied_names_and_gender_for_both_clients(monkeypatch, tmp_path):
    monkeypatch.setattr(windows, "available", lambda: True)
    monkeypatch.setattr(windows, "_listed", None)
    monkeypatch.setattr(windows, "_run", lambda *_: {"voices": [
        {"id": "z", "name": "Vendor Mai", "language": "vi-VN", "gender": None},
        {"id": "a", "name": "Microsoft An - Vietnamese (Vietnam)", "language": "vi-VN", "gender": "Male"},
        {"id": "en", "name": "Microsoft David", "language": "en-US", "gender": "Male"},
    ]})
    listed = windows.voices(tmp_path)
    assert [(v.id, v.name, v.gender, v.online) for v in listed] == [
        ("device:a", "Microsoft An", "male", False),
        ("device:z", "Vendor Mai", "", False),
    ]
    assert windows.voices(tmp_path) == listed


def test_identical_windows_names_get_stable_numbers_only_when_needed(monkeypatch, tmp_path):
    monkeypatch.setattr(windows, "available", lambda: True)
    monkeypatch.setattr(windows, "_listed", None)
    raw = [{"id": id, "name": name, "language": "vi-VN"} for id, name in
           [("b", "Microsoft An"), ("c", "Microsoft Mai"), ("a", "Microsoft An")]]
    monkeypatch.setattr(windows, "_run", lambda *_: {"voices": raw})
    first = windows.voices(tmp_path)
    assert [(v.id, v.name) for v in first] == [
        ("device:a", "Microsoft An 1"), ("device:b", "Microsoft An 2"), ("device:c", "Microsoft Mai")]
    raw.reverse()
    assert windows.voices(tmp_path, refresh=True) == first
