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

## 3. Voices for Listen now

| Voice | Download | Network | Notes |
|---|---|---|---|
| the device's own TTS | none | no | default. Android `TextToSpeech` (Google vi-VN); Windows SAPI/OneCore (vi-VN voice "An" needs the Vietnamese speech pack) |
| Edge TTS | none | yes | Microsoft neural vi-VN voices (HoaiMy, NamMinh) through Edge's read-aloud service; unofficial, may stop working - opt-in, falls back to the device voice |
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

Read-aloud runs a little ahead of the listener (sentence queue, like video buffering), caches what it read as quick audio
in the book, and a phone without a voice engine can stream it from a paired computer (existing stream path).

### Read-along view (owner 03-10: "like Edge's read aloud")

Listen now reuses the existing reading mode (`ui/src/listen/ReaderScreen.tsx`: chapter text as an ebook, the playing
sentence lit and followed, "Nghe từ đây" on a tapped sentence, remembered position). New: the current WORD lit too, as Edge
does, where the voice gives word timings - Edge TTS (WordBoundary events with offsets), the device voice (Android
`UtteranceProgressListener.onRangeStart`, Windows SAPI word events). Owner 03-10: word highlighting is REQUIRED for both Listen now and Studio audiobooks.
- VieNeu gives no word timings (checked: v3nano's duration predictor returns one total duration per utterance). Two ways:
  (a) synthesize per phrase (split at punctuation) and spread each phrase's time over its syllables. Vietnamese
  syllables are fairly even, so this is good enough to look right, though sometimes one beat off.
  (b) run a small CTC forced aligner (ONNX, CPU) on each synthesized sentence: exact. Measure its speed and pick.
- Studio audiobooks: a "word timing" step at packing time, OUTSIDE the hash-locked pipeline. It force-aligns each line's
  known text inside its known time span, with the same aligner as (b). The result is stored additively as
  `scripts/<n>.json` lines[i].words = [[start_ms, end_ms], ...] per word. Existing books get it by re-packing on a
  Studio machine.

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
