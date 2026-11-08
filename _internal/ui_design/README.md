# Shared design tokens

`tokens.json` is the implementation source for colors, radius, type scale, spacing, width classes, motion, easing,
reading surfaces and generated cover palettes. `scripts/gen_native_tokens.py` checks the specified values against `docs/DESIGN.md`.

`scripts/prepare_ui.py` generates Compose `Tokens.kt`, web token CSS/width classes and the token declarations in
`styles.css`, `motion.ts`, `cover.ts`; Qt's `gen_theme.py` reads the same JSON to generate `Theme.qml`.
Generated declarations stay in the actual stylesheet so the existing contrast and layout tests inspect shipped values.

Edit token values here and keep the checked DESIGN specification consistent. Component-specific geometry and values computed
from artwork or user settings remain at their use site.
