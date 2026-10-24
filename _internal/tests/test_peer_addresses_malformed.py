import json
from pathlib import Path

import pytest

from abook.webui import peer_addresses as pa, remote_books as rb

ROWS = json.loads((Path(__file__).parent / "fixtures/peer_addresses_malformed.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row["name"])
def test_malformed_shared_contract(row):
    entry = row["entry"]
    pa.migrate(entry)
    assert pa.ordered(entry) == row["expected"]
    assert len(entry["addresses"]) <= 8
    assert all(isinstance(item, dict) for item in entry["addresses"])
    assert not pa.migrate(entry), "normalization must be idempotent"


@pytest.mark.parametrize("success", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_success_is_discarded(success):
    entry = {"addresses": [{"address": "10.0.0.1:47630", "lastSuccess": success}]}
    assert pa.ordered(entry) == []


def test_bad_peer_does_not_hide_good_peers_and_original_bytes_are_preserved(tmp_path):
    path = tmp_path / "computers.json"
    raw = json.dumps({"computers": {"bad": 17, "bad-port": {"host":"phone.local", "port":"invalid"},
        "good": {"name": "Good", "host":"10.0.0.1", "token":"t", "addresses":[None, {"address":"10.0.0.1:47630", "lastSuccess":4}]}}}).encode()
    path.write_bytes(raw)
    store = rb.Computers(path)
    assert [peer["id"] for peer in store.list()] == ["good"]
    assert store.get("bad") is None and store.get("bad-port") is None
    assert pa.ordered(store.get("good")) == ["10.0.0.1:47630"]
    assert store.broken and "ghép lại" in rb.broken_note(store.broken)
    assert (tmp_path / store.broken).read_bytes() == raw
    store.note("good", error="test")
    assert (tmp_path / store.broken).read_bytes() == raw
    assert [peer["id"] for peer in rb.Computers(path).list()] == ["good"]
