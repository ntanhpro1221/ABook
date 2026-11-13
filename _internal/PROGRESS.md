# TN fixes

## Setup
- Created `dev/tnfix` from `dev/integ168b` at `84b3cf29b` in the requested worktree.
- Read the approved TN audit, three owner rules, ASR warning about real Vietnamese words, and repository instructions.
- Scope: the nine approved classes; CPU only, no source-book edits, no push.
- Initial quality implementation SHA-256: `5cec934fcc5fd76da4125ad26cf6fa232d84c30cb832446ebe3684542b79d76b`.
- Private corpus outputs and baseline code snapshots stay outside the public repository.

## Numeric classes
- Added Vietnamese bare integer readings, terminal-dot grouped integers, short dot decimals and unambiguous comma thousands in Python/Kotlin.
- Added synthetic boundary/ownership tests and shared reading fixtures; refreshed number text and highlight spans in existing fixtures.
- Focused pytest: 303 collected cases passed, zero FAILED (`-rf`). Full TN/G2P/parity and corpus comparison remain pending.
