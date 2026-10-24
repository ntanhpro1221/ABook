"""Audit the built UI using disposable fixture data and coordinate mouse/touch input.

From _internal: python scripts/tap_audit/run.py [--inject-fault]
Requires the existing runtime's httpx/websockets and installed Edge or Chrome.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
from ui_tap_audit import find_browser, limit_cpu, load_scenarios, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--static-dir', type=Path, help='override this tree\'s built UI')
    parser.add_argument('--edge', help='Edge/Chrome executable override')
    parser.add_argument('--only', help='scenario name substring (no match fails)')
    parser.add_argument('--json', action='store_true', help='emit JSON only on stdout')
    parser.add_argument('--output', type=Path, help='save the full JSON report')
    parser.add_argument('--inject-fault', action='store_true', help='negative control; must FAIL')
    args = parser.parse_args()
    started = time.monotonic()
    limit_cpu()
    try:
        args.edge = find_browser(args.edge)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    here = Path(__file__).resolve().parent
    static = (args.static_dir or here.parents[1] / 'abook/webui/static').resolve()
    payload = dict(status='FAIL', results=[], injected=args.inject_fault, static=str(static))
    try:
        if not (static / 'index.html').is_file():
            raise RuntimeError(f'Built UI missing: {static}; run Vite build in ui/ first')
        load_scenarios(here / 'scenarios.json')
        # Both the fixture and its application preferences live below this new root.
        with tempfile.TemporaryDirectory(prefix='abook-tapaudit-state-') as temp:
            root = Path(temp).resolve()
            state = root / 'fixture'
            env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='-1')
            with (root / 'server.log').open('w+', encoding='utf-8') as log:
                server = subprocess.Popen(
                    [sys.executable, '-B', str(here / 'serve_tap_fixture.py'),
                     '--state-dir', str(state), '--port', '0', '--static-dir', str(static)],
                    stdin=subprocess.PIPE, stdout=log, stderr=log, env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                )
                try:
                    ready = state / 'ready.json'
                    deadline = time.monotonic() + 60
                    while not ready.is_file():
                        if server.poll() is not None or time.monotonic() > deadline:
                            log.flush(); log.seek(0)
                            raise RuntimeError('Fixture failed to start:\n' + log.read())
                        time.sleep(.1)
                    metadata = json.loads(ready.read_text(encoding='utf-8'))
                    args.url = metadata['url']
                    args.scenarios = metadata['scenarios']
                    payload = asyncio.run(run(args))
                    payload['static'] = str(static)
                finally:
                    # Closing our pipe requests server.stop() and app.close().
                    server.stdin.close()
                    try:
                        server.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        server.kill(); server.wait(timeout=10)
                    payload.setdefault('cleanup', {})['serverExited'] = server.poll() is not None
        payload.setdefault('cleanup', {})['stateRemoved'] = not root.exists()
    except Exception as exc:
        payload['status'] = 'FAIL'
        payload['error'] = str(exc)
    payload['totalSeconds'] = round(time.monotonic() - started, 3)
    if args.output:
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        # Audit already prints each scenario and its controls in human mode.
        passed = sum(r['status'] == 'PASS' for r in payload['results'])
        print(f"{payload['status']} | {passed}/{len(payload['results'])} PASS | {payload['totalSeconds']}s | cleanup={payload.get('cleanup', {})}")
        if payload.get('error'):
            print(payload['error'], file=sys.stderr)
    return int(payload['status'] != 'PASS')


if __name__ == '__main__':
    sys.exit(main())
