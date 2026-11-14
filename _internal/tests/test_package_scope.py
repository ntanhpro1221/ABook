from abook.webui import book_wishes, package_scope


def fixture(monkeypatch, *, ambiguous=False):
    rows = [dict(stableId=f"c1_s{i}", textSha256=f"{i:064x}", kind="dialogue", speaker="Người gác", text=f"Câu thử {i}.") for i in range(12)]
    chapters = [dict(id=1, title="Chương thử"), dict(id=2, title="Chương khác")]

    class Index:
        def __init__(self, _folder):
            self.chapters = chapters

        def chapter(self, number):
            return next((chapter for chapter in chapters if chapter["id"] == number), None)

        def segments(self, chapter):
            return rows if chapter["id"] == 1 else []

    cast = [dict(name="NPC_LOCAL::c1::guard", displayName="Người gác", voice={"preset": "test"})]
    if ambiguous:
        cast.append(dict(name="NPC_LOCAL::c2::guard", displayName="Người gác", voice={"preset": "test"}))
    monkeypatch.setattr(book_wishes, "Lines", Index)
    monkeypatch.setattr(book_wishes, "people", lambda _folder: cast)
    monkeypatch.setattr(package_scope.book_edits, "load", lambda _folder: {"wishes": {"speakers": {"c1_s2": {
        "speaker": "Khách", "text_sha256": f"{2:064x}", "requested_at": 1}}}})


def test_package_uses_manual_ranges_and_never_fabricates_scene_markers(monkeypatch, tmp_path):
    fixture(monkeypatch)
    view = package_scope.package_chapter(tmp_path, 1)
    assert len(view["lines"]) == 12
    assert all(line["scene"] is None and not line["sceneBreak"] for line in view["lines"])
    assert len({line["current"] for line in view["lines"]}) == 1
    assert view["lines"][2]["wish"]["value"] == "Khách"
    assert view["next"] == 2 and view["previous"] is None
    assert package_scope.package_chapter(tmp_path, 99) is None
    assert package_scope.package_contents(tmp_path)["chapters"][0]["speech"] == 12
    assert list(tmp_path.iterdir()) == []


def test_package_ambiguous_display_labels_do_not_merge_opaque_people(monkeypatch, tmp_path):
    fixture(monkeypatch, ambiguous=True)
    view = package_scope.package_chapter(tmp_path, 1)
    assert len({line["current"] for line in view["lines"]}) == 12
    assert all(line["current"].startswith("line:") for line in view["lines"])
