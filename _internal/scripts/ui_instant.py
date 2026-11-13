"""L7 structural classifier: every show/hide site on the three platforms, sorted into
"a" (a hard toggle the user can see) and "b" (proved safe by a general rule).

No path/line exceptions and no nearby-animation windows: a rule looks at the object
that owns the binding (Qt), the render that owns the expression (web), or the call
target (Android). Unproved candidates stay "a" and count against the ratchet.
An animation on an unrelated sibling, or a parent opening for a different reason,
never proves a child safe.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def mask(source: str) -> str:
    """Hide comments and strings, preserving every offset and newline."""
    return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`(?:\\.|[^`\\])*`',
                  lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), source)


def qml_objects(source: str) -> list[dict]:
    clean = mask(source)
    objects, stack = [], []
    for match in re.finditer(r'[{}]', clean):
        pos = match.start()
        if match[0] == '{':
            head = re.search(r'(?:\b([A-Z]\w*(?:\.[A-Z]\w*)*)|\b(Behavior)\s+on\s+(\w+))\s*$', clean[:pos])
            obj = dict(type=(head[1] or 'Behavior') if head else '', property=head[3] if head else '',
                       start=head.start() if head else pos, brace=pos, end=len(source), parent=stack[-1] if stack else None)
            objects.append(obj)
            stack.append(obj)
        elif stack:
            stack.pop()['end'] = pos + 1
    return objects


def owner_at(objects: list[dict], offset: int) -> dict | None:
    owners = [o for o in objects if o['brace'] < offset < o['end'] and o['type']]
    return max(owners, key=lambda o: o['brace']) if owners else None


def direct_source(source: str, obj: dict, objects: list[dict]) -> str:
    """The object's own text with every child object blanked out (offsets kept)."""
    chars = list(source[obj['brace'] + 1:obj['end'] - 1])
    for child in objects:
        if child['parent'] is obj:
            for pos in range(child['start'], child['end']):
                if obj['brace'] < pos < obj['end'] and chars[pos - obj['brace'] - 1] != '\n':
                    chars[pos - obj['brace'] - 1] = ' '
    return ''.join(chars)


# ------------------------------------------------------------------------------------------------------------------------ Qt
QT_BINDING = re.compile(r'(?<![.\w])visible\s*:\s*([^;\n}]+)')
GEOMETRY = re.compile(r'(?:^|[\s;{])(width|height|implicitWidth|implicitHeight|Window\.width|Window\.height|availableWidth)\b')
NATIVE = {'Window', 'ApplicationWindow'}
POSE = ('x', 'y', 'opacity', 'scale', 'rotation')


def _animated(clean: str) -> set[str]:
    """Property names this file animates: Behavior on P, X on P, property(-ies): "P"."""
    names = set(re.findall(r'\bBehavior\s+on\s+(\w+)', clean))
    names |= set(re.findall(r'\b\w*(?:Animation|Animator)\s+on\s+(\w+)', clean))
    return names


def _animated_raw(source: str) -> set[str]:
    names = set(re.findall(r'\bproperty\s*:\s*"(\w+)"', source))
    for group in re.findall(r'\bproperties\s*:\s*"([\w, ]+)"', source):
        names |= {n.strip() for n in group.split(',')}
    return names


def _declarations(clean: str, source: str) -> dict[str, str]:
    out = {}
    for m in re.finditer(r'\bproperty\s+[\w<>.]+\s+(\w+)\s*:\s*([^;\n]+)', clean):
        out[m[1]] = source[m.start(2):m.end(2)].strip()
    return out


class QtProject:
    """Cross-file facts: component roots, property declarations and the values callers pass in."""

    def __init__(self, paths: list[Path]):
        self.sources = {p.stem: p.read_text(encoding='utf-8') for p in paths}
        self.clean = {k: mask(v) for k, v in self.sources.items()}
        self.roots = {}
        for name, clean in self.clean.items():
            m = re.search(r'^([A-Z]\w*)\s*\{', clean, re.M)
            if m:
                self.roots[name] = m[1]
        self.decls = {k: _declarations(self.clean[k], v) for k, v in self.sources.items()}
        self.objects = {k: qml_objects(v) for k, v in self.sources.items()}

    def chain(self, kind: str) -> list[str]:
        out = [kind]
        while out[-1] in self.roots and len(out) < 20:
            out.append(self.roots[out[-1]])
        return out

    def assignments(self, component: str, prop: str) -> list[tuple[str, str]]:
        """(file, expression) for every caller that sets `prop` on an instance of `component`."""
        out = []
        for name, objects in self.objects.items():
            source = self.sources[name]
            for obj in objects:
                if obj['type'] != component:
                    continue
                own = direct_source(source, obj, objects)
                for m in re.finditer(r'(?<![.\w])' + prop + r'\s*:\s*([^;\n}]+)', mask(own)):
                    out.append((name, own[m.start(1):m.end(1)].strip()))
        return out

    def configured(self, file: str, expression: str) -> bool:
        """True when every name is a literal-default property of this component that no QML binding or assignment ever
        changes: a per-instance setting fixed for the item's lifetime (only C++ tests or the default set it)."""
        names = set(re.findall(r'(?<![.\w])(?:root\.)?([a-zA-Z_]\w*)(?!\s*\()', mask(expression))) - {'root', 'true', 'false', 'null'}
        if not names:
            return False
        for name in names:
            decl = self.decls.get(file, {}).get(name)
            if decl is None or not re.fullmatch(r'"[^"]*"|-?\d+(?:\.\d+)?|true|false', decl):
                return False
            if self.assignments(file, name):
                return False
            if any(re.search(r'\.' + name + r'\s*=(?!=)', clean) for clean in self.clean.values()):
                return False
            if re.search(r'(?<![.\w])' + name + r'\s*=(?!=)', self.clean[file]):
                return False
        return True

    def responsive(self, file: str, expression: str, seen: frozenset = frozenset()) -> bool:
        """True when every name in the expression is derived from a width/height (the layout follows the window size)."""
        names = [n for n in re.findall(r'(?<![.\w])(?:root\.)?([a-zA-Z_]\w*)(?!\s*\()', mask(expression))
                 if n not in ('root', 'true', 'false', 'null', 'undefined', 'Theme', 'Logic')]
        if not names:
            return False
        for name in names:
            if (file, name) in seen:
                return False
            if GEOMETRY.search(' ' + name):
                continue
            decl = self.decls.get(file, {}).get(name)
            if decl is None:
                return False
            if GEOMETRY.search(' ' + mask(decl)):
                continue
            if re.fullmatch(r'"[^"]*"|\d+(?:\.\d+)?|true|false', decl):
                callers = self.assignments(file, name)
                if callers and all(self.responsive(f, e, seen | {(file, name)}) for f, e in callers):
                    continue
                return False
            if not self.responsive(file, decl, seen | {(file, name)}):
                return False
        return True


def qt_classify(paths: list[Path], rel) -> list[dict]:
    project = QtProject(paths)
    rows = []
    for path in paths:
        name = path.stem
        source, clean, objects = project.sources[name], project.clean[name], project.objects[name]
        animated = _animated(clean) | _animated_raw(source)
        for m in QT_BINDING.finditer(clean):
            expression = source[m.start(1):m.end(1)].strip()
            obj = owner_at(objects, m.start())
            if not obj or obj['type'] == 'Behavior':
                continue
            row = dict(path=rel(path), line=source.count('\n', 0, m.start()) + 1, text=source[m.start():m.end()].strip()[:90],
                       platform='qt', object=obj['type'])
            rows.append(row)
            row['category'], row['reason'] = _qt_reason(project, name, source, obj, objects, expression, animated)
    return rows


def _qt_reason(project, name, source, obj, objects, expression, animated):
    clean_expr = mask(expression).strip()
    if clean_expr in ('true', 'false'):
        return 'b-constant', 'constant: never toggles while shown'
    if set(project.chain(obj['type'])) & NATIVE:
        return 'b-native-window', 'native window: the operating system shows and hides it'
    if re.search(r'(?<!\w)(?:\w+\.)?opacity\s*>', clean_expr) and 'opacity' in animated:
        return 'b-follows-opacity', 'visibility follows an animated opacity'
    for clock in re.finditer(r'(?<![.\w])(?:[a-zA-Z_]\w*\.)*([a-zA-Z_]\w*)\s*(?:>|<|>=|<=)\s*\d', clean_expr):
        if clock[1] in animated and clock[1] != 'opacity':
            return 'b-animated-clock', f'gated by animated `{clock[1]}`'
    if re.fullmatch(r'(?:[a-zA-Z_]\w*\.)?(?:width|height|implicitWidth|implicitHeight)\s*>\s*0', clean_expr):
        return 'b-zero-size', 'hidden only once its size is already 0: nothing visible is cut'
    if re.fullmatch(r'[a-zA-Z_]\w*\.visible', clean_expr):
        return 'b-mirrors', 'copies another item\'s visibility, which is checked where it is set'
    names = set(re.findall(r'(?<![.\w])([a-zA-Z_]\w*)', clean_expr))
    if names and names <= {'index', 'modelData', 'model'} | {n for n in names if re.search(r'\b' + n + r'\.(?:index|modelData)\b', clean_expr)}:
        if re.search(r'\b(?:index|modelData|model)\b', clean_expr):
            return 'b-static-delegate', 'depends only on its delegate\'s data: created and removed with the row'
    own = mask(direct_source(source, obj, objects))
    size = re.fullmatch(r'([\w.]+)\s*>\s*0', clean_expr)
    if size and re.search(r'(?<![.\w])(?:width|height)\s*:\s*' + re.escape(size[1]) + r'\s*(?:[;\n}]|$)', own):
        return 'b-zero-size', f'its size is `{size[1]}`: hidden only once nothing is left to see'
    for pose in re.finditer(r'(?<![.\w])(' + '|'.join(POSE) + r')\s*:\s*([^;\n}]+)', own):
        moving = set(re.findall(r'(?<![\w])([a-zA-Z_]\w*)', pose[2])) & animated - {'opacity', 'x', 'y'}
        if moving:
            return 'b-transition-layer', f'the item itself moves with animated `{sorted(moving)[0]}`'
    transform = re.search(r'\btransform\s*:\s*[^\n]*\{([^}]*)\}', own)
    if transform and set(re.findall(r'[a-zA-Z_]\w*', transform[1])) & animated:
        return 'b-transition-layer', 'the item itself slides with an animated transform'
    if project.configured(name, expression):
        return 'b-constant', 'per-instance setting that nothing changes after creation'
    if project.responsive(name, expression):
        return 'b-responsive', 'layout follows the window size'
    return 'a-hard', 'direct conditional with no transition on this object'


def qt_reveal_targets(paths: list[Path], rel) -> list[str]:
    """A Reveal controls its parent. Inside a component whose children go to a default property (or a Flickable's contentItem)
    the parent is that inner holder, so the Reveal must name its item: Reveal { target: someId; ... }."""
    project = QtProject(paths)
    holders = {'Flickable', 'ListView', 'GridView', 'ScrollView'}
    out = []
    for path in paths:
        name = path.stem
        source, clean, objects = project.sources[name], project.clean[name], project.objects[name]
        for m in re.finditer(r'\bReveal\s*\{', clean):
            reveal = next(o for o in objects if o['start'] == m.start())
            if re.search(r'(?<![.\w])target\s*:', direct_source(source, reveal, objects)):
                continue
            owner = reveal['parent']
            chain = project.chain(owner['type']) if owner else []
            if any(re.search(r'\bdefault\s+property', project.clean.get(t, '')) for t in chain) or set(chain) & holders:
                out.append(f"{rel(path)}:{source.count(chr(10), 0, m.start()) + 1} Reveal trong {owner['type']} phải có `target:`")
    return out


# ------------------------------------------------------------------------------------------------------------------------ web
def web_classify(paths: list[Path], rel) -> list[dict]:
    payload = [dict(path=rel(p), source=p.read_text(encoding='utf-8')) for p in paths]
    proc = subprocess.run(['node', str(HERE / 'ui_instant_web.mjs')], input=json.dumps(payload),
                          encoding='utf-8', capture_output=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    return json.loads(proc.stdout)


# ------------------------------------------------------------------------------------------------------------------------ Android
KT_IF = re.compile(r'(?<![\w.])if\s*\(')
KT_COMPOSE = {'Box', 'Column', 'Row', 'BasicText', 'Text', 'Image', 'Icon', 'Spacer', 'LazyColumn', 'LazyRow', 'Canvas', 'Surface',
              'BasicTextField', 'Layout', 'FlowRow', 'FlowColumn', 'LazyVerticalGrid', 'HorizontalPager', 'VerticalPager',
              'SelectionContainer', 'Popup', 'Dialog', 'DropdownMenu', 'CircularProgressIndicator', 'LinearProgressIndicator'}
KT_MOTION = {'AnimatedVisibility', 'AnimatedContent', 'Crossfade', 'Reveal'}


def kt_composables(paths: list[Path]) -> set[str]:
    names = set(KT_COMPOSE)
    for p in paths:
        names |= set(re.findall(r'@Composable\s+(?:(?:private|internal|public|inline)\s+)*fun\s+(?:[\w.<>, ]+\.)?(\w+)\s*\(',
                                p.read_text(encoding='utf-8')))
    return names


def _balanced(clean: str, start: int, open_: str = '(', close: str = ')') -> int:
    depth = 0
    for i in range(start, len(clean)):
        if clean[i] == open_:
            depth += 1
        elif clean[i] == close:
            depth -= 1
            if depth == 0:
                return i + 1
    return len(clean)


def kt_classify(paths: list[Path], rel, all_paths: list[Path] | None = None) -> list[dict]:
    composables = kt_composables(all_paths or paths)
    rows = []
    for path in paths:
        source = path.read_text(encoding='utf-8')
        clean = mask(source)
        for m in KT_IF.finditer(clean):
            cond_end = _balanced(clean, m.end() - 1)
            after = re.match(r'\s*(\{?)\s*(?:[\w.]+\.)?([A-Z]\w*)\s*[({]', clean[cond_end:])
            if not after:
                continue
            target = after[2]
            line_start = clean.rfind('\n', 0, m.start()) + 1
            prefix = clean[line_start:m.start()]
            # An expression `if` (val x = if (...) A else B) picks a value, it does not show or hide a node.
            if re.search(r'(?:=|return|->|\(|,)\s*$', prefix):
                continue
            row = dict(path=rel(path), line=source.count('\n', 0, m.start()) + 1,
                       text=source[line_start:source.find('\n', m.start())].strip()[:90], platform='android', object=target)
            body_end = cond_end + len(after[0])
            if after[1]:
                body_end = _balanced(clean, cond_end + after.start(1), '{', '}')
            else:
                body_end = _balanced(clean, cond_end + after.end() - 1, *(('(', ')') if after[0].rstrip()[-1] == '(' else ('{', '}')))
            swap = re.match(r'\s*else\b', clean[body_end:])
            body = clean[cond_end:body_end]
            if target not in composables:
                row['category'], row['reason'] = 'b-not-ui', f'`{target}` is not a composable: no node appears or disappears'
            elif re.search(r'graphicsLayer\s*\{[^}]*\balpha\s*=\s*[A-Za-z_]', body):
                row['category'], row['reason'] = 'b-transition-layer', 'the node fades itself (graphicsLayer alpha from an animated value)'
            elif _kt_inside_motion(clean, m.start(), clean[m.end():cond_end - 1]):
                row['category'], row['reason'] = 'b-parent-motion', 'inside an animated container that owns this content'
            else:
                row['category'], row['reason'] = ('a-swap' if swap else 'a-hard'), ('content swap without crossfade' if swap else 'direct conditional')
            rows.append(row)
    return rows


def _kt_inside_motion(clean: str, offset: int, condition: str) -> bool:
    """Directly inside the content lambda of an animated container that owns THIS condition: AnimatedVisibility(same condition),
    or AnimatedContent/Crossfade whose lambda parameter the condition reads. An unrelated parent animation proves nothing."""
    depth = 0
    i = offset
    while i > 0:
        i -= 1
        c = clean[i]
        if c == '}':
            depth += 1
        elif c == '{':
            if depth == 0:
                head = clean[max(0, i - 300):i]
                if re.search(r'\bfun\s+\w+\s*\([^)]*\)\s*(?::\s*\w+\s*)?$', head):
                    return False
                tail = head.rstrip()
                args = ''
                if tail.endswith(')'):
                    depth_ = 0
                    for j in range(len(tail) - 1, -1, -1):
                        depth_ += {')': 1, '(': -1}.get(tail[j], 0)
                        if depth_ == 0:
                            args, tail = tail[j + 1:-1], tail[:j].rstrip()
                            break
                call = re.search(r'([A-Z]\w*)$', tail)
                if call and call[1] in KT_MOTION:
                    args = args.split(',')[0].strip()
                    params = re.match(r'\s*(\w+)\s*->', clean[i + 1:i + 80])
                    reads = params[1] if params else 'it'
                    if call[1] == 'AnimatedVisibility' or call[1] == 'Reveal':
                        return re.sub(r'\s+', '', args.removeprefix('visible').lstrip(' =')) == re.sub(r'\s+', '', condition)
                    return bool(re.search(r'(?<![.\w])' + reads + r'\b', condition))
            else:
                depth -= 1
    return False


def classify(root: Path, qt: list[Path], web: list[Path], android: list[Path]) -> list[dict]:
    rel = lambda p: p.relative_to(root).as_posix()
    return qt_classify(qt, rel) + web_classify(web, rel) + kt_classify(android, rel)
