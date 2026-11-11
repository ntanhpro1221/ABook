"""What `TTSCoordinator` reads from the database it is given, derived from the source.

The coordinator is handed a full `ProjectDB` by the pipeline, but a read-only stand-in by the synthesis pool's workers
(`tts_pool.ReadOnlyVoiceDB`) and by the voice preview (`reading_preview.PreviewVoiceDB`). A read added to the coordinator, or
to a function it hands its database to (`studio_names.book_name_readings_for_project`), must exist on every stand-in: when
`list_characters` was missing, the preview answered 422 and a pool worker failed every line.

Nobody keeps that list by hand. `tts_database_surface()` walks `abook/tts.py` for every use of `self.db` and follows the
database into each function it is passed to. A use this walk cannot follow fails loudly, so the list is never a guess.
"""
from __future__ import annotations

import ast
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, Callable

PACKAGE = Path(__file__).resolve().parents[1] / "abook"


@lru_cache(maxsize=None)
def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _function(path: Path, name: str) -> ast.FunctionDef | None:
    return next((node for node in _tree(path).body if isinstance(node, ast.FunctionDef) and node.name == name), None)


def _imported_from(path: Path, name: str) -> tuple[Path, str] | None:
    """Where a name used in the module at `path` was imported from: (module file, name there). Relative imports only."""
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.ImportFrom) or not node.level:
            continue
        for alias in node.names:
            if (alias.asname or alias.name) != name:
                continue
            folder = path.parent
            for _ in range(node.level - 1):
                folder = folder.parent
            target = folder.joinpath(*(node.module or "").split("."))
            return target.with_suffix(".py"), alias.name
    return None


def _reads(scope: ast.AST, is_database: Callable[[ast.AST], bool], path: Path) -> set[str]:
    """Every attribute read from the database expression inside `scope`, following it into the functions it is passed to."""
    parents = {child: parent for parent in ast.walk(scope) for child in ast.iter_child_nodes(parent)}
    found: set[str] = set()
    for node in ast.walk(scope):
        if not is_database(node) or isinstance(getattr(node, "ctx", None), ast.Store):
            continue
        parent = parents[node]
        if isinstance(parent, ast.Attribute):
            found.add(parent.attr)
        elif isinstance(parent, ast.Call) and node in parent.args and isinstance(parent.func, ast.Name):
            position = parent.args.index(node)
            if parent.func.id == "getattr" and position == 0 and isinstance(parent.args[1], ast.Constant):
                found.add(str(parent.args[1].value))
            else:
                found |= _handed_to(path, parent.func.id, position)
        else:
            raise AssertionError(f"{path.name}:{node.lineno}: the database is used in a way this walk cannot follow")
    return found


def _handed_to(path: Path, name: str, position: int) -> set[str]:
    function = _function(path, name)
    if function is None:
        origin = _imported_from(path, name)
        if origin is None:
            raise AssertionError(f"{path.name}: the database is handed to `{name}`, which this walk cannot find")
        path, name = origin
        function = _function(path, name)
        if function is None:
            raise AssertionError(f"{path.name}: `{name}` is not a function of that module")
    parameter = function.args.args[position].arg
    return _reads(function, lambda node: isinstance(node, ast.Name) and node.id == parameter, path)


def _is_self_db(node: ast.AST) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "db"
            and isinstance(node.value, ast.Name) and node.value.id == "self")


@lru_cache(maxsize=1)
def tts_database_surface() -> frozenset[str]:
    """Names `TTSCoordinator` reads from its database: methods, and the `path` attribute beside which shared rulings live."""
    path = PACKAGE / "tts.py"
    coordinator = next(node for node in _tree(path).body if isinstance(node, ast.ClassDef) and node.name == "TTSCoordinator")
    return frozenset(_reads(coordinator, _is_self_db, path))


def missing_reads(database: Any) -> list[str]:
    """Reads of the coordinator that `database` (an object or a class) does not offer. `path` is set per instance."""
    names = tts_database_surface() - ({"path"} if isinstance(database, type) else set())
    return sorted(name for name in names if not hasattr(database, name))


def whole_database_only(init: Callable[..., None]) -> Callable[..., None]:
    """`TTSCoordinator.__init__` that refuses a database missing one of its reads (installed for every test by conftest).

    A test double with only the reads its author knew about passes until the coordinator learns a new read, then fails in a
    place that names neither the double nor the read. This names both, at the moment the double is handed over.
    """
    @wraps(init)
    def checked(self: Any, settings: Any, db: Any, *args: Any, **kwargs: Any) -> None:
        missing = missing_reads(db)
        assert not missing, (
            f"{type(db).__name__} is handed to TTSCoordinator as its database but lacks {missing}. "
            "Use a real ProjectDB (or tts_pool.ReadOnlyVoiceDB over one): a partial stand-in drops the book's own name readings."
        )
        init(self, settings, db, *args, **kwargs)

    checked.whole_database_only = True  # type: ignore[attr-defined]
    return checked
