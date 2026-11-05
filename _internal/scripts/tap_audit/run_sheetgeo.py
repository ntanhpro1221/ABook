"""Build gallery and check real player geometry in private headless Edge (CPU only).

From the task root: <runtime-python> -X utf8 _internal/scripts/tap_audit/run_sheetgeo.py
Exit 0 = PASS, 1 = FAIL, 2 = Edge unavailable. --inject-fault must exit 1.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

sys.dont_write_bytecode = True
from ui_tap_audit import limit_cpu


def find_edge(override=None):
    candidates = [override] if override else [shutil.which('msedge'), shutil.which('msedge.exe')]
    if not override:
        for key in ('PROGRAMFILES(X86)', 'PROGRAMFILES', 'LOCALAPPDATA'):
            if os.environ.get(key):
                candidates.append(str(Path(os.environ[key]) / 'Microsoft/Edge/Application/msedge.exe'))
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and Path(candidate).name.lower() in ('msedge.exe', 'msedge', 'microsoft-edge'):
            return str(Path(candidate).resolve())
    raise FileNotFoundError('Microsoft Edge missing; sheetgeo requires Edge, or --edge PATH to msedge.exe')


def gallery_dependency(ui, root):
    """Shared junction can lag this branch. Use exactly its lockfile package, locally."""
    locked = json.loads((ui / 'package-lock.json').read_text(encoding='utf-8'))['packages']['node_modules/lucide-react']
    installed = json.loads((ui / 'node_modules/lucide-react/package.json').read_text(encoding='utf-8'))
    if installed['version'] == locked['version']:
        return None
    dest = root / '.sheetgeo-deps' / ('lucide-react-' + locked['version'])
    target = dest / 'package/dist/esm/lucide-react.mjs'
    if not target.is_file():
        print(f"Gallery dependency: shared lucide-react {installed['version']}; isolate locked {locked['version']} under {dest}", flush=True)
        data = urllib.request.urlopen(locked['resolved'], timeout=30).read()
        algorithm, expected = locked['integrity'].split('-', 1)
        assert base64.b64encode(hashlib.new(algorithm, data).digest()).decode() == expected, 'dependency integrity mismatch'
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            archive.extractall(dest, filter='data')
    return str(target)


def main():
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--edge')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--inject-fault', action='store_true')
    parser.add_argument('--no-build', action='store_true', help='use gallery already built from this tree')
    args = parser.parse_args()
    try:
        edge = find_edge(args.edge)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    limit_cpu()
    env = dict(os.environ, PYTHON=sys.executable, PYTHONIOENCODING='utf-8', CUDA_VISIBLE_DEVICES='-1')
    ui = root / '_internal/ui'
    output = (args.output or root / ('sheetgeo-fault.json' if args.inject_fault else 'sheetgeo.json')).resolve()
    if not args.no_build:
        dependency = gallery_dependency(ui, root)
        if dependency:
            env['SHEETGEO_LUCIDE'] = dependency
        built = subprocess.run(['node', 'scripts/build_sheetgeo.mjs'], cwd=ui, env=env,
                               capture_output=True, text=True, encoding='utf-8',
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        print(built.stdout, end='')
        if built.returncode:
            print(built.stderr, file=sys.stderr)
            print('FAIL | gallery build', file=sys.stderr)
            return 1
    command = ['node', str(ui / 'scripts/sheetgeo.mjs'), '--edge', edge, '--task-dir', str(root), '--output', str(output)]
    if args.inject_fault:
        command.append('--inject-fault')
    output.unlink(missing_ok=True)
    completed = subprocess.run(command, cwd=root, env=env,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if output.is_file():
        report = json.loads(output.read_text(encoding='utf-8'))
        for result in report['results']:
            print(f"{result['status']} | {result['width']}x900 | content={result.get('contentWidth')} {result.get('widthClass')} | {len(result['trials'])} trials", flush=True)
            for check in result['checks']:
                if not check['pass']:
                    print('  FAIL | ' + json.dumps(check, ensure_ascii=False), flush=True)
            for trial in result['trials']:
                for check in trial['checks']:
                    if not check['pass']:
                        print(f"  FAIL | {trial['name']} | " + json.dumps(check, ensure_ascii=False), flush=True)
        print(f"{report['status']} | sheetgeo | {output}", flush=True)
        if report.get('error'):
            print(report['error'], file=sys.stderr)
        return completed.returncode if report['status'] == 'PASS' else 1
    print('FAIL | no sheetgeo report produced', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
