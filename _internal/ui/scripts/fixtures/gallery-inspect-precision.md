gallery_inspect precision policy (uicheck139c)

Run from _internal/ui:

```
node scripts/gallery_inspect.mjs --out PATH --theme both
node scripts/gallery_inspect.mjs --out PATH --theme both --fail-on none
node scripts/gallery_inspect.mjs --out PATH --theme both --fail-on rule1,rule2,rule3
node scripts/gallery_inspect_precision_fixture.mjs --out PATH
node scripts/gallery_inspect_siblings_fixture.mjs --out PATH
npx vitest run --maxWorkers=2
npx tsc -p tsconfig.json --noEmit
```

The default gate uses SMALL TEXT, TOUCH TARGET, CONTRAST, SIBLING CONSISTENCY.
`--fail-on none` produces an advisory report. An explicit list replaces the defaults.
Exit 0 means the selected gate passed, 1 means selected findings exist, 2 means an
inspection/runtime failure. An empty default list is never inferred from missing data.

The review artifact is the scratchpad codex/uicheck139c/result.md, with reviewed JSON,
seeded per-rule samples, 4x crops, measurements, distinct groups, and limitations.
Only rules with positive gallery observations and reviewed sample precision >=90%
are enabled by default. Zero findings means precision is undefined, not 100%.
Re-audit the defaults after substantial UI, browser, font, or detector changes.

Precision changes are paired against actual layout in Chromium: suppression cases
must be silent and corresponding defects must still fire. The tests cover decorative
and hidden graphics, text font padding and fragmented labels, focus-only content,
truncation, effective font size, expanded hit regions, disabled contrast, icon roles,
centering, state variants, row origins, fractional residue and glyph identity.
The sibling fixture additionally proves the CSS VU overflow remains detected while
the CSS/SVG state glyph width comparison is silent. This narrows rule 9 to matching
glyph families; it does not claim detection of every optical imbalance.

Comparisons use a 1px threshold plus 0.01px numerical tolerance. Text alignment is
relative to row origin. Ink gap/width comparisons require matching glyph identity;
actual negative icon-to-label gaps are reported directly, even across different states.
Text nodes in one element are measured as one label. SVG ink still uses getBBox/CTM
and stroke expansion. General icon sizes are compared only for matching glyph roles.
Text collision first checks per-character ink bounds, then confirms at least 1 CSS
square pixel shared by two glyph masks at >=50% alpha, rasterized at 4x. Empty
glyph corners and subpixel antialias contacts are silent. The Be Vietnam Pro
paused-status/ETA fixture verifies this suppression and an actual shifted collision.

Crops are 4 output pixels per CSS pixel, compensating for the phone's 2x device scale.
Browser profiles are retained by inspector commands; inspection never deletes them.
Source file attribution is explicitly marked as an attribute, likely, or unknown.
Distinct groups retain all occurrence IDs and up to three examples for verification.
