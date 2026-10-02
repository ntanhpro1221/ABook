# The ABook file format (`.abook`)

Media type: `application/vnd.ngdtuanh.abook+zip` · File extension: `.abook` · Format versions: 1, 2, 3, 4 (current: 4)

An `.abook` file is one finished audiobook produced by ABook (https://github.com/ntanhpro1221/ABook): the audio of every
chapter, the text with who speaks each line, the cast of characters and the cover, in a single file that the ABook apps
for Windows and Android open. Since version 3 one file can hold a whole multi-part series (a story split into parts with
"continue this book"). The reference implementation is `_internal/abook/webui/bookfile.py`.

An `.abook` is, logically, a **subset of an `.abookproj`** (`ABOOKPROJ_FILE_FORMAT.md`): a project file carries the same
listening layer (`book.json`, `cast.json`, `scripts/`, `samples/`, `music/`, `cover.jpg`) next to the production
workshop, so anything that opens an `.abook` can play the listening layer of an `.abookproj`. The one difference is the
chapter audio: a project file stores each chapter MP3 once, under `project/output/chapters/<name>.mp3`, and its
`book.json` points there instead of at `chapters/<name>.mp3`. An `.abook` itself keeps the strict names listed below; the
`project/` paths are valid only inside an `.abookproj`.

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
| `scripts/<n>.json` | deflate | the lines of chapter `n`: text, kind (narration / dialogue / thought / heading), speaker, emotion, intensity, pace, volume, and the time span inside the chapter MP3 |
| `samples/<n>.wav` | stored | short voice sample of a character |
| `music/<sha1>.mp3` | stored | version 2 and later: a background-music track the producer attached; `<sha1>` is 40 hex digits and the file is stored once however many chapters or parts use it |
| `edits.json` | deflate | version 4 only: the listener's edit layer (see below), at most 1 MiB |
| `edits/cover.jpg` | deflate | version 4 only: a cover the listener chose, JPEG, at most 8 MiB; only with `edits.json` |

A `.abook` never contains `project/`, `sources/` or `views/` (the producer's workshop): a reader refuses those names.

## Versions

`package.version` is the **lowest** version able to hold the content: a one-part book without music is version 1, so
older apps still open it.

| Version | Adds |
|---|---|
| 1 | the layout above without `music/` and without part folders |
| 2 | background music: the `music` object of `book.json` (`levelDb`, `tracks`, and per chapter the cue list `chapters[<chapterId>]` of `{start, end, track, gainDb}`) and the `music/<sha1>.mp3` entries |
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
- **Music.** One `music/<sha1>.mp3` per track, shared by every part that uses it; `music.chapters` is keyed by the series-wide
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
| `music` | `{enabled?, levelDb?, silenced?: ["<chapter id>:<start in ms>", ...]}` - cues the listener silenced |
| `wishes` | what the listener asked of a producer's Studio (never applied by the reader): `{pronunciations?, speakers?, lines?, voices?, retakes?, aliases?}` with the entry shapes of the Studio's `overrides.json` (a name's spoken form, who says a line, a line's kind/emotion/spoken text, a character's voice or gender, a line to retake, a name to merge). Lines are named by the `stableId` + `textSha256` of the script segments |

Readers validate it strictly and refuse the whole file when it is malformed: more than 1 MiB, more than 2,000
characters, 5,000 chapters or 5,000 silenced cues, more than 2,000 wishes of one kind (5,000 for speakers and retakes), a wish entry with a missing or unknown key, text that is not clean (titles longer than 160 code points, names
longer than 80, control characters, leading or trailing blanks), `levelDb` outside -40..-6, a cover colour that is not
`#rrggbb`. Edits are only the minimum: a value equal to the book's is not stored. The layer never edits story text.

Opening the same book again keeps the listener's own edits (theirs win on a clash; silenced cues are merged). When the
computer that made the book opens a file with edits, it may offer to apply them to its project.

**Privacy.** `edits.json` holds no device name, account, path or time of listening: only the edits themselves (a wish carries the
time it was made, `requested_at`, which the producer re-stamps when it applies the wish).

No version carries the machine-local book id or the `series` link that the phone sync package has: the file names no
location on the producing computer.

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
