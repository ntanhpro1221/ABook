"""List every tappable control whose action is asynchronous but shows no waiting state.

Covers web (`ui/src` JSX), Android Compose (`mobile/android/.../ui`) and Qt (`desktop_qt/qml`).
An asynchronous action is a handler that starts a network/disk request: a react-query
`mutate`, an `await`/`async` function, `api(`/`fetch(` on web; `launch {` or a `suspend`
call on Android; `Api.call`/`Api.quiet`/`Backend.*` requests on Qt. Its control is covered when
it shows the shared waiting state on the control itself:

* web: `loading=` / `pending=` / `aria-busy=` on the element, a `<PendingIndicator>` inside it,
  or a shared `Button` / `IconButton` whose handler returns the promise (usePendingAction);
* Android: a `pending`/`loading` argument, `PendingIndicator` / `ButtonLead` / `BusyRing` in the call;
* Qt: `pending:` / `loading:` / `busy:` bound on the control.

Text matching cannot prove runtime behaviour. It is a regression gate: a new control that
starts work without a waiting state fails the release until it is fixed or reviewed with a
reason in `scripts/pending_audit_reviewed.json` (keyed by file + control text, so the review
expires when the control changes).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "scripts/pending_audit_reviewed.json"
WEB = ROOT / "ui/src"
ANDROID = ROOT / "mobile/android/app/src/main/java/vn/abook/player/ui"
QT = ROOT / "desktop_qt/qml"


@dataclass
class Site:
    platform: str
    path: str
    line: int
    control: str
    handler: str
    text: str

    @property
    def id(self) -> str:
        squashed = re.sub(r"\s+", " ", self.text).strip()
        return hashlib.sha256(f"{self.path}\0{squashed}".encode()).hexdigest()[:20]

    def as_dict(self) -> dict:
        return dict(id=self.id, platform=self.platform, path=self.path, line=self.line, control=self.control,
                    handler=re.sub(r"\s+", " ", self.handler).strip()[:240])


def skip_string(text: str, i: int) -> int:
    quote = text[i]
    i += 1
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if quote == "`" and text.startswith("${", i):
            i = balanced(text, i + 1, "{", "}")
            continue
        if c == quote:
            return i + 1
        if c == "\n" and quote != "`":
            return i + 1
        i += 1
    return i


def balanced(text: str, i: int, open_: str, close: str) -> int:
    """Index after the bracket that closes text[i] (which is `open_`), skipping strings and comments."""
    depth = 0
    while i < len(text):
        c = text[i]
        if c in "\"'`":
            i = skip_string(text, i)
            continue
        if text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0:
                return len(text)
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end < 0 else end + 2
            continue
        if c == open_:
            depth += 1
        elif c == close:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return i


# ---------------------------------------------------------------- web ----

WEB_ASYNC = re.compile(r"\.mutate(?:Async)?\s*\(|\bawait\b|\basync\b|\bapi\s*(?:<[^>]*>)?\s*\(|\bfetch\s*\(")
WEB_RETURNS_PROMISE = re.compile(r"^\s*(?:async\b|\(?[^=]*\)?\s*=>\s*(?!\{)(?!void\b)[^;]*(?:\.mutateAsync\s*\(|\bapi\s*(?:<[^>]*>)?\s*\(|\bfetch\s*\()|\(?[^=]*\)?\s*=>\s*\{[^}]*\breturn\b[^;]*(?:mutateAsync|\bapi\b|\bfetch\b))")
PENDING_BUTTONS = {"Button", "IconButton", "DecisionButton", "ActionButton"}  # usePendingAction inside


def web_tag_end(text: str, i: int) -> int:
    """Index after the `>` closing the opening tag that starts at text[i] == '<'."""
    i += 1
    while i < len(text):
        c = text[i]
        if c == "{":
            i = balanced(text, i, "{", "}")
            continue
        if c in "\"'":
            i = skip_string(text, i)
            continue
        if c == ">":
            return i + 1
        i += 1
    return i


def web_attr(attrs: str, name: str) -> str | None:
    match = re.search(r"(?<![\w-])" + re.escape(name) + r"\s*=\s*\{", attrs)
    if not match:
        return None
    start = match.end() - 1
    return attrs[start + 1:balanced(attrs, start, "{", "}") - 1]


def web_async_names(text: str) -> set[str]:
    names = set(re.findall(r"\b(?:const|let)\s+(\w+)\s*=\s*async\b", text))
    names |= set(re.findall(r"\basync\s+function\s+(\w+)", text))
    # const save = () => api(...) / mutateAsync(...): returns the promise.
    names |= set(re.findall(r"\b(?:const|let)\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*(?:\w+\.mutateAsync|api\s*(?:<[^>]*>)?|fetch)\s*\(", text))
    return names


def web_void_names(text: str) -> dict[str, str]:
    """Handlers declared in the file whose body starts work but returns nothing (mutate, void promise)."""
    found = {}
    for match in re.finditer(r"\b(?:const|let)\s+(\w+)\s*=\s*(?:useCallback\(\s*)?\(([^)]*)\)\s*=>\s*", text):
        start = match.end()
        if text.startswith("{", start):
            body = text[start:balanced(text, start, "{", "}")]
        else:
            body = text[start:text.find("\n", start)]
        if re.search(r"\.mutate\s*\(|\bvoid\s+\w", body) and not re.search(r"\breturn\b", body):
            found[match.group(1)] = body
    return found


def web_sites(path: Path, rel: str) -> list[tuple[Site, bool]]:
    text = path.read_text(encoding="utf-8")
    async_names = web_async_names(text)
    void_names = web_void_names(text)
    result = []
    for match in re.finditer(r"<([A-Za-z][\w.]*)\b", text):
        tag = match.group(1)
        end = web_tag_end(text, match.start())
        attrs = text[match.end():end]
        handler = web_attr(attrs, "onClick")
        if handler is None:
            continue
        reference = re.fullmatch(r"\s*(\w+)\s*", handler)
        name = reference.group(1) if reference else None
        body = void_names.get(name, "") if name else handler
        is_async = bool(WEB_ASYNC.search(body)) or (name in async_names) or (name in void_names)
        # A confirmation (deletion.confirm({run})) runs the work from its own dialog button, which owns the waiting state.
        if not is_async or re.search(r"\.confirm\s*\(", body):
            continue
        returns_promise = (name in async_names) or bool(WEB_RETURNS_PROMISE.match(handler)) and ".mutate(" not in handler
        covered = bool(re.search(r"(?<![\w-])(?:loading|pending|aria-busy)\s*=", attrs))
        if not covered and tag in PENDING_BUTTONS and returns_promise:
            covered = True
        if not covered and not attrs.rstrip().endswith("/>"):
            close = text.find(f"</{tag}>", end)
            inner = text[end:close if close > 0 else end]
            covered = "<PendingIndicator" in inner or bool(re.search(r"<Loader2\b[^>]*animate-spin", inner))
        line = text.count("\n", 0, match.start()) + 1
        label = re.sub(r"\s+", " ", attrs)[:200]
        result.append((Site("web", rel, line, tag, handler, f"<{tag}{label}"), covered))
    return result


# ------------------------------------------------------------ android ----

AND_ASYNC = re.compile(r"\b(?:\w+\.)?launch\s*\{|\bscope\.launch\b|\brunCatching\s*\{\s*\w+\.(?:api|client)\b")
AND_COVER = re.compile(r"\b(?:pending|loading|busy)\s*=|PendingIndicator\(|ButtonLead\(|BusyRing\(|pendingVisible\(")
AND_CONTROLS = re.compile(r"\b(Button|PrimaryButton|SecondaryButton|GhostButton|OutlineButton|DangerButton|TextAction|IconAction|IconButton|"
                          r"InlineActionRow|ActionRow|MenuRow|SheetRow|DecisionButton|ChoiceChip|Chip)\s*\(")


def kotlin_call_end(text: str, i: int) -> int:
    """Given text[i] == '(', return the index after the call including a trailing lambda."""
    end = balanced(text, i, "(", ")")
    rest = re.match(r"\s*\{", text[end:end + 200])
    if rest:
        end = balanced(text, end + rest.end() - 1, "{", "}")
    return end


def android_launchers(text: str) -> re.Pattern | None:
    """Local helpers whose body launches a coroutine (`fun send(tag, work) { ... scope.launch { ... } }`): calling one starts work."""
    names = []
    # Only plain lower-case helpers: a @Composable screen that launches inside is a screen, not an action.
    for match in re.finditer(r"\bfun\s+([a-z]\w*)\s*\(", text):
        if re.search(r"@Composable\s*(?:\w+\s+)*$", text[max(0, match.start() - 80):match.start()]):
            continue
        end = balanced(text, match.end() - 1, "(", ")")
        body = re.match(r"[^{=\n]*\{", text[end:end + 200])
        if body and AND_ASYNC.search(text[end + body.end() - 1:balanced(text, end + body.end() - 1, "{", "}")]):
            names.append(match.group(1))
    return re.compile(r"\b(?:" + "|".join(map(re.escape, names)) + r")\s*\(") if names else None


def android_sites(path: Path, rel: str) -> list[tuple[Site, bool]]:
    text = path.read_text(encoding="utf-8")
    result = []
    seen = set()
    launcher = android_launchers(text)
    starts = lambda call: bool(AND_ASYNC.search(call) or (launcher and launcher.search(call)))
    # Controls: shared button composables with a click lambda.
    for match in AND_CONTROLS.finditer(text):
        if re.search(r"\bfun\s+$", text[max(0, match.start() - 8):match.start()]):
            continue
        start = match.end() - 1
        end = kotlin_call_end(text, start)
        call = text[match.start():end]
        if not starts(call):
            continue
        seen.add(match.start())
        line = text.count("\n", 0, match.start()) + 1
        result.append((Site("android", rel, line, match.group(1), call, call[:400]), bool(AND_COVER.search(call))))
    # Modifiers: pressable { ... } / clickable { ... } with an inline launch.
    for match in re.finditer(r"\.(pressable|clickable|combinedClickable)\s*(\(|\{)", text):
        start = match.end() - 1
        if match.group(2) == "(":
            end = kotlin_call_end(text, start)
        else:
            end = balanced(text, start, "{", "}")
        call = text[match.start():end]
        if not starts(call):
            continue
        # The waiting state belongs to the element this modifier sits on: look inside its content lambda.
        tail = text[end:end + 1600]
        content = re.search(r"\)\s*\{", tail)
        body = ""
        if content:
            body_start = end + content.end() - 1
            body = text[body_start:balanced(text, body_start, "{", "}")]
        line = text.count("\n", 0, match.start()) + 1
        result.append((Site("android", rel, line, match.group(1), call, call[:400]), bool(AND_COVER.search(call + body))))
    return result


# ----------------------------------------------------------------- qt ----

# Requests that go through Api.transport: Api.call / Api.quiet and the Studio store (StudioStore.request -> Api.transport.request).
QT_API = re.compile(r"\bApi\.(?:call|quiet)\s*\(|\bstore\.(?:request|quiet)\s*\(|\bApi\.transport\.request\s*\(")
QT_ASYNC = re.compile(r"\bApi\.(?:call|quiet|post|get|request)\s*\(|\bBackend\.\w+\s*\(|\bstore\.request\s*\(")
QT_COVER = re.compile(r"(?:^|[;{])\s*(?:property\s+bool\s+)?(?:pending|loading|busy)\s*:", re.M)
# Button / IconButton own an Api request their handler starts synchronously (ownedRequest -> PendingIndicator), unless told not to.
QT_OWNERS = {"Button", "IconButton", "DestructiveConfirm"}
# Not tappable controls: Enter in a text field (the form's button carries the wait), system file pickers, keyboard shortcuts.
QT_NOT_CONTROLS = {"FormField", "TextField", "TextInput", "FileDialog", "FolderDialog", "Shortcut", "Keys", "Timer"}


def qt_functions(text: str) -> dict[str, str]:
    """`function name(...) { ... }` bodies of this file, with calls to other local functions inlined once."""
    bodies = {}
    for match in re.finditer(r"\bfunction\s+(\w+)\s*\([^)]*\)\s*\{", text):
        bodies[match.group(1)] = text[match.end() - 1:balanced(text, match.end() - 1, "{", "}")]
    for name, body in list(bodies.items()):
        for other, inner in bodies.items():
            if other != name and re.search(r"(?<![\w.])(?:root\.)?" + re.escape(other) + r"\s*\(", body):
                body += "\n" + inner
        bodies[name] = body
    return bodies


def qt_sites(path: Path, rel: str) -> list[tuple[Site, bool]]:
    text = path.read_text(encoding="utf-8")
    functions = qt_functions(text)
    result = []
    for match in re.finditer(r"\bon(Activated|Clicked|Tapped|Accepted)\s*:\s*", text):
        start = match.end()
        if text.startswith("{", start):
            end = balanced(text, start, "{", "}")
        else:
            end = text.find("\n", start)
        handler = text[start:end]
        reached = handler + "".join("\n" + body for name, body in functions.items()
                                    if re.search(r"(?<![\w.])(?:root\.)?" + re.escape(name) + r"\s*\(", handler))
        if not QT_ASYNC.search(reached):
            continue
        # The control is the innermost object enclosing the handler.
        depth, i = 0, match.start()
        while i > 0:
            i -= 1
            if text[i] == "}":
                depth += 1
            elif text[i] == "{":
                if depth == 0:
                    break
                depth -= 1
        head = re.search(r"([A-Z]\w*)\s*$", text[max(0, i - 80):i])
        control = head.group(1) if head else "?"
        if control in QT_NOT_CONTROLS:
            continue
        body = text[i:balanced(text, i, "{", "}")]
        own = re.sub(r"\n\s+[A-Z]\w*\s*\{[\s\S]*?\n\s+\}", "", body)
        covered = bool(QT_COVER.search(own))
        if not covered and control in QT_OWNERS and not re.search(r"(?:^|[;{])\s*indicateRequest\s*:\s*false\b", own, re.M):
            # Only Api requests are owned; a Backend.* (C++) call has no request serial to follow.
            covered = bool(QT_API.search(reached)) and not re.search(r"\bBackend\.\w+\s*\(", reached)
        line = text.count("\n", 0, match.start()) + 1
        result.append((Site("qt", rel, line, control, handler, body[:600]), covered))
    return result


# --------------------------------------------------------------- main ----

def scan(root: Path = ROOT) -> list[tuple[Site, bool]]:
    found = []
    for base, suffixes, reader in ((WEB, (".tsx",), web_sites), (ANDROID, (".kt",), android_sites), (QT, (".qml",), qt_sites)):
        local = root / base.relative_to(ROOT)
        for path in sorted(local.rglob("*")):
            if path.suffix not in suffixes or ".test." in path.name or "gallery" in path.parts or "generated" in path.name:
                continue
            found.extend(reader(path, path.relative_to(root).as_posix()))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", type=Path, help="write every site with its coverage")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    sites = scan(args.root)
    reviews = {item["id"]: item for item in json.loads(REVIEW.read_text(encoding="utf-8"))} if REVIEW.exists() else {}
    uncovered = [site for site, covered in sites if not covered and site.id not in reviews]
    live = {site.id for site, _ in sites}
    stale = sorted(set(reviews) - live)
    if args.json:
        args.json.write_text(json.dumps([dict(site.as_dict(), covered=covered, reviewed=site.id in reviews) for site, covered in sites],
                                        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for site in uncovered:
        handler = re.sub(r"\s+", " ", site.handler).strip()[:160]
        print(f"{site.path}:{site.line}: {site.platform} {site.control} starts work without a waiting state: {handler}")
    for identity in stale:
        print(f"stale review {identity}: {reviews[identity]['path']} no longer has that control")
    counts = {p: sum(1 for s, _ in sites if s.platform == p) for p in ("web", "android", "qt")}
    print(f"Pending audit: {len(sites)} async controls ({counts['web']} web, {counts['android']} android, {counts['qt']} qt), "
          f"{sum(1 for _, c in sites if c)} covered, {sum(1 for s, c in sites if not c and s.id in reviews)} reviewed, "
          f"{len(uncovered)} missing, {len(stale)} stale")
    return int(bool(uncovered or stale))


if __name__ == "__main__":
    sys.exit(main())
