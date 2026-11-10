"""Reject local decimal renderers: visible numbers use each platform's UiNumber helper."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HELPERS = {"ui/src/shared/number.ts", "desktop_qt/qml/UiNumber.js", "mobile/android/app/src/main/java/vn/abook/player/UiNumber.kt"}


def violations(source: str) -> list[int]:
    patterns = (r"\.toFixed\s*\(", r"%\.\d+f", r"\.toPlainString\s*\(",
                r"\b(?:value|rate|leading|pitch|balance|decibels|megabytes)\.toString\s*\(",
                r"\.replace\(\s*['\"]\.['\"]\s*,\s*['\"],['\"]\s*\)")
    return sorted({source.count("\n", 0, match.start()) + 1 for pattern in patterns for match in re.finditer(pattern, source)})


def findings():
    paths = list((ROOT / "ui/src").rglob("*.ts")) + list((ROOT / "ui/src").rglob("*.tsx"))
    paths += list((ROOT / "desktop_qt/qml").glob("*.qml")) + list((ROOT / "desktop_qt/qml").glob("*.js"))
    paths += list((ROOT / "mobile/android/app/src/main/java/vn/abook/player/ui").rglob("*.kt"))
    for path in paths:
        name = path.relative_to(ROOT).as_posix()
        if name in HELPERS or ".test." in name or path.name in {"UiStrings.kt", "strings.generated.ts", "UiStrings.js"}:
            continue
        source = path.read_text(encoding="utf-8")
        # A generic Choice key is persisted identity, not the visible label.
        source = re.sub(r"override val key[^\n]+", "", source)
        for line in violations(source):
            yield f"{name}:{line}: visible decimals must use UiNumber/formatDecimal"


def main():
    found = list(findings())
    print("\n".join(found)) if found else None
    print(f"UI decimal source audit: {len(found)} violations")
    return bool(found)


if __name__ == "__main__":
    raise SystemExit(main())
