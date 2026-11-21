"""CPU-only checks; never launch a browser or the application server."""
import copy
import asyncio
import json
from pathlib import Path
import socket

import pytest
import ui_tap_audit

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


@pytest.mark.parametrize('mutation', ['empty', 'duplicate', 'steps', 'probe', 'viewport', 'route', 'expect', 'touch', 'reopen', 'checked'])
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
    elif mutation == 'checked': specs[0]['steps'][0]['checked'] = 'true'
    path = tmp_path / 'scenarios.json'
    path.write_text(json.dumps(specs), encoding='utf-8')
    with pytest.raises(ValueError): load_scenarios(path)


def test_free_port_can_be_bound():
    port = free_port()
    assert 0 < port < 65536
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', port))


@pytest.mark.parametrize('initial,responds', [('true', 0), ('false', 0), ('false', 5), ('false', None), (None, 0)])
def test_checked_preparation_uses_coordinates_and_requires_the_result(monkeypatch, initial, responds):
    # responds = state reads after the tap before the saved state arrives (None: never).
    async def immediate(_seconds): pass
    monkeypatch.setattr(asyncio, 'sleep', immediate)
    monkeypatch.setattr(ui_tap_audit, 'READY_TIMEOUT', .05)

    class Switch(CDP):
        def __init__(self):
            super().__init__(None)
            self.state,self.points,self.pending=initial,[],None
        async def select(self, _spec):
            return dict(hit=True,blockedInLayer=[],disabled=False,x=30,y=40)
        async def evaluate(self, expression):
            if expression=='innerWidth<600': return False
            if self.pending is not None:
                if self.pending==0: self.state='true'
                self.pending-=1
            return self.state
        async def point(self, position, touch=False):
            self.points.append(position)
            if responds is not None: self.pending=responds
        async def settle(self):pass
    c=Switch()
    operation=c.step(dict(selector='[role=switch]',checked=True))
    if initial is None or responds is None:
        with pytest.raises(RuntimeError):asyncio.run(operation)
    else:
        asyncio.run(operation)
        assert len(c.points)==int(initial=='false')
        assert c.state=='true'


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
    monkeypatch.setattr(ui_tap_audit, 'READY_TIMEOUT', .01)

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
        assert c.reads >= 3


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


@pytest.mark.parametrize('settles', [True, False])
def test_moving_toast_cover_is_rechecked_until_its_close_button_is_reachable(monkeypatch, settles):
    """Toast đang trượt (✕ ngoài màn hình lúc máy bận) được chờ ổn định có hạn; không ổn định thì vẫn đỏ."""
    monkeypatch.setattr(ui_tap_audit, 'READY_TIMEOUT', .3)

    class FakeCDP(CDP):
        def __init__(self):
            super().__init__(None)
            self.points, self.settles = [], 0

        async def evaluate(self, expression):
            if expression == '!!tapAudit.top()': return False
            if expression == 'innerWidth<600': return False
            if expression.startswith('!!document.elementFromPoint'): return settles and self.settles >= 2
            return dict(hit=bool(self.points), hitToast=not self.points,
                        toastClose=dict(x=30, y=-15 if self.settles < 2 else 40), label='Thêm tuỳ chọn')

        async def point(self, p, touch=False): self.points.append((p, touch))
        async def settle(self): self.settles += 1

    c = FakeCDP()
    result = asyncio.run(c.select(dict(text='Thêm tuỳ chọn'), scroll=False))
    assert result['hit'] is settles
    assert len(c.points) == (1 if settles else 0)
    assert c.settles >= 2


@pytest.mark.parametrize('baseline_healthy,inspection_raises', [(True, False), (False, False), (True, True)])
def test_negative_control_requires_healthy_baseline_and_always_restores(baseline_healthy, inspection_raises):
    class Fault(CDP):
        injected = False
        injection_count = 0
        restored = False

        def sample(self):
            blocked = self.injected or not baseline_healthy
            return dict(label='Read', tag='BUTTON', hit=not blocked, disabled=False,
                        blockedInLayer=['BUTTON'] if blocked else [],
                        pointerEvents='none' if blocked else 'auto')

        async def evaluate(self, expression):
            if "window.__tapOriginalPointer=" in expression:
                self.injected = True
                self.injection_count += 1
                return True
            if 'const [value,priority]' in expression:
                self.injected = False
                self.restored = True
                return True
            if self.injected and inspection_raises:
                raise RuntimeError('CDP inspection failed')
            return [self.sample()]

        async def select(self, _spec, within=False, scroll=True):
            assert within
            if self.injected: assert not scroll
            return self.sample()

        async def point(self, *_args, **_kwargs):
            pytest.fail('negative control must not activate deliberately broken UI')

    c, report, checks = Fault(None), {}, []
    operation = c.negative_control(dict(probe=dict(text='Read')), report,
                                   lambda name, ok, **_: checks.append((name, ok)))
    if not baseline_healthy or inspection_raises:
        with pytest.raises(RuntimeError): asyncio.run(operation)
    else:
        asyncio.run(operation)
        evidence = report['negativeControl']
        assert evidence['baseline']['healthy'] is True
        assert evidence['restored']['healthy'] is True
        assert set(evidence['detected']) == {'mouse', 'touch'}
        assert [name for name, ok in checks if not ok] == [
            'mouse probe center reaches control', 'touch probe center reaches control']
    assert c.injection_count == int(baseline_healthy)
    assert not c.injected
    assert c.restored is baseline_healthy


def test_settle_propagates_timeout_instead_of_treating_it_as_ready():
    class Timeout(CDP):
        async def evaluate(self, expression):
            # The browser deadline is the same load-scaled READY_TIMEOUT as every other wait.
            assert expression == f'(globalThis.__tapSettleMs={round(ui_tap_audit.READY_TIMEOUT*1000)},{ui_tap_audit.SETTLE_JS})'
            raise RuntimeError('UI motion/geometry did not settle within 75s')

    with pytest.raises(RuntimeError, match='did not settle'):
        asyncio.run(Timeout(None).settle())


def test_navigation_waits_for_mount_and_context_replacement(monkeypatch):
    async def immediate(_seconds): pass
    monkeypatch.setattr(asyncio, 'sleep', immediate)

    class Navigation(CDP):
        reads = 0

        async def call(self, method, **params):
            assert method == 'Page.navigate'
            assert params['url'] == 'http://localhost/#/book/fixture'

        async def evaluate(self, expression):
            assert "document.readyState==='complete'" in expression
            self.reads += 1
            if self.reads == 1: raise RuntimeError('Execution context was destroyed')
            return self.reads >= 4

    c = Navigation(None)
    asyncio.run(c.navigate('http://localhost/#/book/fixture'))
    assert c.reads == 4


def test_profile_removal_waits_for_released_handles_and_fails_closed(monkeypatch, tmp_path):
    """Busy machine: Edge children hold profile files after the root exits (WinError 32)."""
    profile = tmp_path / 'profile'
    profile.mkdir()
    calls = []
    real = ui_tap_audit.shutil.rmtree

    def flaky(path):
        calls.append(path)
        if len(calls) < 4: raise PermissionError(32, 'in use')
        real(path)
    monkeypatch.setattr(ui_tap_audit.shutil, 'rmtree', flaky)
    asyncio.run(ui_tap_audit.remove_profile(profile, timeout=5))
    assert not profile.exists() and len(calls) == 4

    profile.mkdir()
    monkeypatch.setattr(ui_tap_audit.shutil, 'rmtree', lambda path: (_ for _ in ()).throw(PermissionError(32, 'in use')))
    with pytest.raises(PermissionError):
        asyncio.run(ui_tap_audit.remove_profile(profile, timeout=.3))


def test_edge_tree_wait_reports_survivors():
    import subprocess
    import sys
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    tree = ui_tap_audit.edge_tree(child.pid)
    try:
        # A venv launcher re-spawns the interpreter: the tree is root + descendants.
        assert tree and tree[0].pid == child.pid
        assert {p.pid for p in ui_tap_audit.wait_tree_exit(tree, .1)} == {p.pid for p in tree}
    finally:
        for p in reversed(tree):
            try: p.kill()
            except Exception: pass
        child.wait()
    assert ui_tap_audit.wait_tree_exit(tree, 10) == []
    assert ui_tap_audit.wait_tree_exit([], 1) == []


@pytest.mark.parametrize('opens,stays_expanded,error', [
    (True, True, None),
    (False, True, 'no layer opened'),
    (True, False, 'also acted inside the layer'),
])
def test_popup_trigger_must_open_its_layer_and_only_open_it(monkeypatch, opens, stays_expanded, error):
    """Cú chạm mở phải mở lớp nổi trong hạn, và không chọn luôn thứ nằm dưới ngón tay trong lớp vừa mở."""
    monkeypatch.setattr(ui_tap_audit, 'READY_TIMEOUT', .2)

    class FakeCDP(CDP):
        def __init__(self):
            super().__init__(None)
            self.points = []

        async def select(self, spec, within=False, scroll=True):
            return dict(hit=True, blockedInLayer=[], disabled=False, x=1, y=2, label='Thêm tuỳ chọn')

        async def evaluate(self, expression):
            if 'hasAttribute("aria-haspopup")' in expression: return True
            if expression.startswith('(') and 'TRACE' not in expression and '__stepTrace=[]' in expression: return True
            if expression == 'innerWidth<600': return True
            if expression == '!!tapAudit.top()': return opens
            if 'getAttribute("aria-expanded")!=="true")(window.__stepTrigger)' in expression: return not stays_expanded
            if expression.startswith('({trace'): return {'trace': []}
            return True

        async def point(self, p, touch=False): self.points.append(p)
        async def settle(self): pass

    c = FakeCDP()
    if error:
        with pytest.raises(RuntimeError, match=error):
            asyncio.run(c.step(dict(text='Thêm tuỳ chọn', exact=True)))
    else:
        asyncio.run(c.step(dict(text='Thêm tuỳ chọn', exact=True)))
    assert len(c.points) == 1


@pytest.mark.parametrize('toast_press,retry_opens', [(True, True), (True, False), (False, True)])
def test_press_taken_by_a_moving_page_toast_is_retapped_once(monkeypatch, toast_press, retry_opens):
    """Toast trang trượt tới dưới ngón sau khi đã kiểm hit: chạm lại MỘT lần; chạm trượt vì lý do khác vẫn đỏ."""
    monkeypatch.setattr(ui_tap_audit, 'READY_TIMEOUT', .2)

    class FakeCDP(CDP):
        def __init__(self):
            super().__init__(None)
            self.points = []

        async def select(self, spec, within=False, scroll=True):
            return dict(hit=True, blockedInLayer=[], disabled=False, x=1, y=2, label='Tốc độ')

        async def evaluate(self, expression):
            if 'hasAttribute("aria-haspopup")' in expression: return True
            if expression == 'innerWidth<600': return True
            if expression == '!!tapAudit.top()': return len(self.points) > 1 and retry_opens
            if expression == 'window.__stepTrace': return [[12, 'pointerdown', 'SPAN', True, toast_press]]
            if 'getAttribute("aria-expanded")!=="true")(window.__stepTrigger)' in expression: return False
            if expression.startswith('({trace'): return {'trace': []}
            return True

        async def point(self, p, touch=False): self.points.append(p)
        async def settle(self): pass

    c = FakeCDP()
    if toast_press and retry_opens:
        asyncio.run(c.step(dict(text='Tốc độ')))
        assert len(c.points) == 2 and len(c.toast_dismissals) == 1
    else:
        with pytest.raises(RuntimeError, match='no layer opened'):
            asyncio.run(c.step(dict(text='Tốc độ')))
        assert len(c.points) == (2 if toast_press else 1)


def test_every_harness_deadline_scales_with_machine_load():
    """Hạn chờ chỉ chặn lỗi treo; máy bận (Unity của chủ sách, tải giả) chỉ làm lần HỎNG chậm hơn - cùng hệ số với tests/timing.py."""
    import importlib
    import os
    old = os.environ.get('ABOOK_TEST_TIME_SCALE')
    try:
        os.environ['ABOOK_TEST_TIME_SCALE'] = '4'
        scaled = importlib.reload(ui_tap_audit)
        assert scaled.TIME_SCALE == 4 and scaled.READY_TIMEOUT == 60 and scaled.EXIT_TIMEOUT == 240
        source = Path(scaled.__file__).read_text(encoding='utf-8') + (Path(scaled.__file__).parent / 'run.py').read_text(encoding='utf-8')
        import re
        # No literal wall-clock bound bypasses the factor (sleeps are polling cadence, not deadlines).
        assert not re.search(r'wait_for\([^)]*,\s*\d+\)|timeout=\d+\)|range\(100\)|monotonic\(\) \+ \d+\b(?! \*)', source)
    finally:
        if old is None: os.environ.pop('ABOOK_TEST_TIME_SCALE', None)
        else: os.environ['ABOOK_TEST_TIME_SCALE'] = old
        importlib.reload(ui_tap_audit)
