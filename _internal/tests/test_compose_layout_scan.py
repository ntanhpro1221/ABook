"""Synthetic Kotlin snippets only; runtime geometry is covered by RevealLayoutTest."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("compose_layout_scan", ROOT / "scripts/compose_layout_scan.py")
scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scanner)


@pytest.mark.parametrize("name", ["Reveal", "ReducedFade", "AnimatedVisibility", "AnimatedContent", "SheetPages"])
@pytest.mark.parametrize("body", [
    "Text(\"One\"); Text(\"Two\")",
    "Spacer(Modifier.height(8.dp))\nText(\"Note\")",
    "for (item in items) Text(item)",
    "items.forEach { Text(it) }",
    "repeat(3) { Text(\"Item\") }",
    "item?.let { Text(it); Button({}) { Text(\"Done\") } }",
    "if (ready) { Text(\"One\"); Text(\"Two\") } else Text(\"Wait\")",
    "value -> when (value) {\n 1 -> { Text(\"One\"); Text(\"Two\") }\n else -> Text(\"Wait\")\n}",
    "\n value ->\n when (value) {\n 1 -> { Text(\"One\"); Text(\"Two\") }\n else -> Text(\"Wait\")\n}",
])
def test_rejects_multiple_roots_including_control_flow(name, body):
    assert scanner.scan(f"{name}(visible) {{ {body} }}") == [(1, name)]


@pytest.mark.parametrize("body", [
    "Column { Text(\"One\"); Text(\"Two\") }",
    "Row(verticalAlignment = Alignment.CenterVertically) { Spacer(Modifier.width(8.dp)); Text(\"Count\") }",
    "val row = item\nColumn { Text(row.title); Text(row.note) }",
    "snapshot -> if (snapshot) Text(\"On\") else Text(\"Off\")",
    "(kind, waiting) -> when {\n waiting -> Text(\"Wait\")\n else -> Column { Text(\"One\"); Text(\"Two\") }\n}",
    "CompositionLocalProvider(LocalValue provides true) { Column { Text(\"One\"); Text(\"Two\") } }",
    "item?.let { Column { Text(it); Text(\"Note\") } }",
    'Text("} Reveal(true) { Text(); Text() }") /* outer /* nested */ comment */',
])
def test_accepts_one_layout_or_one_root_per_branch(body):
    assert scanner.scan(f"Reveal(visible) {{ {body} }}") == []


def test_named_content_and_nested_animation_are_checked():
    assert scanner.scan('Reveal(true, content = { Text("One"); Text("Two") })')
    assert scanner.scan('Reveal(true) { Column { AnimatedVisibility(true) { Text("One"); Text("Two") } } }') == [(1, "AnimatedVisibility")]
    assert scanner.scan('// Reveal(true) { Text(); Text() }\nval example = "Reveal(true) { Text(); Text() }"') == []


def test_all_app_animation_content_has_explicit_flow():
    findings = scanner.scan_tree(ROOT / "mobile/android/app/src/main")
    assert not findings, "\n".join(findings)
