# Shared UI copy

Edit `vi.json`, then run the configured Python interpreter with `-X utf8 scripts/prepare_ui.py` from `_internal`.
The catalog generates Compose `S`, Android resources, web `S`, Qt JavaScript `S`, and Qt C++ strings.
Numbered slots (`{0}`, `{1}`) are values. They are never evaluated as code. Keep formatting and application data at the call site.

Reuse an existing key for identical copy. The generator rejects duplicate values and unknown keys.
Do not put book text, pronunciation tables, storage keys or protocol identifiers in this catalog.
Keys remain stable when wording changes; their suffix is an identifier, not an integrity checksum.

The build gate parses web sources with the pinned TypeScript compiler, and Compose/QML with the parity readers.
`exceptions.json` contains exact file/text exceptions with reasons. It has no directory-wide exclusions.
`qt_wording_review.json` explains the remaining heuristic candidates individually; a new unexplained candidate fails the build.
