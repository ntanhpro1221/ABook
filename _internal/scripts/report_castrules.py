"""Publish text-free measurement tables for the offline cast-rule audit."""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

APP = Path(__file__).resolve().parents[1]
WORK = APP / "runtime/castrules"
OUT = APP / "docs/castrules"
BEFORE = "before_snapshot"
AFTER = "after_final"


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def line(file, function):
    tree = ast.parse((APP / file).read_text(encoding="utf-8"))
    return next(n.lineno for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == function)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    before = load(WORK / f"{BEFORE}.summary.json")
    after = load(WORK / f"{AFTER}.summary.json")
    assert before["input_hashes"] == after["input_hashes"]
    old = {r["slug"]:r for r in before["books"]}
    records, deltas = [], []
    for now in after["books"]:
        slug = now["slug"]
        prior = old[slug]
        pre = load(WORK / f"{slug}.{BEFORE}.json")
        post = load(WORK / f"{slug}.{AFTER}.json")
        pre_rows = {r["stable_id"]:r for r in pre["detail"]}
        newly_wrong = repaired = 0
        for row in post["detail"]:
            previous = pre_rows[row["stable_id"]]
            newly_wrong += not previous["delta_gold"] and row["delta_gold"]
            repaired += previous["delta_gold"] and not row["delta_gold"]
            if previous["delta_gold"] or row["delta_gold"] or previous["final"] != row["final"] or row["adjudicated_bad"]:
                deltas.append(dict(slug=slug,stable_id=row["stable_id"],chapter=row["chapter"],seq=row["seq"],
                                   category=row["category"],gold_kind=row["gold"]["kind"],gold_speaker=row["gold"]["speaker"],
                                   before_kind=previous["final"]["kind"],before_speaker=previous["final"]["speaker"],
                                   after_kind=row["final"]["kind"],after_speaker=row["final"]["speaker"],
                                   target_kind=row["target"]["kind"],target_speaker=row["target"]["speaker"],
                                   different_gold_before=previous["delta_gold"],different_gold_after=row["delta_gold"],
                                   adjudicated_bad_before=previous["adjudicated_bad"],adjudicated_bad_after=row["adjudicated_bad"],
                                   stages_before="|".join(t["stage"] for t in previous["traces"]),
                                   stages_after="|".join(t["stage"] for t in row["traces"])))
        records.append(dict(slug=slug,rows=now["rows"],chapters=now["chapters"],
                            before=prior["different_gold"],after=now["different_gold"],newly_wrong=newly_wrong,repaired=repaired,
                            a_total=now["reviewed_a_total"],a_kept_before=prior["reviewed_a_total"]-prior["reviewed_a_wrong"],
                            a_kept_after=now["reviewed_a_total"]-now["reviewed_a_wrong"],
                            b_total=now["reviewed_b_total"],b_wrong_before=prior["reviewed_b_wrong"],b_wrong_after=now["reviewed_b_wrong"],
                            runtime_changes_before=prior["runtime_speaker_changes"],runtime_changes_after=now["runtime_speaker_changes"],
                            exact_label_before=prior["exact_label_different_gold"],exact_label_after=now["exact_label_different_gold"]))
    for filename, data in (("books.csv",records),("deltas.csv",deltas)):
        with (OUT / filename).open("w",encoding="utf-8-sig",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    suites = list(ET.parse(WORK / "pytest-verified.xml").getroot())
    pytest = {key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ("tests","failures","errors","skipped")}
    pytest["passed"] = pytest["tests"]-pytest["failures"]-pytest["errors"]-pytest["skipped"]
    pytest["failed_nodes"] = sum(case.find("failure") is not None for suite in suites for case in suite.iter("testcase"))
    log_bytes = (WORK/"pytest-verified.log").read_bytes()
    log_text = log_bytes.decode("utf-16" if log_bytes.startswith((b"\xff\xfe",b"\xfe\xff")) else "utf-8-sig")
    pytest["failed_log_lines"] = len(re.findall(r"^FAILED\b", log_text, re.M))
    assert pytest["failed_nodes"] == pytest["failures"] == pytest["failed_log_lines"]
    def content(file, function):
        source=(file).read_text(encoding="utf-8")
        return ast.dump(next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name==function),include_attributes=False)
    intensity_same = content(APP/"abook/analysis.py","_calibrated_intensity") == content(WORK/"base-source/_internal/abook/analysis.py","_calibrated_intensity")
    assert intensity_same
    summary=dict(before_hash=before["implementation_hash"],after_hash=after["implementation_hash"],
                 input_hashes=before["input_hashes"],books=records,pytest=pytest,intensity_function_unchanged=intensity_same)
    # Include every Python source, including worker/presentation helpers outside
    # QUALITY_IMPLEMENTATION_FILES, so this audit identifies the full source tree.
    for key, root in (("source_sha256_before",WORK/"base-source/_internal"),("source_sha256_after",APP)):
        summary[key]={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted((root/"abook").rglob("*.py"))}
    (OUT/"measurements.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    report=["Kết quả dev/castrules — CPU, không LLM/GPU\n",
            f"Đối chiếu cùng đầu vào đóng băng: **{len(records)} sách, {sum(r['chapters'] for r in records)} chương, {sum(r['rows'] for r in records):,} câu**. "
            "Nguồn hand18 đang cập nhật; snapshot cuối bao phủ mọi sách có full/final gold lúc chốt. Tôi muốn trở thành nước mắt của cậu có 5/11 chương; "
            "3 sách chưa có gold: Gửi đến em người ở nơi xa hơn bao giờ hết; Mùa thu hổ phách và chuyến hành trình 0 giây; Tớ sẽ đợi tại mùa xuân hôm qua. "
            "Gold là nhãn model đã lưu, không phải toàn bộ đã được người thật gán nhãn.\n",
            "| Sách | Câu | Khác gold trước → sau | a giữ đúng trước → sau | b còn sai trước → sau |",
            "|---|---:|---:|---:|---:|"]
    for r in records:
        a=f"{r['a_kept_before']} → {r['a_kept_after']} / {r['a_total']}" if r['a_total'] else "—"
        b=f"{r['b_wrong_before']} → {r['b_wrong_after']} / {r['b_total']}" if r['b_total'] else "—"
        report.append(f"| {r['slug']} | {r['rows']} | {r['before']} → {r['after']} | {a} | {b} |")
    report += ["",f"Tổng khác gold: **{sum(r['before'] for r in records)} → {sum(r['after'] for r in records)}**; "
               f"**{sum(r['after']>r['before'] for r in records)} sách tăng**. So sánh kind/speaker sau chuẩn hóa hoa/thường, alias trong cast và tiền tố transport `NPC`; "
               "số khác nhãn chữ tuyệt đối có trong books.csv. Alias đảo tên Aya dùng phán quyết castfix. a/b dùng phán quyết từng stable_id từ classify.py; a gồm cả policy intensity và alias. "
               "Nơi mà có 141 hàng b gốc, nhưng baseline cây này đã đúng hàng 004:440; do đó tái hiện 140 lỗi b.\n",
               "Phép đo: schema projection của Replayer từ gold → `_validate` → `build_registry_and_cast` → `worker.apply_teller_voice`. "
               "Batch accepted của hai sách castfix tái dựng **0 sai khác kind/speaker/intensity** trước sửa; các sách khác dùng batch nguồn cohesive cap 5. "
               "AYNIK có **29 → 0** lần worker đổi speaker nội tâm; 29 lỗi runtime đã nằm trong tổng b=52. "
               "Baseline lấy từ Git HEAD 5678fddf7 vào thư mục runtime riêng, không chuyển nhánh. Mọi thao tác SQLite đều trên bản sao; "
               "socket ngoài bị chặn trong harness. Text và text_sha256 của toàn bộ segment được assert giữ nguyên.\n",
               "Thay đổi theo loại:", ""]
    changes=[("Kind/ngoặc", "abook/analysis.py", "_source_kind_transition_rule", "hint không khóa schema/validation/critic; DB bỏ khóa kind chỉ từ ngoặc"),
             ("Độ sâu ngoặc", "abook/text_processing.py", "_scan_quote_closing", "giữ stack qua nhiều dòng/paragraph; không bỏ chữ"),
             ("Chủ thể lời dẫn", "abook/analysis.py", "_explicit_speaker_attribution", "chỉ động từ phát ngôn thật, chặn ý định/phản ứng/bổ ngữ; cue yếu không đè nhãn chắc"),
             ("Generic/quan hệ", "abook/analysis.py", "_generic_speaker_attribution", "giữ cụm vai, lấy giới theo head; cue app theo mention, không làm neo lan cả đoạn"),
             ("Trích giữa câu", "abook/analysis.py", "_is_quoted_inside_a_sentence", "speech tag thắng heuristic, cần bằng chứng thuật ngữ dương tính; đọc context ngoài mép batch"),
             ("Gọi tên/ABAB", "abook/first_person.py", "is_name_answer", "tên trả lời/tự giới thiệu/trích lồng không làm neo; registry bỏ lan ABAB, cho cùng người nhiều lượt"),
             ("Name-snap", "abook/name_snap.py", "is_name_label", "chặn vai/quan hệ; registry giữ role và chặn gộp trái giới"),
             ("Teller runtime", "abook/teller_voice.py", "ensure", "mặc định giữ identity và giọng nội tâm; opt-in chỉ đổi voice_profile lời dẫn, undo/retarget atomic"),
             ("Worker/UI", "abook/worker.py", "apply_teller_voice", "worker dùng cùng policy; bỏ thẻ đề nghị đổi speaker nội tâm; UI đọc provenance SQLite")]
    additional = {
        "Kind/ngoặc": [("abook/database.py","_analysis_host_lock_contract")],
        "Generic/quan hệ": [("abook/character_registry.py","_merge_adjacent_local_speakers")],
        "Gọi tên/ABAB": [("abook/character_registry.py","_repair_dialogue_turns_by_address"),
                        ("abook/character_registry.py","_repair_dialogue_turns_by_lead_in")],
        "Name-snap": [("abook/character_registry.py","canonical_speaker_names"),
                      ("abook/character_registry.py","_canonicalize_named_speakers")],
        "Worker/UI": [("abook/webui/work_items.py","_teller_cards"),("abook/webui/teller_mode.py","view")],
    }
    for title,file,function,description in changes:
        refs=", ".join(f"`{path}:{line(path,fn)}`" for path,fn in [(file,function),*additional.get(title,[])])
        report.append(f"- {title}: {refs} — {description}.")
    report += ["- `_calibrated_intensity` giữ nguyên AST so với HEAD, có kiểm tra tự động trong report generator.\n",
               "Test hồi quy dùng câu tiếng Việt tự viết trong các file test module hiện có: kind qua hint + crash/reopen DB thật; "
               "ngoặc lồng nhiều paragraph và bảo toàn chữ; lời dẫn/phản ứng/ý định; quan hệ/head gender/mention; speech tag ngắn ở mép batch; "
               "tên trả lời/tự giới thiệu/trích lồng và nhiều lượt cùng người; role/gender chống snap; worker không đổi identity; "
               "voice opt-in, undo, rollback và crash sau commit trước sidecar. Các test buộc hành vi cũ được cập nhật theo chính sách mới.\n",
               "Các test chính:", "",
               f"- Kind/DB reopen, lời dẫn, generic, mép batch: `tests/test_analysis_required.py:{line('tests/test_analysis_required.py','test_semantic_kind_crosses_hint_and_commits_after_an_accepted_candidate_reopen')}`.",
               f"- Parser/giữ chữ: `tests/test_text_processing_safety.py:{line('tests/test_text_processing_safety.py','test_nested_and_unclosed_quotes_keep_every_source_token')}`.",
               f"- Gọi tên/ABAB: `tests/test_nobody_calls_their_own_name.py:{line('tests/test_nobody_calls_their_own_name.py','test_name_answers_and_introductions_are_not_vocative_anchors')}`.",
               f"- Role/gender: `tests/test_name_snap.py:{line('tests/test_name_snap.py','test_kinship_and_role_labels_never_fuzzy_snap_to_bare_names')}`.",
               f"- Worker/thought: `tests/test_teller_voice.py:{line('tests/test_teller_voice.py','test_default_worker_does_not_claim_listener_speaker_changes')}`.",
               f"- Voice transaction/undo: `tests/test_chapter_teller_voice.py:{line('tests/test_chapter_teller_voice.py','test_committed_voice_change_is_undoable_after_a_sidecar_failure')}`; route: `tests/test_teller_mode_route.py:{line('tests/test_teller_mode_route.py','test_explicit_mode_changes_voice_only_and_the_route_restores_it')}`.\n",
               f"Pytest: **{pytest['passed']} passed, {pytest['failures']} failed, {pytest['errors']} errors, {pytest['skipped']} skipped**, "
               "92 file liên quan, chạy `-rf`, đếm từ JUnit và kiểm danh sách FAILED trong log. Baseline trước sửa: 1.304 passed, 0 failed (58 file ban đầu); "
               "không có failure sẵn được dùng để miễn trừ. 3 skip là test giọng ZeroTTS/Supertonic chưa cài; không tải hoặc gọi model.\n",
               "Đánh đổi còn lại: a giữ đúng giảm 5 ở Nơi mà, 2 ở AYNIK: bỏ ép kind để model quyết cũng bỏ các sửa đúng khi gold/model sai. "
               "b còn lại gồm cả những hàng gold đã sai theo phán quyết castfix; không tự chèn đáp án từng câu vào production. "
               "`books.csv` tách số câu mới hỏng và số cứu lại, tránh che hồi quy cục bộ bằng tổng ròng. "
               "Starting Over có 2 câu mới khác gold ở chuẩn hóa họ/tên, chưa được phân xử để khẳng định cùng người. "
               "Không đo lại LLM với prompt mới và không thu/nghe audio trong lượt CPU này.\n",
               "Tái lập: dùng đúng interpreter được chỉ định với `-X utf8 -B _internal/scripts/measure_castrules.py freeze`; "
               "`CASTRULES_APP` trỏ bản source HEAD cho `before_snapshot`, bỏ biến ấy cho `after_final`; cuối cùng chạy `report_castrules.py`. "
               "Freeze chỉ bổ sung chương mới, giữ nhãn chương đã chốt; bổ sung thì phải đo lại cả hai vế. JSON từng câu/stage, hash input, bản sao SQLite và JUnit/log nằm ở "
               "`_internal/runtime/castrules/` (gitignored); CSV/JSON công khai ở cùng thư mục báo cáo chỉ chứa nhãn/số đo, không có câu truyện.\n",
               f"Hash chất lượng: `{before['implementation_hash']}` → `{after['implementation_hash']}`. "
               "Chỉ sửa cây dev/castrules; không commit/push/chuyển nhánh/stash/reset, không dừng tiến trình hay gọi model.\n"]
    (OUT/"result.md").write_text("\n".join(report),encoding="utf-8",newline="\n")
    print(json.dumps(dict(books=len(records),rows=sum(r['rows'] for r in records),pytest=pytest),ensure_ascii=False))


if __name__=="__main__":
    main()
