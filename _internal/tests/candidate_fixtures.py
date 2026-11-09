"""Current-schema candidate scenarios, built through the durable public API."""
from __future__ import annotations

import json
from pathlib import Path

from abook.config import build_settings, save_settings
from abook.database import PRONUNCIATION_DELIVERY_SOURCE, ProjectDB
from abook.io_utils import sha256_text
from abook.quality_policy import QUALITY_POLICY_VERSION, quality_policy_hash
from tests.test_database_safety import (
    _candidate_db,
    _candidate_decode_check,
    _checkpoint_candidate_signal,
    _locked_name_dual_failed_candidate,
    _write_candidate_artifact,
)

POLICY = "candidate-policy-v1"


def _seal(db: ProjectDB) -> ProjectDB:
    """Give the constructed scenario a valid policy identity for pipeline hooks."""
    policy = json.loads(str(db.current_quality_policy()["policy_json"]))
    digest = quality_policy_hash(policy)
    with db.transaction() as conn:
        conn.execute("PRAGMA defer_foreign_keys=ON")
        conn.execute("UPDATE quality_policies SET policy_hash=?,policy_version=?", (digest,QUALITY_POLICY_VERSION))
        conn.execute("UPDATE quality_checks SET policy_hash=?,policy_version=?", (digest,QUALITY_POLICY_VERSION))
        conn.execute("UPDATE segment_candidates SET policy_hash=?", (digest,))
        conn.execute("UPDATE segments SET generation_policy_hash=?", (digest,))
    return db


def _start(root: Path, suffix: str, text: str) -> tuple[ProjectDB, int, str]:
    db, segment_id, incumbent, _ = _candidate_db(root, source_text=text)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET stable_id=?,generation_policy_hash=? WHERE id=?",
                     ("fixture_"+suffix, POLICY, segment_id))
    save_settings(root / "book_settings.json", build_settings())
    return db, segment_id, incumbent


def _candidate(db: ProjectDB, root: Path, segment_id: int, incumbent: str, *, round: int,
               passed: bool, source: bool = False):
    path = root / "candidates" / f"round-{round}.wav"
    digest = _write_candidate_artifact(path, str(round))
    options = {}
    if source:
        options = {"pronunciation_delivery_variant": PRONUNCIATION_DELIVERY_SOURCE,
                   "expected_spoken_text_sha256": sha256_text(str(db.get_segment(segment_id)["text"]))}
    candidate = db.allocate_segment_candidate(segment_id=segment_id, policy_hash=POLICY, repair_round=round,
        max_repair_rounds=2, incumbent_sha256=incumbent, generation_seed=101+round,
        wav_path=path, candidates_root=path.parent, **options)
    _checkpoint_candidate_signal(db, int(candidate["id"]), repair_round=round, generation_seed=101+round,
                                 wav_path=path, wav_sha256=digest, signal_overrides={"generation_ceiling_hit": 0})
    for confirmation in (False, True):
        check = _candidate_decode_check(db, segment_id=segment_id, artifact_sha256=digest, repair_round=round,
            generation_seed=101+round, confirmation=confirmation, verdict="pass" if passed else "fail",
            reason="ok" if passed else "ASR_UNVERIFIABLE_SHORT_TEXT",
            failure_codes=() if passed else ("ASR_UNVERIFIABLE_SHORT_TEXT",))
        db.checkpoint_segment_candidate_decode(int(candidate["id"]), quality_check_id=check, confirmation=confirmation)
    return db.get_segment_candidate(int(candidate["id"]))


def locked_reading(root: Path) -> ProjectDB:
    db, segment_id, incumbent = _start(root, "feeb9dd9dda2", "Đây là một câu thử có tên.")
    _locked_name_dual_failed_candidate(db, segment_id=segment_id, incumbent_sha256=incumbent,
        candidate_path=root/"candidates"/"locked.wav", generation_seed=100)
    spelling = _candidate(db, root, segment_id, incumbent, round=1, passed=True, source=True)
    db.promote_segment_candidate(int(spelling["id"]), validated_wav_sha256=str(spelling["wav_sha256"]),
        repair_action="promote_dual_decode_clarity_candidate", attempt=1, warning_code=None)
    return _seal(db)


def finished_take(root: Path) -> ProjectDB:
    db, segment_id, incumbent = _start(root, "5b7f60a11624", "Thử!")
    with db.transaction() as conn:
        row = conn.execute("SELECT signal_json FROM segments WHERE id=?", (segment_id,)).fetchone()
        signal = json.loads(row[0]); signal["generation_ceiling_hit"] = 1
        conn.execute("UPDATE segments SET signal_json=? WHERE id=?", (json.dumps(signal),segment_id))
    _candidate(db, root, segment_id, incumbent, round=0, passed=False)
    return _seal(db)
