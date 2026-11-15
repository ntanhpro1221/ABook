from scripts.check_ui_actions import inventory, icon_findings
from scripts import check_ui_actions as gate
import hashlib
import json


def test_new_destructive_callback_is_always_a_new_review_entry():
    before = inventory('onClick={() => remove.mutate("a")}', "ui/src/X.tsx")
    after = inventory('onClick={() => remove.mutate("b")}', "ui/src/X.tsx")
    assert before[0]["kind"] == "destructive"
    assert before[0]["id"] != after[0]["id"]


def test_async_ui_and_native_suspend_boundaries_are_inventoried():
    assert inventory('onClick={async () => await save()}', "ui/src/X.tsx")[0]["kind"] == "pending"
    assert inventory('suspend fun connect() {', "ui/X.kt")[0]["kind"] == "pending"
    assert inventory('Api.quiet("POST", "/save", {}, done)', "qml/X.qml")[0]["kind"] == "pending"


def test_event_listener_cleanup_is_not_user_data_loss():
    assert inventory('element.removeEventListener("error", failed)', "ui/src/X.tsx") == []


def test_named_removals_and_unsave_are_not_missed():
    for call in ("state.removeBookmark(id)", "source.deleteNote(id)", "model.unsave(links)"):
        assert inventory(call, "ui/src/X.tsx")[0]["kind"] == "destructive"


def test_a_second_identical_launch_or_delete_is_a_new_review_entry():
    for statement in ('scope.launch {', 'onClick={() => remove.mutate("a")}'):
        before = inventory(statement, "ui/src/X.tsx")
        after = inventory(statement + "\n" + statement, "ui/src/X.tsx")
        assert before[0]["id"] == after[0]["id"]
        assert after[1]["id"] != before[0]["id"]


def test_status_icon_slide_is_rejected_but_page_slide_is_allowed(tmp_path):
    folder = tmp_path / "mobile/android/app/src/main/java/vn/abook/player/ui"
    folder.mkdir(parents=True)
    source = folder / "Example.kt"
    source.write_text('AnimatedContent(targetState = icon, label = "download-icon", transitionSpec = { slideInVertically() })', encoding="utf-8")
    assert icon_findings(tmp_path)
    source.write_text('AnimatedContent(targetState = page, label = "sheet-page", transitionSpec = { slideInVertically() })', encoding="utf-8")
    assert not icon_findings(tmp_path)


def test_status_icon_cannot_indirectly_use_the_sliding_content_default(tmp_path):
    folder = tmp_path / "mobile/android/app/src/main/java/vn/abook/player/ui"
    folder.mkdir(parents=True)
    source = folder / "Example.kt"
    source.write_text('SwapContent(active, contentKey = { it }) { active -> if (active) StopIcon() else PlayIcon() }', encoding="utf-8")
    assert icon_findings(tmp_path)
    source.write_text('SwapContent(active, contentKey = { it }, inPlace = true) { active -> if (active) StopIcon() else PlayIcon() }', encoding="utf-8")
    assert not icon_findings(tmp_path)


def test_removing_the_confirmation_invalidates_review_even_if_delete_call_is_unchanged(tmp_path, monkeypatch):
    source = tmp_path / "ui/src/Example.tsx"
    source.parent.mkdir(parents=True)
    guarded = 'const accepted = await confirmAction();\nif (accepted) {\nremove.mutate("a");\n}\n'
    source.write_text(guarded, encoding="utf-8")
    review = tmp_path / "review.json"
    rows = inventory(guarded, "ui/src/Example.tsx")
    review.write_text(json.dumps([{**row, "source_sha256": hashlib.sha256(guarded.encode()).hexdigest(),
                                  "disposition": "confirmation", "guard": "confirmAction", "reason": "Explicit acceptance"}
                                 for row in rows]), encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "REVIEW", review)
    monkeypatch.setattr(gate, "scan", lambda: inventory(source.read_text(encoding="utf-8"), "ui/src/Example.tsx"))
    monkeypatch.setattr("sys.argv", ["check_ui_actions.py"])
    assert gate.main() == 0
    source.write_text('remove.mutate("a");\n', encoding="utf-8")
    assert gate.main() == 1
