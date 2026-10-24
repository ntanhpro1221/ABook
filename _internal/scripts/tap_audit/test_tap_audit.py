"""CPU-only checks; never launch a browser or the application server."""
import copy
import json
from pathlib import Path
import socket

import pytest

from ui_tap_audit import free_port, load_scenarios, result_status


def test_repository_scenarios():
    specs = load_scenarios(Path(__file__).with_name('scenarios.json'))
    assert len(specs) == 9
    assert any(s.get('viewport') == [1280, 900] for s in specs)
    assert any('{listen}' in s['path'] for s in specs)
    assert any('{studio}' in s['path'] for s in specs)


@pytest.mark.parametrize('mutation', ['empty', 'duplicate', 'steps', 'probe', 'viewport', 'route'])
def test_reject_invalid_scenarios(tmp_path, mutation):
    specs = load_scenarios(Path(__file__).with_name('scenarios.json'))
    if mutation == 'empty': specs = []
    elif mutation == 'duplicate': specs.append(copy.deepcopy(specs[0]))
    elif mutation == 'steps': specs[0]['steps'] = []
    elif mutation == 'probe': specs[0]['probe'] = {'exact': True}
    elif mutation == 'viewport': specs[0]['viewport'] = [True, 900]
    elif mutation == 'route': specs[0]['path'] = 'https://example.org'
    path = tmp_path / 'scenarios.json'
    path.write_text(json.dumps(specs), encoding='utf-8')
    with pytest.raises(ValueError): load_scenarios(path)


def test_free_port_can_be_bound():
    port = free_port()
    assert 0 < port < 65536
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', port))


def test_result_parser_fails_closed():
    good = {'status': 'PASS', 'checks': [{'pass_': True}],
            'elements': [{'status': 'PASS'}, {'status': 'SKIP_DISABLED'}]}
    assert result_status([good]) == 'PASS'
    for reports in ([], None, [{}], [dict(good, checks=[])],
                    [dict(good, checks=[{'pass_': False}])],
                    [dict(good, checks=[{'pass_': 'true'}])],
                    [dict(good, elements=[{'status': 'FAIL'}])],
                    [dict(good, status='FAIL')], [good, {}]):
        assert result_status(reports) == 'FAIL'
