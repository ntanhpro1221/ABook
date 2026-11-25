"""Reject invisible actions and action-colored information in captured UI trees.

Consumes the unmerged Compose tree and Qt item tree next to each screenshot.
DOM uses ui/scripts/probes/affordance.js on the rendered gallery. Exit 1 means
findings; missing, empty or stale tree/image pairs fail instead of passing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

ACCENTS = {'#8a5309', '#f0b961'}
ACTION_INKS = ACCENTS | {'#b23b33', '#ef7b70'}


def action_ink(color):
    if color.lower() in ACTION_INKS: return True
    if len(color) != 7: return False
    r,g,b = (int(color[i:i+2],16) for i in (1,3,5))
    # Compose interpolates the standard accent toward body ink in Oklab while
    # a selection slides. Its visibly warm intermediate ink is still a cue.
    return r > 40 and r-g > 20 and g-b > 10

def shown(node):
    r = node.get('visible', node.get('bounds', [0, 0, 0, 0]))
    return r[2] - r[0] > 1 and r[3] - r[1] > 1


def text_spacing(nodes, exposed=lambda n: True, minimum=8):
    """Compare rendered lines in logical dp, never padded text containers.

    Only independent text nodes on the exposed surface count. Lines of one
    paragraph and parent/child semantic copies are not adjacent labels.
    """
    by_id = {n['id']: n for n in nodes}
    def chain(n):
        result = []
        while n['parent'] in by_id:
            n = by_id[n['parent']]
            result.append(n['id'])
        return result
    lines = []
    for n in nodes:
        if not shown(n) or not exposed(n) or not n.get('text', '').strip(): continue
        visible = n.get('visible', n['bounds'])
        for line in n.get('lines', []):
            if not line.get('text', '').strip(): continue
            b = line['bounds']
            box = [max(b[0], visible[0]), max(b[1], visible[1]), min(b[2], visible[2]), min(b[3], visible[3])]
            if box[2] > box[0] and box[3] > box[1]: lines.append((n, box, chain(n)))
    findings = []
    reported = set()
    for i, (a, x, a_chain) in enumerate(lines):
        for b, y, b_chain in lines[i+1:]:
            if a['id'] == b['id'] or a['id'] in b_chain or b['id'] in a_chain: continue
            # A fixed header, popup or drag target can cover a scrolling body.
            # Those branches are overlapping surfaces, not adjacent row labels.
            common = next((id for id in a_chain if id in b_chain), None)
            if common is not None:
                def branch(n, parents):
                    i = parents.index(common)
                    return by_id[parents[i-1]] if i else n
                ab, bb = branch(a, a_chain), branch(b, b_chain)
                ax, bx = ab['bounds'], bb['bounds']
                if (min(ax[2], bx[2]) > max(ax[0], bx[0])+1 and min(ax[3], bx[3]) > max(ax[1], bx[1])+1
                        and any(not node.get('text') and box[3]-box[1] > max(64, 3*max(x[3]-x[1], y[3]-y[1]))
                                for node, box in [(ab, ax), (bb, bx)])):
                    continue
            overlap = min(x[3], y[3]) - max(x[1], y[1])
            if overlap < min(x[3]-x[1], y[3]-y[1]) * .6: continue
            left, right = (x, y) if x[0] <= y[0] else (y, x)
            gap = right[0] - left[2]
            key = tuple(sorted((a['id'], b['id'])))
            if gap < minimum - .1 and key not in reported:
                reported.add(key)
                findings.append({'rule': 'TEXT_GAP', 'id': a['id'], 'other_id': b['id'],
                                 'text': a['text'][:140], 'other_text': b['text'][:140],
                                 'gap_dp': round(gap, 2), 'bounds': x, 'other_bounds': y})
    return findings

def audit(tree, image=None):
    nodes = tree['nodes']
    if image is not None and tree.get('platform') == 'qt':
        # QtTest clips an oversized item to its offscreen window; it does not
        # shrink the screenshot to fit. Keep the actual uniform device scale.
        ratio = tree.get('pixel_ratio', 1)
        width, height = image.shape[1]/ratio, image.shape[0]/ratio
        nodes = [dict(n, visible=[max(0,n.get('visible',n['bounds'])[0]), max(0,n.get('visible',n['bounds'])[1]),
                                 min(width,n.get('visible',n['bounds'])[2]), min(height,n.get('visible',n['bounds'])[3])]) for n in nodes]
    if not nodes:
        raise ValueError('Empty UI tree')
    children = {n['id']: [] for n in nodes}
    by_id = {n['id']: n for n in nodes}
    for n in nodes:
        if n['parent'] >= 0:
            children[n['parent']].append(n)

    def ancestors(n):
        while n['parent'] >= 0:
            n = by_id[n['parent']]
            yield n

    def clickable(n):
        return n.get('clickable', False) and not n.get('disabled', False)

    def descendants(n):
        yield n
        for child in children[n['id']]:
            if shown(child) and not clickable(child):
                yield from descendants(child)

    # Modal sheets block earlier content even though Compose keeps that content
    # in its unmerged tree. Audit the exposed surface, as the DOM probe does.
    modal_layers = [n for n in nodes if shown(n) and n.get('tag') == 'sheet_layer' and children[n['id']]]
    qt_modals = [n for n in nodes if shown(n) and n.get('modal')]
    if qt_modals: modal_layers = [max(qt_modals, key=lambda n: (n.get('z', 0), n['id']))]
    foregrounds = [n for n in nodes if shown(n) and n.get('tag') == 'now_playing']
    scrims = [n for n in nodes if shown(n) and clickable(n)
              and n.get('role') in (None, 'button')
              and n['bounds'][2]-n['bounds'][0] >= tree.get('width', float('inf'))*.95
              and n['bounds'][3]-n['bounds'][1] >= tree.get('height', float('inf'))*.95
              and not any(p.get('text', '').strip() for p in descendants(n))]

    def exposed(n):
        if any(not shown(a) for a in ancestors(n)):
            return False
        chain = {n['id'], *(a['id'] for a in ancestors(n))}
        if modal_layers and modal_layers[-1]['id'] not in chain:
            return False
        if foregrounds and n['id'] < foregrounds[-1]['id']:
            return False
        return not scrims or n['id'] >= scrims[-1]['id']

    def text_action(n):
        if any(clickable(p) for p in [n, *ancestors(n)]): return True
        # Qt may place its accessible Interactive over the ink of a Text item.
        # It must cover every rendered line, not merely be a nested button.
        boxes = [line['bounds'] for line in n.get('lines', []) if line.get('text', '').strip()]
        if not boxes: return False
        owners = {n['id'], *(a['id'] for a in ancestors(n))}
        for action in nodes:
            if not clickable(action) or not owners.intersection(a['id'] for a in ancestors(action)): continue
            b = action.get('visible', action['bounds'])
            if all(b[0] <= box[0]+1 and b[1] <= box[1]+1 and b[2] >= box[2]-1 and b[3] >= box[3]-1 for box in boxes):
                return True
        return False

    def painted_cue(n):
        if image is None:
            return False
        sx, sy = (tree.get('pixel_ratio', 1),)*2 if tree.get('platform') == 'qt' else (image.shape[1] / tree['width'], image.shape[0] / tree['height'])
        r = n.get('visible', n['bounds'])
        x0, y0, x1, y1 = (round(r[0]*sx), round(r[1]*sy), round(r[2]*sx), round(r[3]*sy))
        crop = image[max(0,y0):max(0,y1), max(0,x0):max(0,x1), :3].astype(float)
        if min(crop.shape[:2], default=0) < 3:
            return False
        # Underlines, control borders and painted selection tracks are real pixels,
        # including the shared indicator drawn by a sibling rather than a child.
        accent = np.array([[138,83,9], [240,185,97], [212,145,43], [233,169,69]])
        edge = np.concatenate([crop[:max(1,round(sy*3))].reshape(-1,3), crop[-max(1,round(sy*3)):].reshape(-1,3)])
        if (np.min(np.max(abs(edge[:,None,:]-accent),axis=2),axis=1)<12).sum() >= max(6, crop.shape[1]*0.2):
            return True
        background = np.median(crop.reshape(-1,3), axis=0)
        # Scroll-edge fades blend a real underline into its background. Accept
        # only points on that color segment, never an arbitrary warm rectangle.
        direction = accent - background
        length = np.sum(direction*direction, axis=1).clip(1)
        mix = np.sum((edge[:,None,:]-background)*direction[None,:,:], axis=2)/length
        residual = np.max(abs(edge[:,None,:]-(background+mix[:,:,None]*direction)), axis=2)
        if np.any((mix > .025) & (mix < 1.05) & (residual < 2), axis=1).sum() >= max(6, crop.shape[1]*.5):
            return True
        # Solid inset/outlined controls differ from the pixels just outside them.
        outer = image[max(0,y0-round(sy*2)):max(0,y0), max(0,x0):max(0,x1), :3]
        contrast = 6 if n.get('selected') else 12
        if outer.size and np.max(abs(np.median(crop.reshape(-1,3),axis=0)-np.median(outer.reshape(-1,3),axis=0))) > contrast:
            return True
        # A native checkbox may be an empty outline with neutral ink. Require
        # straight painted edges on both axes, never the scattered text pixels.
        base = np.median(crop.reshape(-1,3),axis=0)
        row = np.median(crop,axis=1)
        col = np.median(crop,axis=0)
        row_edge = (np.max(abs(row-base),axis=1)>6) & ((np.max(abs(crop-row[:,None,:]),axis=2)<3).mean(axis=1)>=.5)
        col_edge = (np.max(abs(col-base),axis=1)>6) & ((np.max(abs(crop-col[None,:,:]),axis=2)<3).mean(axis=0)>=.5)
        if row_edge.sum() >= 1 and col_edge.sum() >= 1: return True
        return False

    def ink_visible(parts):
        if image is None: return True
        texts = [p for p in parts if p.get('text') and p.get('color')]
        if not texts: return True
        sx, sy = (tree.get('pixel_ratio', 1),)*2 if tree.get('platform') == 'qt' else (image.shape[1] / tree['width'], image.shape[0] / tree['height'])
        for p in texts:
            r = p.get('visible', p['bounds'])
            x0,y0,x1,y1 = (round(r[0]*sx),round(r[1]*sy),round(r[2]*sx),round(r[3]*sy))
            crop = image[max(0,y0):max(0,y1),max(0,x0):max(0,x1),:3].astype(float)
            color = np.array([int(p['color'][i:i+2],16) for i in (1,3,5)])
            if crop.size and (np.max(abs(crop-color),axis=2)<6).sum() >= 3: return True
        return False

    findings = []
    checked = 0
    for n in nodes:
        if not shown(n) or not exposed(n):
            continue
        if clickable(n):
            own = list(descendants(n))
            drawn_text = ' '.join(p.get('text', '') for p in own).strip()
            text = drawn_text or n.get('description', '')
            b = n['bounds']
            full_surface = b[2]-b[0] >= tree.get('width', float('inf'))*.95 and b[3]-b[1] >= tree.get('height', float('inf'))*.95
            if not drawn_text and full_surface and n.get('role') in (None, 'button'): continue
            visible = n.get('visible', b)
            if visible[3]-visible[1] < (b[3]-b[1])*.95: continue
            if visible[2]-visible[0] < (b[2]-b[0])*.5: continue
            # Blank gesture zones and native editable/range controls are not text actions.
            if not text or n.get('editable') or n.get('role') in ('slider', 'textfield') or n.get('type', '').split('_')[0] == 'Slider':
                continue
            if not ink_visible(own): continue
            checked += 1
            # An absolute Qt action can cover ink declared as sibling items.
            # Only its own parent's non-action graphics fully inside the target
            # count; nested buttons still cannot lend their icons.
            overlay = []
            if not drawn_text and n['parent'] >= 0:
                for p in descendants(by_id[n['parent']]):
                    r = p.get('visible', p['bounds'])
                    if p['id'] != n['id'] and r[0] >= b[0]-1 and r[1] >= b[1]-1 and r[2] <= b[2]+1 and r[3] <= b[3]+1:
                        overlay.append(p)
            own += overlay
            cue = any(p.get('icon') or p.get('graphic') or p.get('type', '').split('_')[0] in ('SkipGlyph', 'DownloadRing', 'VoiceCheck', 'Switch', 'ImportBox') or action_ink(p.get('color', '')) or
                      p.get('text', '').rstrip().endswith(('›','→','↗','+')) for p in own)
            # A row may repeat the switch action; its visible native control is
            # an affordance for that same label, not an unrelated child button.
            cue = cue or any(c.get('role') in ('checkbox', 'switch') and c.get('description') and c['description'] in drawn_text
                             and n['id'] in {a['id'] for a in ancestors(c)} for c in nodes)
            cue = cue or any(c.get('role') in ('checkbox', 'switch') and c.get('description') and c['parent'] == n['parent']
                             and c['description'] in drawn_text for c in nodes)
            if not cue and not painted_cue(n):
                findings.append({'rule': 'AFFORDANCE_CLICK', 'id': n['id'], 'tag': n.get('tag', ''), 'text': text[:140], 'bounds': n['bounds']})
        if n.get('text') and n.get('color', '').lower() in ACCENTS and not text_action(n):
            findings.append({'rule': 'AFFORDANCE_ACCENT', 'id': n['id'], 'tag': n.get('tag', ''), 'text': n['text'][:140], 'bounds': n['bounds']})
    # Semantic trees can retain a fully covered outgoing text item. Verify its
    # ink before comparing it with a foreground label, and trim whitespace from
    # the measured line rather than treating its padded box as painted text.
    spacing_nodes = nodes
    if image is not None:
        sx, sy = (tree.get('pixel_ratio', 1),)*2 if tree.get('platform') == 'qt' else (image.shape[1]/tree['width'], image.shape[0]/tree['height'])
        spacing_nodes = []
        for n in nodes:
            lines = []
            color = n.get('color', '')
            for line in n.get('lines', []):
                if len(color) != 7:
                    lines.append(line); continue
                b = line['bounds']; v = n.get('visible', n['bounds'])
                x0,y0,x1,y1 = max(0,round(max(b[0],v[0])*sx)),max(0,round(max(b[1],v[1])*sy)),min(image.shape[1],round(min(b[2],v[2])*sx)),min(image.shape[0],round(min(b[3],v[3])*sy))
                crop = image[y0:y1,x0:x1,:3]
                if not crop.size: continue
                rgb = np.array([int(color[i:i+2],16) for i in (1,3,5)])
                yy,xx = np.where(np.max(abs(crop.astype(float)-rgb),axis=2)<12)
                if len(xx) < 3: continue
                lines.append(dict(line,bounds=[(x0+int(xx.min()))/sx,b[1],(x0+int(xx.max())+1)/sx,b[3]]))
            spacing_nodes.append(dict(n,lines=lines))
    findings.extend(text_spacing(spacing_nodes, exposed))
    return checked, findings

def audit_dirs(directories, rules=None, since=None):
    """Audit every captured tree/image pair under `directories`. `since` (epoch seconds) skips pairs
    written before it: a release gate audits only what this run captured, not leftovers of removed tests."""
    report = {'screens': 0, 'controls': 0, 'findings': [], 'errors': []}
    fresh = lambda path: since is None or path.stat().st_mtime >= since
    for directory in directories:
        paths = sorted(p for p in directory.rglob('*.tree.json') if fresh(p))
        for png in directory.rglob('*.png'):
            if fresh(png) and not png.with_suffix('.tree.json').exists():
                report['errors'].append(f'Missing captured tree: {png}')
        if not paths:
            report['errors'].append(f'No captured trees: {directory}')
        for path in paths:
            try:
                tree = json.loads(path.read_text(encoding='utf-8'))
                png = path.with_name(tree['image'])
                if hashlib.sha256(png.read_bytes()).hexdigest() != tree['image_sha256']:
                    raise ValueError('Stale tree/image checksum')
                image = np.asarray(Image.open(png).convert('RGB'))
                count, findings = audit(tree, image)
                report['screens'] += 1
                report['controls'] += count
                report['findings'].extend(dict(f, image=str(png)) for f in findings if not rules or f['rule'] in rules)
            except (OSError, ValueError, KeyError) as error:
                report['errors'].append(f'{path}: {error}')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', nargs='+', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--rules', nargs='+', choices=['AFFORDANCE_CLICK', 'AFFORDANCE_ACCENT', 'TEXT_GAP'],
                        help='Run only these rules; image/tree integrity is always checked')
    args = parser.parse_args(argv)
    report = audit_dirs(args.directories, args.rules)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Affordance: {report['screens']} screens, {report['controls']} controls, {len(report['findings'])} findings, {len(report['errors'])} errors")
    return int(bool(report['findings'] or report['errors']))

if __name__ == '__main__':
    raise SystemExit(main())
