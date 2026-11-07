"""Offline replay of saved hand18 labels through validation and casting.

Private source material stays under the ignored runtime/castrules directory.
No model, network transport, audio engine, or production writer is used.
"""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys

ROOT_APP = Path(__file__).resolve().parents[1]
APP = Path(os.environ.get("CASTRULES_APP", ROOT_APP))
sys.path.insert(0, str(APP))
sys.dont_write_bytecode = True
os.environ.update(CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
WORK = Path(os.environ.get("CASTRULES_WORK", ROOT_APP / "runtime/castrules"))
DATA = Path("D:/Novels/LLM_Train/gold_mass/hand18")
AUDIT = DATA.parent / "castfix"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def ro(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def freeze():
    """Snapshot once, including gold selection and the original accepted batch boundaries."""
    WORK.mkdir(parents=True, exist_ok=True)
    manifest = []
    for incoming in sorted((DATA / "incoming").glob("*.json")):
        slug = incoming.stem
        cached = WORK / f"{slug}.input.json"
        if cached.exists():
            item = load(cached)
            # Append newly finalized chapters without changing the frozen labels
            # or source rows of any chapter already measured.
            existing = {c["stem"] for c in item["chapters"]}
            if not item["envs"]:
                for directory in sorted((DATA / "projects").glob(f"{slug}_*")):
                    stem = directory.name
                    gold_path = DATA / f"full/final/{stem}.json"
                    if stem in existing or not gold_path.exists():
                        continue
                    with ro(next(directory.rglob("project.sqlite3"))) as conn:
                        rows = [dict(r) for r in conn.execute("select * from segments order by seq")]
                    ch_id = len(item["chapters"]) + 1
                    for row in rows:
                        row["chapter_id"] = ch_id
                        row["stable_id"] = f"chapter{ch_id}:" + row["stable_id"]
                        row["id"] += ch_id * 100000
                    item["chapters"].append(dict(stem=stem,rows=rows,gold=load(gold_path),gold_path=str(gold_path)))
                save(cached,item)
            manifest.append(dict(slug=slug,chapters=len(item["chapters"]),rows=sum(len(c["rows"]) for c in item["chapters"])))
            continue
        special = AUDIT / f"{slug}.snapshot.json"
        chapters = []
        if special.exists():
            snap = load(special)
            project = Path(snap["project"])
            with ro(project / "project.sqlite3") as conn:
                envs = [load_json["segments"] for (raw,) in conn.execute(
                    "select commit_envelope_json from analysis_candidates where state='accepted'")
                    for load_json in [json.loads(raw)]]
                settings = json.loads(conn.execute("select settings_json from book").fetchone()[0])
                conn.backup(sqlite3.connect(WORK / f"{slug}.template.sqlite3"))
            stems = [x["chapter"] for x in load(project / "gold_inject.json")["alignment"]]
            for chapter, stem in zip(snap["chapters"], stems):
                rows = [r for r in snap["segments"] if r["chapter_id"] == chapter["id"]]
                gold_path = project / f"hand18_gold_replay/{stem}.json"
                chapters.append(dict(stem=stem, rows=rows, gold=load(gold_path), gold_path=str(gold_path)))
            cast = load(project / "hand18_gold_replay/cast.json")
            decisions = load(AUDIT / f"{slug}.decisions.json")
        else:
            envs, decisions = [], []
            settings = None
            cast_path = DATA / f"full/book_{slug}.json"
            if not cast_path.exists():
                continue
            cast = load(cast_path)
            for directory in sorted((DATA / "projects").glob(f"{slug}_*")):
                stem = directory.name
                gold_path = DATA / f"full/final/{stem}.json"
                if not gold_path.exists():
                    continue
                db_path = next(directory.rglob("project.sqlite3"))
                with ro(db_path) as conn:
                    rows = [dict(r) for r in conn.execute("select * from segments order by seq")]
                    if settings is None:
                        settings = json.loads(conn.execute("select settings_json from book").fetchone()[0])
                        conn.backup(sqlite3.connect(WORK / f"{slug}.template.sqlite3"))
                # Prep projects each have chapter_id=1. Give the assembled book unique ids.
                ch_id = len(chapters) + 1
                for row in rows:
                    row["chapter_id"] = ch_id
                    row["stable_id"] = f"chapter{ch_id}:" + row["stable_id"]
                    row["id"] += ch_id * 100000
                chapters.append(dict(stem=stem, rows=rows, gold=load(gold_path), gold_path=str(gold_path)))
        if not chapters:
            continue
        item = dict(slug=slug, chapters=chapters, cast=cast, settings=settings, envs=envs, decisions=decisions)
        save(WORK / f"{slug}.input.json", item)
        manifest.append(dict(slug=slug, chapters=len(chapters), rows=sum(len(c["rows"]) for c in chapters)))
    save(WORK / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False), flush=True)


def measure(label):
    from abook import analysis as A, character_registry as C
    from abook.config import build_settings
    from abook.database import ProjectDB
    from abook.quality_policy import quality_implementation_hash
    implementation_hash = quality_implementation_hash()
    input_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in WORK.glob("*.input.json")}
    # Fail immediately if an accidentally reached transport tries to connect.
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline measurement attempted network access")
    socket.create_connection = forbidden
    socket.socket.connect = forbidden
    # Registry name resolution reads every sibling TXT, not only chapter.input_path.
    # Materialize all context BEFORE either arm starts, grouped by book and deduped
    # across model runs. Never expose one book to another book's temporary sources.
    manifest = load(WORK / "manifest.json")
    source_paths = {}
    for entry in manifest:
        frozen = load(WORK / f"{entry['slug']}.input.json")
        for ch in frozen["chapters"]:
            body = "\n".join(r["text"] for r in ch["rows"])
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            source_dir = WORK / "frozen_sources" / ch.get("book", entry["slug"])
            source_dir.mkdir(parents=True, exist_ok=True)
            source_path = source_dir / f"{digest}.txt"
            if source_path.exists():
                assert source_path.read_text(encoding="utf-8") == body
            else:
                source_path.write_text(body, encoding="utf-8", newline="\n")
            source_paths[(entry["slug"], ch["rows"][0]["chapter_id"])] = source_path
    source_hashes = {str(p.relative_to(WORK)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in (WORK / "frozen_sources").rglob("*.txt")}
    summary = []
    for entry in manifest:
        if (WORK / f"stop.{label}").exists():
            raise RuntimeError("Offline audit stopped at a book boundary")
        slug = entry["slug"]
        selected = os.environ.get("CASTRULES_ONLY", "").split(",")
        if selected != [""] and slug not in selected:
            continue
        item = load(WORK / f"{slug}.input.json")
        rows = [r for ch in item["chapters"] for r in ch["rows"]]
        by_id = {r["stable_id"]: r for r in rows}
        raw_gold = {r["stable_id"]: ch["gold"][str(r["seq"])] for ch in item["chapters"] for r in ch["rows"]
                    if str(r["seq"]) in ch["gold"]}
        local_input = "raw_groups" in item
        cast = item["cast"]
        people = cast.get("cast", {}) | cast.get("npc", {})
        aliases = {a.upper(): name for name, p in cast.get("cast", {}).items() for a in p.get("aliases", [])}
        aliases.update({name.upper(): name for name in cast.get("cast", {})})
        text = "\n".join(r["text"] for r in rows)
        import re
        spelling = {}
        def spelled(name):
            if name not in spelling:
                forms = collections.Counter(m.group() for m in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.I)
                                            if m.group()[:1].isupper())
                spelling[name] = forms.most_common(1)[0][0] if forms else name.title()
            return spelling[name]
        context = A._original_neighbor_context(rows)
        groups = [[by_id[r["stable_id"]] for r in env] for env in item["envs"]] if item["envs"] else A._pack_source_cohesive_analysis_groups(rows, 5)
        traces = collections.defaultdict(list)
        funcs = ["_repair_explicit_attribution", "_repair_addressee_speakers", "_repair_same_paragraph_speakers",
                 "_repair_continued_dialogue_speakers", "_repair_in_sentence_quote_speakers"]
        originals = {name: getattr(A, name) for name in funcs}
        def wrap(name, fn):
            def inner(group, result, *args, **kwargs):
                before = copy.deepcopy(result)
                ret = fn(group, result, *args, **kwargs)
                for stable, data in result.items():
                    delta = {f: [before[stable][f], data[f]] for f in ("speaker", "kind") if before[stable][f] != data[f]}
                    if delta:
                        traces[stable].append(dict(stage=name, changes=delta))
                return ret
            return inner
        for name, fn in originals.items():
            setattr(A, name, wrap(name, fn))
        validated, rejected, mismatches = {}, [], []
        for group_index, group in enumerate(groups):
            allowed = A._allowed_kinds_by_id(group, context)
            payload = []
            for row in ([] if local_input else group):
                g = raw_gold[row["stable_id"]]
                kinds = allowed.get(row["stable_id"], sorted(A.ALLOWED_KINDS))
                kind = g["kind"] if g["kind"] in kinds else kinds[0]
                name = g["speaker"].strip()
                if kind == "narration":
                    name = "NARRATOR"
                elif name.upper().startswith("NPC"):
                    name = name[3:].strip(" :-_").capitalize() or "Người lạ"
                else:
                    name = aliases.get(name.upper(), name)
                person = people.get(name, {}) or people.get(g["speaker"], {})
                payload.append(dict(g, id=row["stable_id"], kind=kind, speaker=spelled(name) if name not in {"NARRATOR", "UNKNOWN"} else name,
                                    gender=person.get("gender", "unknown"), age=person.get("age", "unknown"), confidence=.95))
            if local_input:
                frozen_group = item["raw_groups"][group_index]
                assert frozen_group["ids"] == [r["stable_id"] for r in group]
                payload = copy.deepcopy(frozen_group["payload"])
            got = A._validate(group, {"segments": payload}, original_context=context)
            if local_input:
                A._apply_host_structural_locks(group, got)
            rejected.extend(r["stable_id"] for r in group if r["stable_id"] not in got)
            validated.update(got)
        for name, fn in originals.items():
            setattr(A, name, fn)
        for env in item["envs"]:
            for r in env:
                got = validated.get(r["stable_id"], {})
                delta = {f: [r["data"].get(f), got.get(f)] for f in ("speaker", "kind", "intensity") if r["data"].get(f) != got.get(f)}
                if delta:
                    mismatches.append(dict(stable_id=r["stable_id"], changes=delta))
        # Use the actual SQLite rewrite methods for all pre-casting repairs. Scratch DBs only.
        path = WORK / f"{slug}.{label}.sqlite3"
        # Use the same current schema in both arms. Source databases remain read-only;
        # only their immutable segment metadata and model answers are replayed.
        template = Path(os.environ.get("CASTRULES_TEMPLATE", WORK / f"{slug}.template.sqlite3"))
        with ro(template) as src, sqlite3.connect(path) as dst:
            src.backup(dst)
        db = ProjectDB(path)
        if local_input:
            db.initialize_book(title=slug, project_root=WORK, settings=item["settings"],
                               settings_hash="offline-audit", input_manifest_hash="offline-audit")
        with db.transaction() as conn:
            # Preserve full schema but replace source and analysis rows by the frozen corpus.
            conn.execute("PRAGMA defer_foreign_keys=ON")
            conn.execute("DELETE FROM analysis_candidates")
            conn.execute("DELETE FROM segments")
            conn.execute("DELETE FROM chapters")
            columns = {x[1] for x in conn.execute("pragma table_info(segments)")}
            for index, ch in enumerate(item["chapters"], 1):
                chapter_id = ch["rows"][0]["chapter_id"]
                source_path = source_paths[(slug, chapter_id)]
                conn.execute("INSERT INTO chapters(id,chapter_index,title,input_path,input_sha256,input_size,output_mp3,status) VALUES(?,?,?,?,?,?,?,?)",
                             (chapter_id,index,ch["stem"],str(source_path), "",0,"","pending"))
                for row in ch["rows"]:
                    data = {k: v for k, v in row.items() if k in columns}
                    if local_input:
                        # Never reuse a production label when validation rejects a row.
                        data.update(kind="narration", speaker="NARRATOR", gender="unknown", age="unknown",
                                    emotion="neutral", intensity=0, pace="normal", volume="normal", confidence=0)
                    data.update({k:v for k,v in validated.get(row["stable_id"], {}).items() if k in columns})
                    if row["stable_id"] in validated:
                        data["analysis_notes"] = validated[row["stable_id"]]["notes"]
                    data.update(status="analyzed",canonical_character_id=None,voice_profile_id=None,wav_path=None)
                    keys = list(data)
                    conn.execute(f"INSERT INTO segments({','.join(keys)}) VALUES({','.join('?' for _ in keys)})", [data[k] for k in keys])
        settings = item["settings"] or build_settings("high_quality")
        log = lambda msg: None
        registry_stages = ["resolve_first_person_labels", "snap_labels_to_chapter_names",
                           "_repair_cross_batch_dialogue_continuations", "_repair_crowd_dialogue_blocks",
                           "_canonicalize_named_speakers", "_repair_dialogue_turns_by_address",
                           "_repair_dialogue_turns_by_lead_in", "_merge_adjacent_local_speakers",
                           "_merge_local_speakers_with_named_identity"]
        registry_originals = {name:getattr(C,name) for name in registry_stages}
        def registry_wrap(name, fn):
            def inner(db, *args, **kwargs):
                before = {r["stable_id"]:dict(r) for r in db.list_segments()}
                ret = fn(db,*args,**kwargs)
                for row in db.list_segments():
                    stable = row["stable_id"]
                    delta = {f:[before[stable][f],row[f]] for f in ("speaker","kind") if before[stable][f] != row[f]}
                    if delta:
                        traces[stable].append(dict(stage=name,changes=delta))
                return ret
            return inner
        for name, fn in registry_originals.items():
            setattr(C,name,registry_wrap(name,fn))
        try:
            C.build_registry_and_cast(db, settings, log)
        finally:
            for name, fn in registry_originals.items():
                setattr(C,name,fn)
        db.finalize_casting()
        from abook.worker import apply_teller_voice
        # Runtime policy reads/writes only this book-specific scratch root.
        runtime_root = WORK / f"{slug}.{label}.runtime"
        runtime_root.mkdir(exist_ok=True)
        cast_rows = {r["stable_id"]: dict(r) for r in db.list_segments()}
        apply_teller_voice(runtime_root, db, settings, log)
        final = {r["stable_id"]: dict(r) for r in db.list_segments()}
        assert all(r["text"] == by_id[stable]["text"] and r["text_sha256"] == by_id[stable]["text_sha256"] for stable,r in final.items())
        for stable, row in final.items():
            delta = {f:[cast_rows[stable][f],row[f]] for f in ("speaker","kind") if cast_rows[stable][f] != row[f]}
            if delta:
                traces[stable].append(dict(stage="worker.apply_teller_voice",changes=delta))
        decisions = {d["stable_id"]: d for d in item["decisions"]}
        def canon(name):
            name = str(name).upper()
            if name.startswith("NPC "):
                name = name[4:]
            if slug == "noi-ma-hai-ta-da-goi-dien" and name == "HAJIKANO AYA":
                name = "AYA HAJIKANO"  # Explicit alias adjudication from classify.py.
            return aliases.get(name, name).upper()
        def speaker_correct(g, r):
            predicted = canon(r["speaker"])
            accepted = g.get("speakers", [g["speaker"]])
            return any(predicted == canon(name) or
                       (str(name).startswith("NPC*") and str(r["speaker"]).startswith("NPC_LOCAL"))
                       for name in accepted)
        def kind_correct(g, r):
            return r["kind"] in g.get("kinds", [g["kind"]])
        def differs(g, r):
            return not kind_correct(g, r) or not speaker_correct(g, r)
        detail = []
        for stable, r in final.items():
            if stable not in raw_gold:
                continue
            g = raw_gold[stable]
            d = decisions.get(stable)
            target = d["target"] if d else g
            # Adjudicated local aliases are equivalent only for the exact reviewed row.
            bad = differs(target, r)
            if d and d["category"] == "a" and d["subtype"] in {"alias", "local_alias"}:
                bad = bad and differs(g, r)
            detail.append(dict(stable_id=stable,chapter=r["chapter_id"],seq=r["seq"],gold=g,
                               validated=validated.get(stable),cast={k:cast_rows[stable][k] for k in ("kind","speaker")},
                               final={k:r[k] for k in ("kind","speaker")},
                               delta_gold=differs(g,r) or stable in rejected, adjudicated_bad=bad,
                               speaker_correct=speaker_correct(g,r) and stable not in rejected,
                               kind_correct=kind_correct(g,r) and stable not in rejected,
                               category=d["category"] if d else None, target=target, traces=traces.get(stable, [])))
        result = dict(slug=slug,rows=len(rows),scored=len(detail),chapters=len(item["chapters"]),
                      speaker_correct=sum(d["speaker_correct"] for d in detail),
                      kind_correct=sum(d["kind_correct"] for d in detail),
                      different_gold=sum(d["delta_gold"] for d in detail),
                      reviewed_b_wrong=sum(d["adjudicated_bad"] for d in detail if d["category"] == "b"),
                      reviewed_a_wrong=sum(d["adjudicated_bad"] for d in detail if d["category"] == "a"),
                      reviewed_a_total=sum(d["category"] == "a" for d in detail),
                      reviewed_b_total=sum(d["category"] == "b" for d in detail),
                      runtime_speaker_changes=sum(cast_rows[stable]["speaker"] != row["speaker"] for stable,row in final.items()),
                      exact_label_different_gold=sum(raw_gold[stable]["kind"] != row["kind"] or raw_gold[stable]["speaker"] != row["speaker"] for stable,row in final.items() if stable in raw_gold),
                      validation_rejected=len(rejected),accepted_reconstruction_mismatches=len(mismatches))
        save(WORK / f"{slug}.{label}.json", dict(summary=result,detail=detail,mismatches=mismatches,rejected=rejected))
        summary.append(result)
        print(json.dumps(result,ensure_ascii=False),flush=True)
    assert quality_implementation_hash() == implementation_hash, "Implementation changed during measurement"
    assert input_hashes == {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in WORK.glob("*.input.json")}
    assert source_hashes == {str(p.relative_to(WORK)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (WORK / "frozen_sources").rglob("*.txt")}
    save(WORK / f"{label}.summary.json",dict(implementation_hash=implementation_hash,input_hashes=input_hashes,
                                            source_hashes=source_hashes, books=summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    args = parser.parse_args()
    freeze() if args.label == "freeze" else measure(args.label)
