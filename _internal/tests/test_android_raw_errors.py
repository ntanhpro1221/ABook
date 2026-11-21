"""No Android screen shows a raw exception message (owner, 0.4.173: "Permission Denial ... ACTION_OPEN_DOCUMENT" on Thêm sách)."""
import json

from scripts import check_raw_errors as gate


def test_every_raw_error_read_is_routed_or_reviewed():
    assert not gate.main()


def test_review_entries_are_exact_and_explained():
    entries = gate.reviewed()
    assert all(set(x) == {"file", "line", "reason"} and len(x["reason"]) > 40 for x in entries)
    assert len({(x["file"], x["line"]) for x in entries}) == len(entries)


def test_detector_catches_new_raw_message_paths(tmp_path):
    probe = tmp_path / "Probe.kt"
    probe.write_text("\n".join([
        "fun a() { try { x() } catch (oops: Exception) { problem.value = oops.message.orEmpty() } }",
        "fun b() { runCatching { x() }.onFailure { state = it.localizedMessage } }",
        "fun c() { RowHint(result.exceptionOrNull()?.message.orEmpty()) }",
        "fun d() { try { x() } catch (error: Exception) { say(\"Lỗi: $error\") } }",
        "fun e() { try { x() } catch (failure: Throwable) { notice = failure.toString() } }",
        "fun ok() { try { x() } catch (error: Exception) { problem.value = UserText.of(error, S.s_x) } }",
        "fun log() { try { x() } catch (error: Exception) { AppLog.w(\"T\", error.message.orEmpty()) } }",
        "// error.message in a comment is not code",
    ]), encoding="utf-8")
    lines = [line for _, line in gate.findings(tmp_path)]
    assert len(lines) == 5, lines
    assert not any("UserText.of" in line or "AppLog" in line for line in lines)


def test_mapper_is_the_only_android_reader_and_says_vietnamese():
    source = (gate.SOURCES / "UserText.kt").read_text(encoding="utf-8")
    catalog = json.loads((gate.ROOT / "ui_strings/vi.json").read_text(encoding="utf-8"))["strings"]
    for key in ("s_abook_khong_con_quyen_mo_file_nay_ban_hay_b7276dfc", "s_khong_thay_file_nua_co_the_no_da_bi_xoa_371f4e4f"):
        assert f"S.{key}" in source and key in catalog
