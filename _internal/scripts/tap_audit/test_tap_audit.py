"""CPU-only checks; never launch a browser or the application server."""
import copy
import asyncio
import json
from pathlib import Path
import socket

import pytest

from ui_tap_audit import CDP, free_port, load_scenarios, result_status


@pytest.mark.parametrize('appears', [True, False])
def test_toast_wait_requires_a_real_mounted_toast(monkeypatch, appears):
    class FakeCDP(CDP):
        calls = 0

        async def evaluate(self, expression):
            assert 'data-sonner-toast' in expression and 'data-mounted' in expression
            self.calls += 1
            return appears and self.calls >= 2

    async def no_sleep(_seconds):
        pass

    monkeypatch.setattr(asyncio, 'sleep', no_sleep)
    c = FakeCDP(None)
    assert asyncio.run(c.wait_toast(timeout=.01)) is appears
    assert c.calls >= 2


def test_toast_event_is_retried_until_the_new_shell_listener_is_ready(monkeypatch):
    class FakeCDP(CDP):
        publications = 0

        async def evaluate(self, expression):
            if 'dispatchEvent' in expression:
                self.publications += 1
                return True
            return self.publications >= 2

    async def no_sleep(_seconds):
        pass

    monkeypatch.setattr(asyncio, 'sleep', no_sleep)
    c = FakeCDP(None)
    assert asyncio.run(c.wait_toast(publish=True))
    assert c.publications == 2


def test_repository_scenarios():
    specs = load_scenarios(Path(__file__).with_name('scenarios.json'))
    assert len(specs) == 21
    assert any(s.get('viewport') == [1280, 900] for s in specs)
    assert any('{listen}' in s['path'] for s in specs)
    assert any('{studio}' in s['path'] for s in specs)
    assert any('{profiles}' in s['path'] for s in specs)
    for name in ('Speed', 'Sleep timer', 'Voice', 'Background music'):
        for platform in ('mobile', 'desktop'):
            scenario = next(s for s in specs if s['name'] == f'Player {platform} - {name}')
            assert scenario['probe']['expect']
    assert any(s['name'] == 'Player mobile - Chapters' for s in specs)


@pytest.mark.parametrize('mutation', ['empty', 'duplicate', 'steps', 'probe', 'viewport', 'route', 'expect', 'touch', 'reopen'])
def test_reject_invalid_scenarios(tmp_path, mutation):
    specs = load_scenarios(Path(__file__).with_name('scenarios.json'))
    if mutation == 'empty': specs = []
    elif mutation == 'duplicate': specs.append(copy.deepcopy(specs[0]))
    elif mutation == 'steps': specs[0]['steps'] = []
    elif mutation == 'probe': specs[0]['probe'] = {'exact': True}
    elif mutation == 'viewport': specs[0]['viewport'] = [True, 900]
    elif mutation == 'route': specs[0]['path'] = 'https://example.org'
    elif mutation == 'expect': specs[0]['probe']['expect'] = True
    elif mutation == 'touch': specs[0]['touchProbe'] = {'exact': True}
    elif mutation == 'reopen': specs[0]['reopenSteps'] = []
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


@pytest.mark.parametrize('opens', [False, True])
def test_reopened_layer_waits_for_a_live_surface_and_missing_surface_stays_red(monkeypatch, opens):
    async def immediate(_seconds): pass
    monkeypatch.setattr(asyncio, 'sleep', immediate)

    class PendingLayer(CDP):
        def __init__(self):
            super().__init__(None)
            self.reads = 0

        async def evaluate(self, _expression):
            self.reads += 1
            return dict(role='dialog', title='Speed', body='none') if opens and self.reads >= 3 else None

    c = PendingLayer()
    if opens:
        assert asyncio.run(c.capture_layer())['role'] == 'dialog'
        assert c.reads == 3
    else:
        with pytest.raises(RuntimeError, match='layer did not open'):
            asyncio.run(c.capture_layer())
        assert c.reads == 30


@pytest.mark.parametrize('layer_open', [False, True])
def test_toast_cover_is_dismissed_only_on_page(layer_open):
    """Không che giấu lỗi toast chồng lên bảng; trang thường đóng bằng toạ độ thật."""
    class FakeCDP(CDP):
        def __init__(self):
            super().__init__(None)
            self.points = []

        async def evaluate(self, expression):
            if expression == '!!tapAudit.top()': return layer_open
            if expression == 'innerWidth<600': return True
            if expression.startswith('!!document.elementFromPoint'): return True
            return dict(hit=bool(self.points), hitToast=not self.points,
                        toastClose=dict(x=30, y=40), label='Nền')

        async def point(self, p, touch=False): self.points.append((p, touch))
        async def settle(self): pass

    c = FakeCDP()
    result = asyncio.run(c.select(dict(text='Nền'), scroll=False))
    assert result['hit'] is (not layer_open)
    assert c.points == ([] if layer_open else [(dict(x=30, y=40), True)])
    assert len(c.toast_dismissals) == (0 if layer_open else 1)
