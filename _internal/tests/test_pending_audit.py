"""Regression gate for scripts/pending_audit.py: async controls must show a waiting state on the control itself."""
from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pending_audit as audit


def sites(reader, tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return [(site.control, covered) for site, covered in reader(path, name)]


def test_web_mutation_on_a_shared_button_needs_the_returned_promise(tmp_path):
    text = """
    export function A() {
      return <>
        <Button disabled={save.isPending} onClick={() => save.mutate(x)}>Lưu</Button>
        <Button onClick={() => settled(save.mutateAsync(x))}>Lưu</Button>
        <IconButton label="Tải" icon={Download} loading={get.isPending} onClick={() => get.mutate()} />
        <button type="button" onClick={() => remove.mutate(id)}><PendingIndicator pending={remove.isPending}><X /></PendingIndicator>Bỏ</button>
        <button type="button" onClick={() => remove.mutate(id)}>Bỏ</button>
        <Button onClick={() => deletion.confirm({ run: () => remove.mutateAsync() })}>Xoá</Button>
        <Button onClick={() => setOpen(true)}>Mở</Button>
      </>;
    }"""
    assert sites(audit.web_sites, tmp_path, "a.tsx", text) == [
        ("Button", False), ("Button", True), ("IconButton", True), ("button", True), ("button", False)]


def test_web_named_handlers_are_resolved_in_the_same_file(tmp_path):
    text = """
    const restart = async () => { await playBook(book); };
    const stop = () => { void api("/stop", { method: "POST" }); };
    export const B = () => <><ActionButton label="Từ đầu" onClick={restart} /><Button onClick={stop}>Dừng</Button></>;
    """
    assert sites(audit.web_sites, tmp_path, "b.tsx", text) == [("ActionButton", True), ("Button", False)]


def test_android_launch_needs_a_pending_argument(tmp_path):
    text = """
    @Composable
    fun Sheet() {
        TextAction(S.go, { scope.launch { repo.go() } }, "go")
        TextAction(S.go, { busy = true; scope.launch { try { repo.go() } finally { busy = false } } }, "go2", pending = busy)
        MenuRow(S.done, "done", pending = marking, onClick = { scope.launch { repo.done() } }) { ink -> CheckIcon(ink) }
        IconAction(S.retry, { send("retry") { repo.find() } }, "retry")
        TextAction(S.close, { dismiss() }, "close")
    }
    fun send(tag: String, work: suspend () -> Unit) { scope.launch { work() } }
    """
    assert sites(audit.android_sites, tmp_path, "S.kt", text) == [
        ("TextAction", False), ("TextAction", True), ("MenuRow", True), ("IconAction", False)]


def test_a_composable_screen_that_launches_is_not_an_action_helper(tmp_path):
    text = """
    @Composable
    fun OtherSheet(repo: Repo) { val scope = rememberCoroutineScope(); scope.launch { repo.load() } }
    @Composable
    fun Row() { Box(Modifier.pressable { sheets.show { OtherSheet(repo) } }) {} }
    """
    assert sites(audit.android_sites, tmp_path, "R.kt", text) == []


def test_qt_buttons_own_their_api_request_but_not_a_backend_call(tmp_path):
    text = """
    Item {
        function save() { Api.call("POST", "/x", {}, function() {}) }
        function reload() { store.request("GET", "/y", null, function() {}) }
        Button { text: "Lưu"; onActivated: root.save() }
        Button { text: "Tải lại"; onActivated: root.reload() }
        Button { text: "Thử lại"; onActivated: Backend.refreshLibrary() }
        Button { text: "Thử lại"; busy: Backend.libraryRefreshing; onActivated: Backend.refreshLibrary() }
        Button { text: "Lặng"; indicateRequest: false; onActivated: root.save() }
        MenuRow { text: "Xong"; onClicked: root.save() }
        MenuRow { text: "Xong"; property bool pending: root.marking; onClicked: root.save() }
        FormField { onAccepted: root.save() }
        Shortcut { onActivated: root.save() }
    }
    """
    assert sites(audit.qt_sites, tmp_path, "Q.qml", text) == [
        ("Button", True), ("Button", True), ("Button", False), ("Button", True), ("Button", False), ("MenuRow", False), ("MenuRow", True)]


def test_reviews_are_keyed_to_the_control_and_expire(tmp_path, monkeypatch, capsys):
    site = audit.Site("qt", "desktop_qt/qml/X.qml", 3, "MenuRow", "root.save()", "MenuRow { onClicked: root.save() }")
    monkeypatch.setattr(audit, "scan", lambda root: [(site, False)])
    review = tmp_path / "reviewed.json"
    monkeypatch.setattr(audit, "REVIEW", review)
    review.write_text("[]", encoding="utf-8")
    assert audit.main([]) == 1
    review.write_text(json.dumps([{"id": site.id, "path": site.path, "reason": "menu closes"}]), encoding="utf-8")
    assert audit.main([]) == 0
    review.write_text(json.dumps([{"id": site.id, "path": site.path, "reason": "menu closes"},
                                  {"id": "0" * 20, "path": "gone.qml", "reason": "old"}]), encoding="utf-8")
    assert audit.main([]) == 1
    assert "stale review" in capsys.readouterr().out


def test_every_async_control_in_the_product_shows_a_waiting_state(capsys):
    assert audit.main([]) == 0, capsys.readouterr().out
    out = capsys.readouterr().out
    counts = {platform: int(number) for number, platform in
              __import__("re").findall(r"(\d+) (web|android|qt)\b", out)}
    # The scan must keep seeing the product: a parser that silently finds nothing would pass every control.
    assert counts["web"] >= 40 and counts["android"] >= 20 and counts["qt"] >= 40, out
