import json
from pathlib import Path

from abook.webui.music_art import descriptor, seed
from abook.webui.music_library import detail, row

FIXTURE = Path(__file__).parent / "fixtures/music_art/cases.json"


def test_shared_seed_contract_and_list_detail_identity():
    for case in json.loads(FIXTURE.read_text(encoding="utf-8")):
        link, info = case["link"], case["info"]
        assert seed(link, info) == case["seed"]
        assert row(link, info)["artSeed"] == detail(link, info, [])["artSeed"] == case["seed"]


def test_real_art_provenance_survives_both_api_shapes():
    art = {"url": "https://music.example/art/cover.jpg", "sha1": "a"*40, "w": 512, "h": 512,
           "source": "https://source.example/album.jpg", "credit": "Artwork by Example", "landing": "https://source.example/album"}
    for result in (row("track", {"art": art}), detail("track", {"art": art}, [])):
        assert result["art"] == art
    assert "art" not in descriptor("track", {"art": {**art, "sha1": "../../bad"}})
    assert "art" not in descriptor("track", {"art": {**art, "url": "file:///private"}})


def test_palette_and_motif_follow_mood_and_energy():
    assert seed("same", {"emotions": {"fear": 1}}) % 5 == 3
    assert seed("same", {"emotions": {"joy": 1}}) % 5 == 2
    assert seed("same", {"emotions": {"nostalgia": 1}}) % 5 == 1
    assert seed("same", {"style": "ambient"}) % 5 == 0
    assert seed("same", {"arousal": -1}) // 5 % 5 < seed("same", {"arousal": 1}) // 5 % 5
