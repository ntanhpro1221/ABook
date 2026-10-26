"""Hằng số token của giao diện native phải khớp docs/DESIGN.md (docs/NATIVE_PHONE_UI.md §2: một nguồn)."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "gen_native_tokens.py"


def _generator():
    spec = importlib.util.spec_from_file_location("gen_native_tokens", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tokens_kt_matches_design_md():
    gen = _generator()
    assert gen.OUT.read_bytes().decode("utf-8") == gen.render(), "Tokens.kt lệch DESIGN.md: chạy scripts/gen_native_tokens.py"


def test_tokens_kt_uses_lf():
    assert b"\r" not in _generator().OUT.read_bytes()


def test_generator_reads_every_palette_row():
    gen = _generator()
    light, dark = gen.colors(gen.DESIGN.read_text(encoding="utf-8"))
    assert set(light) == set(dark) == set(gen.COLOR_NAMES.values())
    assert light["BG"] == 0xFFF5F3EF and dark["BG"] == 0xFF121110
    assert dark["ACCENT_SOFT"] == 0x24E9A945  # rgb(233 169 69 / .14)
