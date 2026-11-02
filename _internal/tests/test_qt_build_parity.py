"""The Qt build must run the Android–web hard rules too."""
import ast
import runpy
from pathlib import Path


def test_qt_build_includes_android_web_parity():
    root = Path(__file__).resolve().parents[1]
    runner = root / "desktop_qt/tools/qt_pytests.py"
    tree = ast.parse(runner.read_text(encoding="utf-8"))
    parity = next(ast.literal_eval(node.value) for node in tree.body
                  if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == "PARITY" for target in node.targets))
    assert "test_ui_parity.py" in parity
    assert str(root / "tests/test_ui_parity.py") in runpy.run_path(str(runner))["files"]()
    assert '"%HERE%tools\\qt_pytests.py"' in (root / "desktop_qt/build.bat").read_text(encoding="utf-8")
