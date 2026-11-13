"""Independent token oracle: read native Vietnamese entries from SEAP data.

The SEAP v1/v2 binary layout is documented by sea-g2p src/core/dict.rs. This
does not call the production probe, G2P engine, or reproduce tone placement.
Tone variants are discovered from actual dictionary spellings, never synthesized.
"""
from functools import lru_cache
from pathlib import Path
import re
import struct
import unicodedata

MARKS = "\u0301\u0300\u0309\u0303\u0323"


def toneless(word):
    return unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", word) if c not in MARKS))


@lru_cache(maxsize=1)
def dictionary():
    import sea_g2p

    raw = (Path(sea_g2p.__file__).parent / "sea_g2p.bin").read_bytes()
    assert raw[:4] == b"SEAP"
    version, _, merged_n, common_n, offsets, merged, common = struct.unpack_from("<7I", raw, 4)
    assert version in {1, 2}, "Review oracle reader for new dictionary layout"
    base = 48 if version == 2 else 32

    def string(index):
        start = base + struct.unpack_from("<I", raw, offsets + 4 * index)[0]
        return raw[start:raw.index(0, start)].decode("utf8")

    native = {}
    for pos, count, width in ((merged, merged_n, 2), (common, common_n, 3)):
        for index in range(count):
            ids = struct.unpack_from("<" + "I" * width, raw, pos + index * width * 4)
            word, phone = string(ids[0]), string(ids[1])
            if "<en>" not in phone:
                native[word] = phone
    variants = {}
    for word, phone in native.items():
        if any(c in MARKS for c in unicodedata.normalize("NFD", word)):
            variants.setdefault(toneless(word), []).append((word, phone))
    return native, variants


@lru_cache(maxsize=8192)
def vietnamese_phone(word):
    word = unicodedata.normalize("NFC", word.lower())
    native, variants = dictionary()
    if toneless(word) != word:
        if word not in native:
            raise ValueError(f"No Vietnamese dictionary oracle for token {word!r}")
        return native[word]
    # A level-tone stop syllable is invalid Vietnamese: do not fabricate one
    # by stripping the tone from a checked syllable such as dát/bách.
    if word.endswith(("p", "t", "c", "ch")):
        raise ValueError(f"No level-tone Vietnamese stop syllable: {word!r}")
    # Dictionary-attested acute forms supply segmental spelling. This lookup
    # cannot inherit a bug in production's choice of tone-mark position.
    candidates = [(w, p) for w, p in variants.get(word, [])
                  if "\u0301" in unicodedata.normalize("NFD", w) and len(p.split()) == 1 and "ɜ" in p]
    native_phone = native.get(word)
    if candidates:
        options = {p.replace("ɜ", "") for _, p in candidates}
        segmental = lambda p: re.sub("[1ˈˌ]", "", p)
        if native_phone and any(segmental(native_phone) == segmental(target) for target in options):
            return native_phone
        assert len(options) == 1, f"Ambiguous dictionary tone variants for {word!r}"
        target = next(iter(options))
        return target
    if native_phone:
        return native_phone
    raise ValueError(f"No dictionary-attested Vietnamese oracle for {word!r}")
