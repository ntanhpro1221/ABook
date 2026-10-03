# Listen to any book (design, Lead 03-10, not built yet)

Owner request 03-10: a user without an `.abook` drops in an EPUB, a Word file, a PDF or a folder of `.txt` chapters and
listens right away. "Listen now" is plain read-aloud - a machine voice reads the text as written, like Edge's Read Aloud. No
analysis, no casting, no per-character voices (owner: a rushed analysis gives a patchy result; per-character voices stay a
Studio product). Background music can play along.

## 1. The book is layered; every layer but text is optional

`.abook` stops meaning "a finished audiobook". It is a book that can sit at any stage, chapter by chapter:

| Stage | The package holds | Listening |
|---|---|---|
| 0 text | chapter titles + text (`texts/<n>.txt`) | read aloud by a machine voice |
| 1 analysed | + `scripts/<n>.json` without time spans (speaker, kind, emotion, scene) | read aloud; music can follow scenes |
| 2 cast | + `cast.json` | Studio can produce it; read-aloud still one voice |
| 3 voiced | + chapter audio, `quality: "quick"` (read-aloud cache) or `"produced"` | plays the audio |
| 4 produced | audio made and checked by the Studio pipeline (`quality: "produced"`) | as today's audiobooks |

- `book.json` gains `chapters[i].state` (`text` / `analysed` / `cast` / `quick` / `produced`) and `chapters[i].text`
  (entry name). Audio entries become optional; a chapter without audio has no duration.
- Quick audio (read-aloud cache) is never mixed up with produced audio: a separate folder (`quick/<n>.<ext>`), its own
  `quality` and the voice/engine that made it, so a reader can drop or regenerate it and a Studio never mistakes it for
  checked output.
- The edit layer (`edits.json`: title, cover, names, music pins, wishes) applies at every stage unchanged.
- `.abookproj` stays "book + workshop" (P3); a stage-0 book can become a project ("Dựng xưởng") like any `.abook`.
- New format version; no backward compatibility needed (owner rule).

### What was built (layered book, stage 0 "text" + the import entry, 03-10)

- **Format version 5** (`ABOOK_FILE_FORMAT.md`): `texts/<id>.txt` entries; `chapters[i].state` = `"text"` and `chapters[i].text`; a chapter without audio has no
  `file`, `script` or duration (`duration 0`, `available false`); a file may have no audio chapter at all (`complete` false, Readium `readingOrder` empty,
  no `cast.json`). Only stage 0 is written; `analysed` / `cast` / `quick` / `produced` and the `quick/` folder are still design. Python `bookfile.py`
  (`seal` - formerly `_seal` - accepts texts instead of audio; `listening_layer` adds the chapters' source texts when a Studio project has no audio yet;
  `package_version` / `layer_version` give 5 for texts), Kotlin `BookFileImport.kt` / `BookDocumentWriter.kt` (`seal` shared by "Lưu thành .abook" and
  `TextBook`). Entry order: `texts/` after `scripts/`.
- **P3 blockers fixed** (docs/EDITING.md "Limits"): a book with no audio is identified by the SHA-256 of its chapter texts
  (`fingerprints.identity_prints` / `BookFileImport.identityPrints`, feeding the same `content_key` formula; `Store.findByChapters` and
  `packages.import_opened` match text books by the WHOLE set of texts, not by one shared chapter); `bookfile.seal` and `BookDocumentWriter.seal` accept
  no-audio books; `bookfile.listening_layer` / `projectfile._listening_book` produce a `book.json` for a Studio project that has sources but no audio
  yet. `workshop._sources` now copies `texts/<n>.txt` for a text book (nothing is rebuilt from scripts).
- **One text per chapter = the file Studio would read** (`ImportedBook.chapter_source` / `BookImport.chapterSource`): title + blank line + text for
  EPUB / DOCX / PDF, the file verbatim for TXT. The Studio chapter folder (`importers.extract`) and the text book use the same function, so
  "Làm sách nói từ cuốn này" (`POST /api/books/<id>/workshop`, `workshop.build`, desktop with Studio only) writes exactly the chapters Studio would have got from
  the original file.
- **Import into the library**: desktop `textbook.py` (`preview`, `build`, `add_to_library` = build a stage-0 `.abook` in a temp folder, then the normal
  `packages.import_file`, so verification, dedupe and edits are the ones of every book file) behind `POST /api/listen/import/preview` and
  `POST /api/listen/import`; reading text is `GET /api/listen/books/<id>/chapters/<n>/text` (also open to paired listen-only devices). Phone:
  `TextBook.kt` + `TextImports.kt` behind `EbookLibrary.pickSource / previewImport / createImport / discardImport` (system picker → copy into
  `library/imports/<ref>/` → `BookImport` rules → `BookDocumentWriter.seal` → `BookFileImport`). Both write the SAME `book.json` and hashes on
  `tests/fixtures/text_books/` (`tests/text_book_fixtures.py`, `TextBookTest.kt`; `python_text.abook` is read by Kotlin, `kotlin_text.abook` by Python).
- **PDF on the phone, the bridge**: Kotlin copies the PDF to the app folder, the WebView reads that copy with pdf.js (`ui/src/shared/pdfPages.ts` via
  `android/textImport.ts`) and hands the pages' lines to `previewImport({ref, pages, title, author})`, which runs `BookImport.fromPdfPages`. Pages travel
  over the Capacitor bridge as JSON (a 500-page text PDF is about 1-2 MB).
- **UI**: `listen/AddBook.tsx` ("Thêm sách từ file…": choose → chapter list (`shared/ChapterPreview.tsx`, the Studio list's row layout) + suggestions never applied →
  add; shared by desktop and phone through `ListenSource.textImport`); the library card says "Chỉ có chữ" and opens the reader; the book page and
  `ReaderScreen` show "Chưa có âm thanh" and no playback controls for a text chapter, and no per-line editing; the reader builds paragraphs from the text
  (`listen/textScript.ts`, one implementation for both platforms - no fake script on the server). Characters, music and "đánh dấu đã nghe" are hidden for a
  text-only book; title, cover and chapter names are editable and saved like any imported book.
- **Not built**: dropping a file onto the window (only the "Thêm sách từ file…" button and the pasted path); a Studio-style per-chapter delete before adding;
  accepting a suggestion (credit line) - suggestions are only shown; reading-position bar for text books on the library card; OCR for scanned PDFs.

## 2. Importers (shared by Studio and Listen now)

One function `import_text(path) -> {title, author?, cover?, chapters: [{title, text}]}`, Python + Kotlin with shared fixtures:

| Input | How | Risk |
|---|---|---|
| folder of `.txt` | file order = chapter order (what Studio takes today) | encoding: detect UTF-8 / UTF-16 / cp1258 |
| EPUB | spine order + nav/NCX titles, XHTML to text, cover from the manifest | low |
| DOCX | split on Heading 1/2 (fallback: "Chương N" lines) | medium |
| PDF (text) | text layer; strip running headers/footers and page numbers, join hyphenated lines, split on chapter headings | medium-high |
| PDF (scanned) | needs OCR - out of scope at first; say so | - |

Text is never auto-edited (owner rule): cleanup proposals (e.g. a credit line) are suggestions the user accepts.

### What was built (Importers, 03-10)

- `abook/importers.py`: `import_text(path) -> ImportedBook{title, author, language, cover_bytes, chapters[{title, text}], notes}` for a
  folder of `.txt` (Studio's order and `decode_text_bytes`: UTF-8 with/without BOM, UTF-16, cp1258, cp1252), EPUB (spine order, nav/NCX titles,
  cover from the manifest, image-only pages noted), DOCX (Heading 1/2, fallback `Chương|Chapter|Hồi|Quyển N` lines) and text-layer PDF.
  EPUB/DOCX use only `zipfile` + `xml.etree`/`html.parser`; PDF uses `pypdf` 6.16.2 (BSD-3, pure Python), vendored unchanged in
  `abook/vendor/pypdf/` (LICENSE + wheel SHA-256 in its README; `pyproject.toml` is hash-locked so nothing is declared there). A PDF with no text
  layer fails with "PDF scan, cần OCR". `epub_import.py` moved into it; `extract()` writes the Studio chapter folder (+ `import.json`, cover).
- One spec, three places: the **rules** (heading regex, running header/footer removal = lines in the first/last 2 of a page whose digits-normalised
  text repeats on >= 40% of >= 3 pages or that are a bare page number; paragraph joining = a sentence-final line shorter than 75% of the
  90th-percentile line length, or a next line opening with a dash/quote, ends a paragraph; `xyz-` + lowercase joins without a space and keeps
  the hyphen because Vietnamese hyphens belong to the word ("Mát-xcơ-va"), only U+00AD is dropped; split on heading lines, text before the first
  one is "Mở đầu") live in Python (`importers.py`) and Kotlin (`BookImport.kt`) and are replayed on `tests/fixtures/import/` (made by
  `tests/import_fixtures.py`: EPUB 2/3, DOCX with/without headings, PDF, scanned PDF, TXT folder in four encodings, own text only).
  Golden JSON is byte-identical in both languages. Credit lines are never removed: they appear in `notes` as suggestions.
- Phone PDF: **pdf.js** (`pdfjs-dist` legacy build, Apache-2.0) in the WebView, lazy-loaded. It only extracts lines per page
  (`ui/src/shared/pdfPages.ts`, same `pages/story.pages.json` as pypdf on the fixture); the rules above run in Kotlin (`BookImport.fromPdfPages`).
  Measured: debug APK 9,480,805 -> 10,216,254 bytes (+735 KB, +7.8%; the chunk is 488 KB + worker 1,317 KB raw, ~540 KB gzip), the main
  JS bundle is unchanged. PdfBox-Android was the alternative (Apache-2.0, 3.25 MB aar, JVM-heavy); not chosen. The desktop UI does not need the
  TS extractor (Studio runs the Python importer), though the same module would work in its webview.
- Wired (03-10, section 1 "What was built"): the phone's "Thêm sách từ file…" runs `BookImport` + `readPdfPages` and creates a stage-0 book. Studio: the new-book
  flow, remote upload and the Tauri file dialog accept `.epub/.docx/.pdf/.txt` and a folder; the chapter list shows title, words and characters.

## 3. Voices for Listen now

| Voice | Download | Network | Notes |
|---|---|---|---|
| Edge TTS | none | yes | default (owner 03-10). Microsoft neural vi-VN voices (HoaiMy, NamMinh) through Edge's read-aloud service; offline or failing -> that paragraph falls back to the device voice without stopping |
| the device's own TTS | none | no | offline voice. Android `TextToSpeech` (Google vi-VN); Windows OneCore (vi-VN voice "An" needs the Vietnamese speech pack) |
| VieNeu module | yes | no | best quality, several voices; a module like "Phân tích nhạc" (versioned pins, download on tap) |

Online voices (owner 03-10: "đọc ngay, cần mạng" is its own group; Edge TTS is what the owner already uses):
- Edge TTS is the online default (no key).
- "Bring your own key" providers, the user's key only (we never pay or sign anyone up):
  - Azure Speech, first in the list: the official home of the same voices as Edge, so it is the natural fallback if Edge's endpoint closes.
  - Google Cloud TTS: vi-VN Standard/WaveNet/Neural2.
  - FPT.AI: 100k chars/month free, 7 regional voices.
  - Viettel AI: 50k chars in the first month.
- Google Translate's read-aloud is a last resort only: unofficial, ~200 chars per call, robotic.
- Every provider is a separate adapter behind one interface (`speak(text, voice) -> audio`, `voices()`, `limits`). A failure or an exhausted quota falls back to the device voice without stopping playback.
- The UI says plainly that an online voice sends the book's text to that provider.

VieNeu 3.8.1 (installed) has CPU modes: `v3nano` (48M-parameter flow model, ONNX, 24 kHz) and `v3turbo` (ONNX on CPU,
48 kHz). Measured 03-10 on the home laptop CPU (busy with GPU evals): v3nano RTF 0.18, first audio after 0.76 s.
v3turbo (ONNX on CPU, 48 kHz, 25 voices): RTF 0.36 (~2.8x faster than listening), first streamed audio after 0.21 s; first load downloads the model (~20 min here). ONNX means the same runtime as the music module, so a phone build is plausible; phone speed not
measured yet.

VieNeu module = user choice with a recommendation (owner 03-10: "sao không cho người dùng chọn tải cùng recommended?"):
- Choices:
  - Turbo int8: 158 MB, 48 kHz, 25 voices. Desktop CPU RTF 0.315, first audio 0.20 s.
  - Nano: ~270 MB cached, 24 kHz, 11 voices. RTF 0.18.
  - The 122 MB word aligner: ticked by default on desktop, optional on the phone.
- One or both voices may be installed.
- "Khuyên dùng" before download comes from device facts (cores, RAM, GPU, chip class).
- After download, a few-second self-benchmark checks it. If the chosen voice cannot keep up with listening, offer to switch; never switch silently.
- The size shown is what this device still lacks (shared parts such as ONNX Runtime, the aligner and Studio's VieNeu are not counted twice).
- The same pattern applies to every module with options.
- Phone speed of Turbo is NOT measured yet (estimate RTF 0.6-1.5); thresholds get tuned once a real phone is measured.

Device choice (owner 03-10: never force CPU when a GPU is there), picked automatically:
- Studio installed (NVIDIA): GPU through Studio's torch. Yield to Studio work and fall back to CPU while the card is busy.
- GPU but no Studio: ONNX Runtime with DirectML (any vendor, about +20 MB in the module). Not measured with VieNeu yet.
- No GPU: CPU (numbers above).
- Phone: CPU with ARM-optimised kernels (XNNPACK). Try NNAPI/QNN if they help, but expect to rely on CPU. Measure on a real phone.

Phone, measured 03-10 (owner's OPPO A93 = CPH2121, MediaTek Helio P95 MT6779: 2x Cortex-A75 2.2 GHz + 6x A55 2.0 GHz,
7.6 GB RAM, Android 12; ONNX Runtime 1.30; run in the background while the owner watched YouTube, so a busy phone;
Kotlin port `mobile/android/.../vieneu/`, bench `scripts/vieneu_phone_bench.sh`, 3-5 sentences of 21-132 characters):
- Turbo int8, best = 2 threads for the per-frame graphs + 8 for the codec: RTF 1.75 (desktop 0.315, ~5.5x slower), first
  audio 1.0 s, load 4.2 s, peak memory 0.7-1.0 GB (the codec on the longest sentence). 1 thread 2.3; 6-8 threads 2.5
  (more threads than big cores slows the small per-frame graphs). XNNPACK 3.2 at 4-8 threads. Per audio second at the best
  setting: backbone step 0.41 s, acoustic decoder 0.52, output heads + sampling (Kotlin) 0.53, codec 0.30, prefill 0.23.
- Nano: RTF 1.8-1.9 at 4-8 threads (2.4 at 6 on a busier minute; 3.7 at 1), desktop 0.18; first audio = the whole
  sentence (6-7 s for a 45-character one); load 2.2 s; peak 0.5 GB. XNNPACK 3.9-4.3, NNAPI 4.4 (falls back, load 7.6 s).
- Two minutes of non-stop Turbo: RTF 2.35 first half, 2.16 second half, battery 39.6 -> 41.6 C - no thermal slow-down
  in that time; the spread (1.6-3.1 per sentence) is the phone's other work.
- Output sane: Nano is bit-identical to the desktop on all 5 sentences; Turbo's codec is bit-identical on the desktop's
  codes; Turbo int8 picks different codes from frame 0-1 (int8 kernels differ between ARM and x86) but every sentence
  keeps the desktop's length (+-7%) and loudness (RMS 0.10-0.11), no NaN.
- So on a 2020 mid-range phone neither voice keeps up with listening (needs RTF < 1, ideally < 0.8 for headroom).
  "Khuyên dùng" on phones: never live VieNeu below flagship-class big cores; offer it as "make ahead" (synthesize the next
  chapters while charging) or stream from a paired computer. A phone ~2.5x faster per big core (A78/X1 and newer) is the
  estimated break-even for Turbo; the after-download self-benchmark decides. Cheapest speed-ups left: move the 16 output
  heads into ORT (MLAS GEMV instead of Kotlin loops) and cut the 16 acoustic calls per frame.

How it is built (Lead 03-10): every voice does one thing - turn ONE paragraph of the text script (`textScript.ts`
`paragraphsOf`) into one audio clip at speed 1.0 plus `words` (one [start_ms, end_ms] per whitespace token, the
`words.ts` convention). The player strings clips into a virtual chapter clock (unknown paragraphs estimated at ~14
chars/s, corrected as clips arrive) and writes the timings into the chapter's text script, so the reading view lights
the paragraph and the word with no special case. Speed is the player's playback rate, never re-synthesis, so cached
clips stay valid. Desktop: voices run in the local server (`abook/readaloud/`, stdlib WebSocket client for Edge, OneCore
through PowerShell for the device voice), the web player plays the clips. Phone: voices run in the native core (Edge
client + `TextToSpeech.synthesizeToFile` with `onRangeStart` frames), so reading goes on with the screen off and across
chapters like an audiobook; the reading view asks the `ReadAloud` plugin for timings.

Read-aloud runs a little ahead of the listener (sentence queue, like video buffering), caches what it read as quick audio
in the book, and a phone without a voice engine can stream it from a paired computer (existing stream path).

### Read-along view (owner 03-10: "like Edge's read aloud")

Listen now reuses the existing reading mode (`ui/src/listen/ReaderScreen.tsx`: chapter text as an ebook, the playing
sentence lit and followed, "Nghe từ đây" on a tapped sentence, remembered position). New: the current WORD lit too, as Edge
does, where the voice gives word timings - Edge TTS (WordBoundary events with offsets), the device voice (Android
`UtteranceProgressListener.onRangeStart`, Windows SAPI word events). Owner 03-10: word highlighting is REQUIRED for both Listen now and Studio audiobooks.
Tap a word to read from it (owner 03-10, as Edge's Immersive Reader does): any word in the reading view is a start point,
for Listen now and Studio audiobooks alike - seek to that word's start from `words`; a Listen-now paragraph not yet
synthesized is made first, then played from the word's offset. No usable `words`: start at the line.
- VieNeu gives no word timings (checked: v3nano's duration predictor returns one total duration per utterance). Two ways:
  (a) synthesize per phrase (split at punctuation) and spread each phrase's time over its syllables. Vietnamese
  syllables are fairly even, so this is good enough to look right, though sometimes one beat off.
  (b) run a small CTC forced aligner (ONNX, CPU) on each synthesized sentence: exact. Measure its speed and pick.
- Studio audiobooks: a "word timing" step at packing time, OUTSIDE the hash-locked pipeline. It force-aligns each line's
  known text inside its known time span, with the same aligner as (b). The result is stored additively as
  `scripts/<n>.json` lines[i].words = [[start_ms, end_ms], ...] per word. Existing books get it by re-packing on a
  Studio machine.

### Word timings - measured 03-10 (research in D:/Novels/LLM_Train/word_align)

Ground truth: Edge TTS word boundaries (HoaiMy + NamMinh, 60 own sentences, 1,696 words; Edge's starts run ~100 ms early
because of MP3 codec delay - one constant offset learned per method). CPU Ryzen 9 8945HX.

| method | size | s per audio-min (4 thr) | starts within 100 ms |
|---|---|---|---|
| spread over syllables, no pause detection | 0 | 0.01 | 56% |
| spread over syllables + energy pauses | 0 | 0.01 | 93% (Edge), ~70% vs CTC on VieNeu |
| CTC wav2vec2 base Vietnamese, ONNX int8 | 122 MB | 1.3 (4.2 on 1 thread) | 99% (median 15 ms) |
| MMS_FA multilingual, ONNX int8 | 355 MB | 2.4 | 99% (no better) |

All base CTC models tie; large/MMS add nothing; int8 loses nothing. On VieNeu audio two different CTC models agree within
20 ms (p90), CTC adds ~110 ms per 5 s sentence (~13% of synthesis time).

Decision:
- Aligner: `dragonSwing/wav2vec2-base-vietnamese` (Apache-2.0), ONNX int8, 122 MB. Feed it the TTS's normalised text and
  map back to the displayed tokens; a word ends where the next starts.
- Studio books (case B): align each line inside its known span at pack time on the desktop (~13 CPU-minutes per 10-hour
  book), store word timings in the `.abook`, so every player just reads them. Fallback: spread + energy pauses.
- Listen now with VieNeu on desktop (case A): show spread + energy pauses at once, swap in CTC timings when ready.
- Phone: streaming from a computer gets timings from it; local VieNeu uses spread + pauses (~70% within 100 ms), with the
  122 MB aligner as an optional part of the VieNeu module (estimated 10-17 s per audio-min on a phone, not measured).
- Edge TTS and the device voice give word timings themselves.
- Side benefit: the same CTC output gives an 8.6% syllable error rate on VieNeu audio - a free check for skipped or
  mispronounced words.

Status 03-10: the Studio-book part is built (`abook/webui/word_timing.py`, `words` in `scripts/<n>.json`, docs/ABOOK_FILE_FORMAT.md "Word
timings", the "wordalign" Studio step, "Căn từ cho sách đã làm" in the export box, the lit word in `ui/src/listen/ReaderScreen.tsx`). Measured
here with the real int8 model on a 13.7-minute chapter: 1.3 s per audio-minute with 8 threads, 2.1 with 4, 4.2 with 1; the numpy Viterbi is
0.05 s per audio-minute, decoding 0.02. The spread fallback costs 0.03. Listen now (VieNeu / Edge / device voice) is not built yet.

## 4. Music while listening

No analysis means no scene moods, so the machine does not pick per scene. The user pins tracks to chapters (existing pins),
or chooses a playlist: catalogue tracks filtered by the book's genre or a feel the user picks, or their own imported tracks.
A stage-1 book (analysed) can use the normal scene picker.

## 5. Order of work

1. Importers (all formats) - useful to Studio at once.
2. Format version with stages + quick audio; readers tolerate text-only chapters (P3 told to keep helpers tolerant).
3. Listen now with the device voice (desktop + phone), read-ahead, quick-audio cache, text view.
4. Edge TTS opt-in; VieNeu module (desktop, then phone after measuring).
5. Music playlists / pins for Listen now.
