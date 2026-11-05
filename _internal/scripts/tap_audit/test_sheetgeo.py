"""Real Edge integration wrapper, including the negative control; no models/GPU."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from run_sheetgeo import find_edge


@pytest.fixture(scope='module')
def edge():
    try:
        return find_edge()
    except FileNotFoundError as exc:
        pytest.skip(str(exc))


@pytest.mark.parametrize('injected', [False, True], ids=['real-app', 'push-content-fault'])
def test_real_player_geometry(edge, injected):
    root = Path(__file__).resolve().parents[3]
    output = root / ('sheetgeo-pytest-fault.json' if injected else 'sheetgeo-pytest.json')
    command = [sys.executable, '-X', 'utf8', str(Path(__file__).with_name('run_sheetgeo.py')),
               '--edge', edge, '--output', str(output)]
    if injected:
        command.extend(['--no-build', '--inject-fault'])
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=900)
    assert completed.returncode == int(injected), completed.stdout + completed.stderr
    report = json.loads(output.read_text(encoding='utf-8'))
    assert report['status'] == ('FAIL' if injected else 'PASS'), completed.stdout
    assert report['allWidthClassesCovered']
    assert report['cleanup']['profileRemoved']
    assert report['cleanup']['serverClosed']
    assert len(report['results']) == 6
    assert all(r['trials'] and all(c['pass'] for c in r['checks']) for r in report['results']), completed.stdout
    for result in report['results']:
        for check in result['checks']:
            if 'layout' not in check:
                continue
            layout = check['layout']
            if result['contentWidth'] < check['largeFrom']:
                assert abs(layout['columnMarginBox']['width'] - result['contentWidth']) <= 0.5
            else:
                assert abs(layout['panel']['x'] - layout['column']['right']) <= 0.5
    if injected:
        # An execution error cannot stand in for a detected geometry regression.
        for result in report['results']:
            assert any(c['name'] == 'header/text/controls invariant on every frame' and not c['pass']
                       for trial in result['trials'] for c in trial['checks']), completed.stdout
