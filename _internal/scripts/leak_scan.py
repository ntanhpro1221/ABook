"""Find private material in the tracked files of this repository before it goes public.

Three checks, each printed as ``path:line: kind: excerpt``:

(a) ``corpus``  - a run of 7 words that also appears verbatim in the private book corpus. Escapes such as
    ``\\u1ea1`` are decoded first, and a line typed without diacritics is compared with the corpus folded
    to bare letters. The corpus is looked up at ``$ABOOK_CORPUS`` or ``<main checkout>/Corpus``; when it
    is absent the check is skipped and says so, it never passes silently.
(b) ``ipa``     - a line with 8 or more IPA-bearing tokens (phonemised prose is still the prose).
(c) ``machine`` - this machine's own name (read from the environment at run time, never written here),
    its own addresses, and any tailnet (100.64.0.0/10) or home-LAN (192.168.0.0/16) address that is not
    one of the documentation samples below.

Exit status is 1 when anything is found. ``--rev REV`` scans a commit instead of the work tree,
which is what the pre-push hook uses.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import ipaddress
import io
import os
import re
import socket
import subprocess
import unicodedata
import sys
from pathlib import Path

SHINGLE = 7
# Book folders in the corpus that hold no book text of their own.
CORPUS_SKIP = {"claude", "_full", "_dup", "_survey", "_gold", "keys", "releases", "research", "g2pgate", "S"}
VN_MARKS = set("ăâđêôơưàảãáạằẳẵắặầẩẫấậèẻẽéẹềểễếệìỉĩíịòỏõóọồổỗốộờởỡớợùủũúụừửữứựỳỷỹýỵ")
WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
BINARY_SUFFIXES = (
    ".wav", ".mp3", ".flac", ".ogg", ".m4a", ".opus", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".ttf",
    ".otf", ".woff", ".woff2", ".jar", ".zip", ".gz", ".exe", ".dll", ".so", ".onnx", ".bin", ".pdf", ".db",
    ".npz", ".pyc", ".keystore", ".jks",
)

IPA_MARKS = set(
    "ɐɑɒæɓʙβɔɕçɗɖðʤəɘɚɛɜɝɞɟʄɡɠɢʛɦɧħɥʜɨɪʝɭɬɫɮʟɱɯɰŋɳɲɴøɵɸθœɶʘɹɺɾɻʀʁɽʂʃʈʧʉʊʋⱱʌɣɤʍχʎʏʑʐʒʔʡʕʢˈˌːˑ"
)
IPA_MIN_TOKENS = 8
# Exact files whose IPA lines phonemise short sentences written for the tests (reviewed by hand 2026-11-12/13: the
# sentences beside the phonemes were checked against the corpus and carry no book text). Their IPA findings are
# counted as reviewed; the text in them is still covered by the corpus check. Any other file with long IPA lines,
# or a new fixture, fails until it is reviewed and named here.
IPA_REVIEWED_FILES = frozenset({
    "_internal/tests/fixtures/vieneu/android/text.json",
    "_internal/tests/fixtures/vieneu/android/tokens.json",
    "_internal/tests/fixtures/vieneu/android/clips.json",
    "_internal/tests/fixtures/readaloud/shared_vietnamese/cases.json",
    "_internal/tests/fixtures/readaloud/real_names/cases.json",
    "_internal/tests/fixtures/readaloud/japanese_delivery/cases.json",
    "_internal/tests/fixtures/readaloud/english_direct/frontend.json",
    "_internal/tests/fixtures/readaloud/phoneme_delivery/cases.json",
    "_internal/tests/test_readaloud_vieneu.py",
    "_internal/tests/test_readaloud_phoneme_policy.py",
    "_internal/tests/test_real_names.py",
    "_internal/mobile/android/app/src/test/java/vn/abook/player/vieneu/RealNamesTest.kt",
})
ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})|\\x([0-9a-fA-F]{2})")


def unescape(line: str) -> str:
    """Prose written as ``\\u1ea1`` / ``\\xe0`` escapes is still prose: decode before matching."""
    if "\\u" not in line and "\\U" not in line and "\\x" not in line:
        return line
    return ESCAPE.sub(lambda m: chr(int(m.group(1) or m.group(2) or m.group(3), 16)), line)


IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?:/(\d{1,2}))?(?![\d.])")
TAILNET = ipaddress.ip_network("100.64.0.0/10")
HOME_LAN = ipaddress.ip_network("192.168.0.0/16")
# Made-up addresses the tests and docs already use. Anything else in these ranges looks real: new examples
# should use the documentation ranges 192.0.2.0/24, 198.51.100.0/24 or 203.0.113.0/24 instead.
SAMPLE_ADDRESSES = {
    "100.64.0.0", "100.64.0.1", "100.64.0.7", "100.64.1.2", "100.64.19.7", "100.73.1.2", "100.101.2.3",
    "100.101.102.103", "100.127.255.1", "100.127.255.254",
    "192.168.0.5", "192.168.0.9", "192.168.1.1", "192.168.1.2", "192.168.1.3", "192.168.1.4", "192.168.1.5",
    "192.168.1.8", "192.168.1.9", "192.168.1.20", "192.168.1.21", "192.168.1.22", "192.168.1.30", "192.168.1.40",
    "192.168.1.55", "192.168.1.60", "192.168.1.77", "192.168.1.99", "192.168.1.255", "192.168.7.8", "192.168.19.7",
    "192.168.123.9",
}


def repo_root() -> Path:
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
    return Path(out.stdout.strip())


def default_corpus(root: Path) -> Path | None:
    env = os.environ.get("ABOOK_CORPUS")
    if env:
        return Path(env)
    common = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True, text=True,
    ).stdout.strip()
    candidates = [root / "Corpus"]
    if common:
        candidates.append(Path(common).parent / "Corpus")
    for c in candidates:
        if c.is_dir():
            return c
    return None


def tracked_files(root: Path, rev: str | None) -> list[tuple[str, str]]:
    """(path, text) for every tracked text file, from the work tree or from ``rev``."""
    if rev is None:
        names = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True).stdout
        paths = [p for p in names.decode("utf-8").split("\0") if p]
    else:
        names = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "-r", "-z", "--name-only", rev], capture_output=True, check=True
        ).stdout
        paths = [p for p in names.decode("utf-8").split("\0") if p]
    paths = [p for p in paths if not p.lower().endswith(BINARY_SUFFIXES)]
    batch = None
    if rev is not None:
        result = subprocess.run(
            ["git", "-C", str(root), "cat-file", "--batch"],
            input="".join(f"{rev}:{p}\n" for p in paths).encode("utf-8"),
            capture_output=True, check=True,
        )
        batch = io.BytesIO(result.stdout)
    out = []
    for p in paths:
        if p.lower().endswith(BINARY_SUFFIXES):
            continue
        if rev is None:
            fp = root / p
            if not fp.is_file():
                continue
            data = fp.read_bytes()
        else:
            header = batch.readline().split()
            if len(header) != 3 or header[1] != b"blob":
                raise RuntimeError(f"Cannot read committed blob: {p}")
            data = batch.read(int(header[2]))
            if batch.read(1) != b"\n":
                raise RuntimeError(f"Invalid blob boundary: {p}")
        if b"\x00" in data[:8000]:
            continue
        out.append((p, data.decode("utf-8", errors="replace")))
    return out


def _shingles(words: list[str]):
    for i in range(len(words) - SHINGLE + 1):
        yield " ".join(words[i:i + SHINGLE])


def _story_like(line_lower: str) -> bool:
    return sum(1 for c in line_lower if c in VN_MARKS) >= 4


def _fold_table() -> dict[int, str]:
    table = {ord("đ"): "d"}
    for ch in VN_MARKS:
        base = unicodedata.normalize("NFD", ch)[0]
        table[ord(ch)] = "d" if ch == "đ" else base
    return table


# Precomposed Vietnamese letters -> bare letter. A table, not unicodedata.normalize on a whole book (superlinear).
FOLD = _fold_table()


def scan_corpus(files: list[tuple[str, str]], corpus: Path) -> list[tuple[str, int, str, str]]:
    """7-word runs shared with the corpus. A line with Vietnamese marks is matched as written (the audit's rule);
    a line without them is matched with the corpus folded to bare letters, so a copy typed without diacritics
    ("toi bat dau thu...") is still a copy."""
    wanted: dict[str, list[tuple[str, int, str]]] = {}
    wanted_bare: dict[str, list[tuple[str, int, str]]] = {}
    for path, text in files:
        for no, line in enumerate(text.splitlines(), 1):
            low = unescape(line).lower()
            if _story_like(low):
                for sh in _shingles(WORD.findall(low)):
                    wanted.setdefault(sh, []).append((path, no, line))
            else:
                words = WORD.findall(low.translate(FOLD))
                if len(words) >= SHINGLE:
                    for sh in _shingles(words):
                        wanted_bare.setdefault(sh, []).append((path, no, line))
    if not wanted and not wanted_bare:
        return []
    hit: set[str] = set()
    hit_bare: set[str] = set()
    for top in sorted(os.listdir(corpus)):
        if top in CORPUS_SKIP or not (corpus / top).is_dir():
            continue
        for base, _dirs, names in os.walk(corpus / top):
            for name in names:
                if not name.endswith((".txt", ".md")):
                    continue
                try:
                    text = open(os.path.join(base, name), encoding="utf-8", errors="replace").read().lower()
                except OSError:
                    continue
                for sh in _shingles(WORD.findall(text)):
                    if sh in wanted:
                        hit.add(sh)
                if wanted_bare:
                    for sh in _shingles(WORD.findall(text.translate(FOLD))):
                        if sh in wanted_bare:
                            hit_bare.add(sh)
    found: dict[tuple[str, int], str] = {}
    for sh in hit:
        for path, no, line in wanted[sh]:
            found.setdefault((path, no), line)
    for sh in hit_bare:
        for path, no, line in wanted_bare[sh]:
            found.setdefault((path, no), line)
    return [(p, n, "corpus", unescape(line).strip()[:140]) for (p, n), line in sorted(found.items())]


def scan_ipa(files: list[tuple[str, str]]) -> list[tuple[str, int, str, str]]:
    out = []
    for path, text in files:
        for no, line in enumerate(text.splitlines(), 1):
            if not any(c in IPA_MARKS for c in line):
                continue
            tokens = [t for t in re.split(r"[\s,\"'\[\]|/]+", line) if any(c in IPA_MARKS for c in t)]
            if len(tokens) >= IPA_MIN_TOKENS:
                out.append((path, no, "ipa", line.strip()[:140]))
    return out


ALLOWLIST_PATH = "_internal/scripts/leak_scan_allowlist.json"


def apply_reviews(files, findings):
    """Only identical, individually reviewed lines may be suppressed."""
    texts = dict(files)
    data = json.loads(texts.get(ALLOWLIST_PATH, '{"entries": []}'))
    approved = set()
    for path, no, kind, excerpt in findings:
        if kind == "ipa" and path in IPA_REVIEWED_FILES:
            line = texts[path].splitlines()[no - 1]
            approved.add((kind, path, hashlib.sha256(line.strip().encode("utf-8")).hexdigest()))
    for entry in data["entries"]:
        if not entry.get("reason", "").strip() or entry["kind"] not in {"corpus", "ipa"}:
            raise ValueError("leak_scan: invalid review entry")
        approved.add((entry["kind"], entry["path"], entry["sha256"]))
    pending, reviewed = [], []
    for finding in findings:
        path, no, kind, excerpt = finding
        line = texts[path].splitlines()[no - 1]
        digest = hashlib.sha256(line.strip().encode("utf-8")).hexdigest()
        (reviewed if (kind, path, digest) in approved else pending).append(finding)
    return pending, reviewed


def own_identity() -> tuple[list[str], set[str]]:
    names = []
    for raw in (os.environ.get("COMPUTERNAME"), os.environ.get("HOSTNAME"), socket.gethostname()):
        if raw and raw.lower() not in {"localhost"} and raw.lower() not in (n.lower() for n in names):
            names.append(raw)
    addresses: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(info[4][0])
    except OSError:
        pass
    addresses -= {"127.0.0.1"}
    return names, addresses


def scan_machine(files: list[tuple[str, str]]) -> list[tuple[str, int, str, str]]:
    names, own_addresses = own_identity()
    name_res = [re.compile(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", re.IGNORECASE) for n in names]
    out = []
    for path, text in files:
        for no, line in enumerate(text.splitlines(), 1):
            for rx in name_res:
                if rx.search(line):
                    out.append((path, no, "machine", "this machine's name"))
            for m in IPV4.finditer(line):
                value = m.group(1)
                try:
                    addr = ipaddress.ip_address(value)
                    if m.group(2) is not None:
                        # A network in CIDR notation ("192.168.0.0/16") names a range, not a machine;
                        # an interface address with its mask ("192.0.2.30/24") is still that address.
                        ipaddress.ip_network(f"{value}/{m.group(2)}", strict=True)
                        continue
                except ValueError:
                    if m.group(2) is None:
                        continue
                if value in own_addresses:
                    out.append((path, no, "machine", f"this machine's address {value}"))
                elif (addr in TAILNET or addr in HOME_LAN) and value not in SAMPLE_ADDRESSES:
                    out.append((path, no, "machine", f"non-sample private address {value}"))
    return out


PENDING_AUDIO_PATH = "_internal/scripts/leak_scan_pending_audio.json"


def pending_audio(root: Path, files, rev: str | None) -> list[str]:
    """Listed audio whose git blob is still the recorded one: it still speaks book text and waits for regeneration.

    Audio is not transcribed here; the list is written by hand when a recording is known to read book text, and an
    entry stops counting as soon as the file's bytes change (or the file is gone)."""
    data = json.loads(dict(files).get(PENDING_AUDIO_PATH, '{"entries": []}'))
    entries = {e["path"]: e["blob"] for e in data["entries"]}
    if not entries:
        return []
    if rev is None:
        present = [p for p in entries if (root / p).is_file()]
        out = subprocess.run(["git", "-C", str(root), "hash-object", "--", *present],
                             capture_output=True, text=True, check=True).stdout.split() if present else []
        current = dict(zip(present, out))
    else:
        listing = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", rev, "--", *entries],
                                 capture_output=True, text=True, check=True).stdout
        current = {line.split("\t", 1)[1]: line.split()[2] for line in listing.splitlines()}
    return sorted(p for p, blob in entries.items() if current.get(p) == blob)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rev", help="scan this commit instead of the work tree")
    ap.add_argument("--corpus", help="private corpus folder (default: $ABOOK_CORPUS or <main checkout>/Corpus)")
    ap.add_argument("--skip-corpus", action="store_true", help="only run the fast checks")
    ap.add_argument("--raw", action="store_true", help="also report exact reviewed false positives")
    ap.add_argument("--json", type=Path, help="write the findings without prose excerpts")
    ap.add_argument("--strict-audio", action="store_true",
                    help="also fail while listed audio still waits for regeneration")
    args = ap.parse_args(argv)
    root = repo_root()
    files = tracked_files(root, args.rev)
    findings = scan_ipa(files) + scan_machine(files)
    if args.skip_corpus:
        print("leak_scan: corpus check SKIPPED (--skip-corpus)", file=sys.stderr)
    else:
        corpus = Path(args.corpus) if args.corpus else default_corpus(root)
        if corpus is None or not corpus.is_dir():
            print("leak_scan: corpus check SKIPPED - no private corpus found (set ABOOK_CORPUS)", file=sys.stderr)
        else:
            findings += scan_corpus(files, corpus)
    raw_findings = sorted(set(findings))
    pending, reviewed = apply_reviews(files, raw_findings)
    findings = raw_findings if args.raw else pending
    if args.json:
        args.json.write_text(json.dumps({
            "files": len(files), "raw_count": len(raw_findings), "reviewed_count": len(reviewed),
            "findings": [{"path": p, "line": n, "kind": k} for p, n, k, _ in findings],
        }, indent=2) + "\n", encoding="utf-8")
    for path, no, kind, excerpt in findings:
        print(f"{path}:{no}: {kind}: {excerpt}")
    waiting = pending_audio(root, files, args.rev)
    if waiting:
        print(f"leak_scan: PENDING AUDIO - {len(waiting)} recording(s) still speak book text and must be "
              f"regenerated ({PENDING_AUDIO_PATH}):", file=sys.stderr)
        for path in waiting:
            print(f"  {path}", file=sys.stderr)
    print(f"leak_scan: {len(findings)} finding(s) in {len(files)} file(s); "
          f"{len(reviewed)} exact reviewed false positive(s)", file=sys.stderr)
    return 1 if findings or (args.strict_audio and waiting) else 0


if __name__ == "__main__":
    sys.exit(main())
