"""Verify a manually installed runtime before recording setup completion."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile


INTERNAL_ROOT = Path(__file__).resolve().parents[1]
# Select this checkout's contract even when the venv has another editable checkout.
sys.path.insert(0, str(INTERNAL_ROOT))
sys.dont_write_bytecode = True

from abook import runtime_contract  # noqa: E402


def checked_payload(runtime: Path) -> tuple[dict, list[str]]:
    """Run the runtime contract's prerequisites, excluding the marker being created."""
    expected_prefix = runtime / ".venv"
    if Path(sys.prefix).resolve() != expected_prefix.resolve():
        return {}, [f"interpreter: run with {expected_prefix / 'Scripts' / 'python.exe'} "
                    f"(current prefix: {sys.prefix})"]

    checks = {
        "perceptual_cache": runtime_contract.perceptual_cache_check(runtime),
        "voice_model": runtime_contract.voice_model_check(runtime),
        **{f"dependency:{name}": result for name, result in
           runtime_contract.critical_dependency_checks().items()},
    }
    errors = []
    for name, result in checks.items():
        print(f"[{'OK' if result['ok'] else 'FAIL'}] {name}: {result['detail']}")
        if not result["ok"]:
            errors.append(f"{name}: {result['detail']}")
    if errors:
        return {}, errors

    return {
        "schema_version": runtime_contract.SETUP_SCHEMA_VERSION,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "python": str(Path(sys.executable).resolve()),
        "internal_root": str(INTERNAL_ROOT),
        "perceptual_ready_marker": str(runtime / "models" / "utmosv2" /
                                       runtime_contract.PERCEPTUAL_CACHE_MARKER_FILENAME),
        "installed_by": "dev-check",
        "python_version": sys.version.split()[0],
        "components": runtime_contract.installed_dependency_provenance(),
        "checks": checks,
    }, []


def write_marker(marker: Path, payload: dict) -> None:
    """Publish atomically without truncating an existing marker on failure."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=marker.parent,
            prefix=marker.name + ".", suffix=".part", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, marker)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True, help="Runtime root containing .venv and models")
    parser.add_argument("--dry-run", action="store_true", help="Verify and print the proposed marker without writing")
    args = parser.parse_args(argv)
    runtime = args.runtime.expanduser().resolve()
    # Imports and cache checks stay offline; no model construction or inference.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HOME"] = str(runtime / "models" / "huggingface")
    os.environ["PYTORCH_NVML_BASED_CUDA_CHECK"] = "1"
    marker = runtime / ".setup_complete"
    try:
        payload, errors = checked_payload(runtime)
        if errors:
            for error in errors:
                print(f"[FAIL] {error}", file=sys.stderr)
            print("Runtime check failed; marker was not written.", file=sys.stderr)
            return 1
        if args.dry_run:
            print(f"DRY RUN: would write {marker}")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            write_marker(marker, payload)
            print(f"Wrote {marker}")
    except Exception as exc:  # Fail closed, including import, filesystem and metadata errors.
        print(f"[FAIL] {type(exc).__name__}: {exc}; marker was not written.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
