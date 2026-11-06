"""Keep library-only startup independent of the Studio analysis module."""
import os
from pathlib import Path
import subprocess
import sys


def test_library_import_does_not_load_analysis_but_reading_still_can():
    internal = Path(__file__).resolve().parents[1]
    code = """
import sys
import abook.webui.server
from abook.webui.host import _studio_analysis_model
model = _studio_analysis_model()
assert 'abook.analysis' not in sys.modules
from abook.readaloud.vieneu import ordinal_one
from abook.readaloud.shouts import stretch_reading
assert ordinal_one(['Toán', 'I', 'rồi'], 1, 'I')
assert stretch_reading('rồiiii') == 'rồi… ì'
assert 'abook.analysis' in sys.modules
from abook.config import build_settings
assert model == build_settings()['analysis']['model']
print('startup imports and first text normalization passed')
"""
    env = dict(os.environ, PYTHONPATH=str(internal))
    result = subprocess.run([sys.executable, '-X', 'utf8', '-c', code], cwd=internal,
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'normalization passed' in result.stdout
