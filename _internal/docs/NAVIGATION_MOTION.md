# Navigation motion contract

The shell owns persistent playback/navigation chrome. A destination transition
only animates content. Library filters are adjacent pages, with one position
driving the content and indicator; incoming pages never wait for outgoing pages
to disappear. Cover geometry stays proportional throughout the transition.

## Android

- `ShellFrame`: ordinary destinations retain tabs and mini-player at the same
  baseline as the library. Destinations owning bottom actions smoothly hide shell
  chrome. Selecting a tab from a child returns to that tab's root.
- `ScreenStack`/`Motion.kt`: disjoint horizontal page rectangles for every
  destination. `NavState.progress` also drives predictive back, commit and cancel.
- Book entry/return: `SharedTransitionLayout` supplies the overlay; cover geometry
  uses the navigation clock, while other content fades through. This deliberately
  uses the caller-driven overlay rather than starting a second animation clock.
  The grid source remains painted. Resident filter pages can contain the same
  book, so source selection uses the visible instance, not layout callback order.
- `CoverLoader`/`BookCover`: reuse an adequate decoded bitmap across sizes. While
  a sharper decode is pending, retain the same artwork. Cache identities include
  path and stamp; source and destination never depend on an empty size-specific
  placeholder.
- Book detail loading starts at the tap and shares state with the destination.
  Late chapter rows fade over 150 ms. The page survives in the shell cache.
- Library: `HorizontalPager`, resident neighbouring pages, one count per selected
  result set, swipe and tab selection. Offscreen page semantics are cleared.
  Presence animations belong to additions/removals within one page, with fade and
  translation; filters never mix outgoing rows into an incoming page.
- `ShellFrame` only publishes insets in the actual measurement pass. Publishing
  lookahead and actual bar heights into the same state causes an idle/layout loop
  during an UndoBar reveal; the existing UndoBar tests exercise that boundary.

Applied through the exhaustive destination switch: Book; all Settings groups;
Devices Pair/Share/Storage; Voice Keys/Music; AddBook; ImportReview/ImportChapter;
EditBook/EditChapter; CropCover/CoverSearch; Export; Studio home/new/project and
every StudioSub kind (Precast, Script, Readings, Export, Activity, Cover).
The shell's root Library/Studio/Settings tabs use the same
chrome. Full-player and sheet transitions keep their existing owners.

Device selection is a cast icon beside play. Only a non-hidden remote device
with a book, chapter and `playing=true` creates the single-line <=36 dp strip.
The strip and icon open the existing OtherPlayersSheet. Full-player selection
remains available.

## Web and Qt audit

| Surface | Finding and change |
| --- | --- |
| Web route shell | Replaced exit-then-commit with a retained outgoing snapshot and immediate route commit. Both content rectangles translate on the same clock, clipped to prevent overlap with fixed chrome. Applies to every router destination. |
| Web library | Key presence by filter page (and the empty state), retain nodes for unchanged search membership, avoid height tween during page slides; swipe changes filter; counts follow the filtered set. |
| Web book cover | Keep the source until route replacement, uniform scale, portrait header cover matching the grid. Delayed destinations retain the flight image. |
| Web device controls | A single <=36 px remote strip opens controls. Cast selector exists for zero/one/many peers, including compact player. The icon opens selection instead of immediately transferring to the only peer. |
| Qt ScreenStack | Simultaneous page entry/return, no sequential sidebar gap. Cover overlay reuses source texture; source remains painted. Footer is outside ScreenStack. |
| Qt library | Capture old page pixels before changing data, move old/new pages simultaneously, fixed cover geometry, filtered count and horizontal drag. Empty states move with their page. |
| Qt Settings/Studio children | Common ContentSlide captures the outgoing view and immediately commits the incoming one; both use one clock, including reverse navigation and layout changes. |
| Qt device controls | This branch has no permanent remote-player row to remove. Direct cast icons on PlayerBar and MiniPlayer open its existing OutputPopover. |

Other Android AnimatedContent sites were reviewed: responsive layouts, action
labels, chapter/button labels, EditBook readings, CoverSearch, voice sample glyph,
Studio primary/work cards, confirmation pages and music states already enter and
exit concurrently. They retain their local owners. Music's horizontal expansion
was replaced with short translation/fade; the library sort menu now scales
uniformly. Radio marks, press feedback and full-player morphs already scale both
axes together. Vertical Reveal/Presence remains appropriate for adding/removing
rows; library filter pages do not run those animations against one another.

The source inventory (paths below are under Android `ui/`) is:

| Files | Result |
| --- | --- |
| `screens/LibraryScreen.kt`, `screens/LibraryUiState.kt` | Replaced the filter exit/swap/enter clock and per-tile height animation with adjacent pager pages. Within-page additions/removals still fade/translate concurrently. |
| `screens/LibraryChrome.kt`, `motion/BookCoverFlight.kt` | Corrected independent-axis scaling; sort menu and cover now use equal X/Y scale. |
| `music/MusicPanel.kt` | Removed horizontal expansion of cue actions. State/label AnimatedContent already enters/exits concurrently. |
| `screens/BookScreen.kt`, `screens/SettingsScreen.kt`, `motion/Motion.kt` | Responsive layouts already use simultaneous slide/fade; book data arrival now has a separate 150 ms fade. |
| `editbook/EditBookScreen.kt`, `editbook/CoverSearchScreen.kt` | Existing concurrent content swaps and vertical row presence; no exit-only page interval or width scaling. |
| `studio/StudioProjectScreen.kt`, `studio/WorkTab.kt` | Existing concurrent action/card replacements; route navigation is owned by ScreenStack. |
| `devices/StorageScreen.kt`, `devices/CompanionSurfaces.kt`, `addbook/AddBookScreen.kt` | Vertical row additions/removals with placement animation; no cross-filter row mixing. |
| `components/Confirm.kt`, `components/MovingTextAction.kt`, `components/ListParts.kt`, `voice/VoiceParts.kt`, `nowplaying/ReadAlongPane.kt` | Local confirmation/label/control presence already concurrent; no page sequencing or cover deformation. |
| `nowplaying/NowPlayingScreen.kt`, `nowplaying/PlayerVisuals.kt`, `nowplaying/NowPlayingWindow.kt`, `screens/SettingsVoice.kt` | Scale is uniform on both axes (window/cover/glyph/selection feedback). |
| `nowplaying/PlayerSheets.kt`, `components/Sheet.kt` | Read-only audit; the task explicitly reserves these files for phonefix. |

On web the page/filter owners are `shared/motion.ts` and
`shared/MotionRegion.tsx`; page slides now have simultaneous movement and fixed
content height. Local fade-through label/layout updates retain their own short
fade phases. `listen/LibraryScreen.tsx` isolates filter presence. On Qt the
exit-then-enter page owners were `ScreenStack.qml`, `LibraryScreen.qml`,
`SettingsScreen.qml` and `StudioScreen.qml`; all four were changed. The remaining
SequentialAnimation in LibraryScreen only pulses its loading skeleton and never
sequences a page replacement.

## Reusable recorded-pixel gate

Run `scripts/audit_navigation_frames.py manifest.json --output metrics.json`
with the production venv and `-X utf8`. Manifest coordinates are original video
pixels, and frame numbers are zero-based decoded frames. The decoder disables
ffmpeg frame synchronisation (`-vsync 0`) and verifies the count against showinfo
presentation timestamps; average FPS is not a frame-selection clock for Android
screenrecord's VFR output.

- `cover`: reference frame plus rect/rects, search rect, candidate widths and
  independent aspect probes. Optional vertical strips can track a partially
  clipped cover. Every matched cover contributes to the worst aspect error.
  Missing matches remain explicit, with unknown aspect; they never pass.
- `bar`: fixed-size template matching, missing-frame list and total y range.
- `grid`: per-frame coloured-artwork occupancy, including completely empty frames.
- `fade`: projection between recorded before/after pixels, optional translation
  alignment, per-frame alpha steps and fit residual. A threshold breach marks
  the precise pop frame.

The script writes per-frame JSON, summary booleans and an optional numbered
contact sheet. Its tests plant a blank grid, a one-frame pop, vertical footer
movement and independent width distortion, including a good cover beside a bad
one. Match coverage and fit residual must be reviewed along with a numeric pass.
Clipping at a page edge must not be described as a change to an image's aspect.
Choose correspondence thresholds from the actual artwork: similar gradient
strips can match the wrong book at low correlation. Review template identities
and use a detailed unoccluded patch when the system Back bubble covers a corner.

External API reference checked for overlay ownership:
[Android shared transition customisation](https://developer.android.com/develop/ui/compose/animation/shared-elements/customize).
