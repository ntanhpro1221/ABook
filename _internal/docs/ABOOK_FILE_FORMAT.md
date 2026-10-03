# The ABook file format (`.abook`)

Media type: `application/vnd.ngdtuanh.abook+zip` · File extension: `.abook` · Format versions: 1, 2, 3, 4 (current: 4)

An `.abook` file is one finished audiobook produced by ABook (https://github.com/ntanhpro1221/ABook): the audio of every
chapter, the text with who speaks each line, the cast of characters and the cover, in a single file that the ABook apps
for Windows and Android open. Since version 3 one file can hold a whole multi-part series (a story split into parts with
"continue this book"). The reference implementation is `_internal/abook/webui/bookfile.py`.

An `.abook` is, logically, a **subset of an `.abookproj`** (`ABOOKPROJ_FILE_FORMAT.md`): a project file carries the same
listening layer (`book.json`, `cast.json`, `chapters/`, `scripts/`, `samples/`, `music/`, `cover.jpg`, and the version 4 edit
layer) with exactly the entry names below, next to the production workshop, so anything that opens an `.abook` can play the
listening layer of an `.abookproj`. The project file stores no byte twice: where the same audio also lives under
`project/`, that copy is an alias of the `chapters/<name>.mp3` entry. An `.abook` itself keeps the strict names listed below.

## Container

A ZIP archive (PKWARE APPNOTE, as used by EPUB and OOXML).

1. The **first** entry is named `mimetype`, stored **uncompressed**, and contains exactly the
   ASCII string `application/vnd.ngdtuanh.abook+zip` (no newline). A reader can identify the format from the fixed
   bytes at the start of the file (the entry name at offset 30, the media type right after it) without opening the
   archive, the same technique EPUB uses.
2. Every other entry name must match one of the names below. Absolute paths, `..`, and any other name make the file
   invalid.

| Entry | Compression | Content |
|---|---|---|
| `mimetype` | stored | the media type, see above |
| `book.json` | deflate | the book: title, author, chapters, durations, and a `package` object with the format version and the size and SHA-256 of every other entry |
| `manifest.json` | deflate | the same book as a Readium Audiobook manifest, so other audiobook players can read the audio |
| `cover.jpg` | deflate | cover image (optional) |
| `cast.json` | deflate | characters and the voice each one speaks with |
| `chapters/<name>.mp3` | stored | chapter audio, MP3; stored so players can seek inside the archive |
| `chapters/<part>/<name>.mp3` | stored | version 3 only: chapter audio of part `<part>` (1-4 digits); two parts may use the same file name |
| `scripts/<n>.json` | deflate | the lines of chapter `n`: text, kind (narration / dialogue / thought / heading), speaker, emotion, intensity, pace, volume, and the time span inside the chapter MP3; since 2026-10-03 optionally the time of every word (`words`, see "Word timings") |
| `samples/<n>.wav` | stored | short voice sample of a character |
| `music/<sha1>.<ext>` | stored | version 2 and later: a background-music track the producer attached; `<sha1>` is 40 hex digits and the file is stored once however many chapters or parts use it. `<ext>` is `mp3` for catalogue tracks; a track the producer imported from their own files (`music.tracks[...].link` starts with `local:`) keeps its own format: `mp3`, `m4a`, `ogg`, `opus`, `flac` or `wav`, and `<sha1>` is then the hash of the file's content. Such a track carries no licence fields, only the title and artist read from the file's own tags |
| `edits.json` | deflate | version 4 only: the listener's edit layer (see below), at most 1 MiB |
| `edits/cover.jpg` | deflate | version 4 only: a cover the listener chose, JPEG, at most 8 MiB; only with `edits.json` |

A `.abook` never contains `project/`, `sources/` or `views/` (the producer's workshop): a reader refuses those names.

## Versions

`package.version` is the **lowest** version able to hold the content: a one-part book without music is version 1, so
older apps still open it.

| Version | Adds |
|---|---|
| 1 | the layout above without `music/` and without part folders |
| 2 | background music: the `music` object of `book.json` (`levelDb`, `tracks`, and per chapter the cue list `chapters[<chapterId>]` of `{start, end, track, gainDb}`) and the `music/<sha1>.<ext>` entries |
| 3 | a whole series in one file: parts, nested chapter paths and a series-wide chapter id scheme, described next |
| 4 | the listener's edit layer: `edits.json` and `edits/cover.jpg`, described after version 3. Only written when the listener changed something; an unedited book stays at version 1-3 |

### Version 3: a series in one file

- **Chapter paths.** Audio is `chapters/<part>/<name>.mp3`. Each part keeps its own audio file names, which are not unique
  across parts, hence the folder. (A version 3 reader also accepts the flat `chapters/<name>.mp3`.) Version 1 and 2 files
  must not contain a part folder; a reader treats such an entry as an unknown name.
- **Chapter ids.** The id of a chapter is `part * 100000 + id inside the part` (part 2, chapter 1: `200001`). It is the
  `id` in `book.json`, the `<n>` of `scripts/<n>.json`, the `chapterId` inside that script, the key of the `music.chapters`
  object, and what a listener's position and bookmarks refer to. Adding a part later never changes an existing id, so
  listening data survives re-opening a longer file of the same series. Every chapter also has `part`.
- **`parts`.** A top-level array in `book.json`, in reading order: `{part, title, chapters: [firstId, lastId], duration,
  narrator}`. `title` is the series title with the suffix ` · Phần N` ("Part N"); `duration` is in seconds. Parts that had
  nothing to hear yet are left out, so part numbers may skip.
- **Series-wide metadata.** `title` is the series title without the part suffix. There is one `cover.jpg` (the first part's)
  and one `cast.json`: characters are merged by their canonical `name`, line counts are summed, and each character has
  `parts: [n, ...]`, the parts in which they speak.
- **Samples.** `samples/<k>.wav` are numbered 1..K across the whole file, and `sampleId` in `cast.json` refers to that new
  number (sample ids of different parts would otherwise collide).
- **Music.** One `music/<sha1>.<ext>` per track, shared by every part that uses it; `music.chapters` is keyed by the series-wide
  chapter id.
- **Size.** A series can be several gigabytes. A single file larger than 4 GiB cannot be stored on FAT32 media (some SD
  cards and USB sticks), so the producing app also offers one file per part (each a normal version 1 or 2 file).

### Version 4: the edit layer

The book layer (`book.json`, `cast.json`, `scripts/`, `cover.jpg`, `music/`, audio) is the producer's and is never
rewritten by a listener's app. What a listener changes lives next to it in `edits.json`, a JSON object:

| Key | Content |
|---|---|
| `format`, `version` | `"abook-edits"`, `1` |
| `title` | book title shown instead of the one in `book.json` |
| `cover` | absent: the book's cover; `{color, width, height, version}` and `edits/cover.jpg`: the listener's cover |
| `characters` | `{canonical name: display name}` |
| `chapters` | `{chapter id: {title?, subtitle?}}` |
| `music` | `{enabled?, levelDb?, silenced?: ["<chapter id>:<start in ms>", ...], pins?: {"<chapter id>:<start in ms>": "local:<sha1>"}, tracks?: {"<sha1>": {ext, title?, creator?, duration?, lufs?}}}` - cues the listener silenced; cues the listener switched to one of their own tracks, and the info of exactly those tracks (`ext` mp3, m4a, ogg, opus, flac or wav). The track file is `music/<sha1>.<ext>` in the package, listed in `package.files` but not in `book.json`'s `music.tracks` (a reader that knows `pins` plays it from there) |
| `wishes` | what the listener asked of a producer's Studio (never applied by the reader): `{pronunciations?, speakers?, lines?, voices?, retakes?, aliases?}` with the entry shapes of the Studio's `overrides.json` (a name's spoken form, who says a line, a line's kind/emotion/spoken text, a character's voice or gender, a line to retake, a name to merge). Lines are named by the `stableId` + `textSha256` of the script segments |

Readers validate it strictly and refuse the whole file when it is malformed: more than 1 MiB, more than 2,000
characters, 5,000 chapters, 5,000 silenced cues or 5,000 pinned cues, a pin without its track info (or the reverse), a pinned track whose file is not in the package, more than 2,000 wishes of one kind (5,000 for speakers and retakes), a wish entry with a missing or unknown key, text that is not clean (titles longer than 160 code points, names
longer than 80, control characters, leading or trailing blanks), `levelDb` outside -40..-6, a cover colour that is not
`#rrggbb`. Edits are only the minimum: a value equal to the book's is not stored. The layer never edits story text.

Opening the same book again keeps the listener's own edits (theirs win on a clash; silenced cues and pins are merged). When the
computer that made the book opens a file with edits, it may offer to apply them to its project.

**Privacy.** `edits.json` holds no device name, account, path or time of listening: only the edits themselves (a wish carries the
time it was made, `requested_at`, which the producer re-stamps when it applies the wish).

No version carries the machine-local book id or the `series` link that the phone sync package has: the file names no
location on the producing computer.

## Word timings (`words`)

Each entry of `segments` in `scripts/<n>.json` may carry `words`, which lets a player light the word being spoken (read-along). It is
additive: the format version does not change, a reader that does not know `words` ignores it, and a reader must work without it
(light the whole sentence, as before). Absence is normal: books packed before 2026-10-03, or on a machine that could not align.

```json
{"id": 12, "text": "Trời vừa hửng sáng, sương mù.", "start": 3.412, "end": 6.05, "words": [[3450, 3820], [3820, 4010], [4010, 4300], [4300, 5150], [5390, 5700], [5700, 6020]]}
```

- One `[start_ms, end_ms]` pair per **displayed token**, in order. The tokens of `text` are its maximal runs of non-whitespace characters
  (JavaScript `/\S+/g`, Python `re.findall(r"\S+", text)`): punctuation stays attached to its word, a number such as `2.500.000` is one token.
- Times are integer milliseconds from the **start of the chapter MP3** (the clock `start` / `end`, which are seconds, are on), not from the
  start of the sentence.
- A word ends where the next one starts (`words[i][1] == words[i+1][0]`), so the highlight is continuous; the last word keeps its own end.
  `start <= end` and starts never decrease. A token with no sound (a lone dash) has zero length.
- A reader uses `words` only when it is an array whose length equals the number of tokens of `text` and whose pairs are numbers in
  non-decreasing order; otherwise it ignores it for that sentence. The listener's edit layer never changes story text, so `words` stays
  valid; a Studio that re-renders or edits a sentence aligns it again.
- Producer side (`abook/webui/word_timing.py`): at packing time each line's known text is force-aligned inside its known time span with
  a CTC speech model (wav2vec2 Vietnamese, ONNX int8, Apache-2.0), numbers read out and foreign letters mapped to the model's alphabet; when
  the model is absent or the fit is poor it spreads the span over syllables and snaps phrase breaks to detected silences. The result is
  cached per project (`word_timings/<chapter>.json`: SHA-256 of the chapter audio, and per line the SHA-256 of the text, the span and
  the method), so packing again aligns nothing new. Measured on 1,696 Edge TTS words: 99% of word starts within 100 ms of the reference
  after one constant offset, median 15 ms.

## Rules for readers

- Reject the file if `mimetype` is not the first entry, is compressed, or does not hold the exact media type.
- Reject entries whose size or SHA-256 differs from `book.json`, more than 20,000 entries, JSON entries over 32 MiB,
  or more than 64 GiB in total.
- Reject a `package.version` greater than the version the reader supports (currently 4), and tell the user to update.
- Check that the destination has room for the whole book before extracting, and extract and hash in one pass.
- Nothing inside the file is executed. The file carries no listening data (position, bookmarks, history) and no
  identifier of the person or device that made it.

## Security considerations

The file is a ZIP of media and JSON. Risks are the usual ones for archives: path traversal (prevented by the fixed
entry names), decompression bombs (prevented by the entry, size and hash limits), and malformed MP3/JPEG/WAV data, which
readers hand to their platform's media decoders. The format has no active content and no external references.

## Versioning

`package.version` in `book.json` is an integer. Additions that old readers can ignore keep the version; anything an old
reader would misread raises it (version 2 added `music/` entries, version 3 added part folders, version 4 the `edits.json` / `edits/` entries: an older reader would
report them as unknown names, so the version was raised and the older reader asks the user to update the app).
