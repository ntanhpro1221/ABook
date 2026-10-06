"""A release whose only files are wheels for other interpreters cannot be installed, so it is not an update."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check_dependency_updates as checker  # noqa: E402


def test_old_interpreter_wheels_without_an_sdist_are_not_installable():
    files = [{"filename": "pkg-1.0-cp36-cp36m-win_amd64.whl"}, {"filename": "pkg-1.0-cp37-cp37m-win32.whl"}]
    assert not checker._supports_running_python(files)


def test_a_pure_python_wheel_or_an_sdist_is_installable():
    assert checker._supports_running_python([{"filename": "pkg-1.0-py3-none-any.whl"}])
    assert checker._supports_running_python([{"filename": "pkg-1.0.tar.gz"}])


def test_a_fitting_wheel_still_obeys_requires_python():
    files = [{"filename": "pkg-1.0-py3-none-any.whl", "requires_python": ">=99"}]
    assert not checker._supports_running_python(files)


def test_a_release_with_every_file_yanked_is_not_installable():
    assert not checker._supports_running_python([{"filename": "pkg-1.0.tar.gz", "yanked": True}])
