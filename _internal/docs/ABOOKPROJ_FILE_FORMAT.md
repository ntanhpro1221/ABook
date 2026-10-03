# The ABook project file format (`.abookproj`)

Media type: `application/vnd.ngdtuanh.abookproj+zip` · File extension: `.abookproj` · Format version: 3 (the only one read)

An `.abookproj` file is one whole audiobook *production project* of ABook (https://github.com/ntanhpro1221/ABook): the
project database, the audio recorded so far, the working files, the chapter sources and the cover, in a single file.
It is for backing a project up or moving it to another computer; opening it gives the same project back in the ABook
Studio. The finished audiobook for listening is a different format, `.abook` (`ABOOK_FILE_FORMAT.md`), and an `.abook`
is logically a **subset** of an `.abookproj`: a project file also carries the *listening layer* of the book with the very
entry names of an `.abook`, so a reader that can open an `.abook` (the Android app) can play the finished chapters of a
project file without the production data. The reference implementation is `_internal/abook/webui/projectfile.py`.

Version 3 is the first version meant for sharing; versions 1 and 2 (development builds) are not read - an older file is
refused with a message to re-pack it with the app that wrote it.

## Container

A ZIP archive (PKWARE APPNOTE, as used by EPUB and OOXML).

1. The **first** entry is named `mimetype`, stored **uncompressed**, and contains exactly the ASCII string
   `application/vnd.ngdtuanh.abookproj+zip` (no newline). The entry name sits at offset 30 and the media type right
   after it, so the format is identified from the first bytes, as for EPUB and `.abook`.
2. Every other entry name must be one of the names below. Absolute paths, `..`, backslashes, drive letters, control
   characters and any other top-level name make the file invalid.

| Entry | Compression | Content |
|---|---|---|
| `mimetype` | stored | the media type, see above |
| `project.json` | deflate | format, version, producer, creation time, book title, `workshop`, the project's original folder, the chapter sources (original path and entry name), sources that were missing when packing, `aliases`, and the size and SHA-256 of every other entry (aliases included) |
| `cover.jpg` | stored | the cover, if any (also what file browsers show as a thumbnail) |
| `project/<path>` | stored for audio and images, deflate otherwise | every file of the project folder. `project/project.sqlite3` is a consistent SQLite snapshot (no `-wal`/`-shm`); logs, lock files, partial `.part` files and exported `.abook` files are left out. Absent when `workshop` is `"pending"` |
| `sources/<n>_<name>` | deflate | chapter source text files that lived outside the project folder; `n` is the chapter number. Optional when `workshop` is `"pending"` (then they are what "Dựng xưởng" uses instead of rebuilding the text from the scripts) |
| `views/work.json`, `views/casting.json`, `views/names.json` | deflate | read-only snapshots of three Studio screens, see below |
| `book.json` | deflate | the listening layer's description, exactly the `book.json` of an `.abook` (`ABOOK_FILE_FORMAT.md`) without any identifier, with `package.files` listing the size and SHA-256 of each listening entry (aliases included). Present when at least one chapter was finished at packing time, and always when `workshop` is `"pending"` |
| `chapters/<name>.mp3`, `cast.json`, `scripts/<n>.json`, `samples/<n>.wav`, `music/<sha1>.<ext>` | as in `.abook` | the listening layer: the audio of the finished chapters, the cast, the lines of each chapter, voice samples, and every background-music track the book's music plan uses (taken from the packing computer's music cache, downloaded if needed; a track that cannot be obtained is left out and its cues dropped, as for `.abook`) |
| `edits.json`, `edits/cover.jpg` | as in `.abook` | the listener's edit layer (`ABOOK_FILE_FORMAT.md`, version 4 section), written by an app that has no workshop to put the edits in (the Android app, a Windows install without Studio), with the pinned tracks `music/<sha1>.<ext>`. Studio never writes them |

## `project.json`

```
{"format": "abookproj", "version": 3, "createdAt": "...", "producer": "ABook", "title": "...",
 "workshop": "present" | "pending",
 "projectRoot": "D:\\Studio\\sach_thu" ("" when pending), "sources": [{"path": "...", "entry": "sources/00001_645.txt"}],
 "missingSources": ["..."], "aliases": {"<alias>": "<real entry>"}, "files": {"<entry>": {"size": N, "sha256": "..."}}}
```

- `workshop: "present"` - the file carries the workshop (`project/` with at least `project.sqlite3` and `book_settings.json`).
  Opened by Studio it becomes a project.
- `workshop: "pending"` - the file has only the listening layer (and the listener's edits and wishes): it was saved from an
  `.abook`, or from a project by an app with no workshop to keep. It has no `project/` entries and must have `book.json`.
  An ABook with Studio offers **"Dựng xưởng"**: a new project is created from the book (sources if present, else the text rebuilt from
  `scripts/`), seeded with the voice keys of `cast.json`, the display names the listener set, and the wishes that still make
  sense (pronunciations, voice/gender, merged names; wishes tied to one line are dropped). Lost: the original chapter
  sources (unless included), the analysis history, every recorded line, seeds, candidates and listener acceptances - the
  whole audio is produced again.

## No byte is stored twice (`aliases`)

An entry with a media suffix (`.mp3 .wav .jpg .png .flac .ogg .opus .m4a .zip`) and a non-zero size whose size and SHA-256
equal another entry's is an **alias**: it is *not* in the archive, `project.json` lists it in `aliases` (alias -> real entry)
and in `files` with the very size and hash of the real entry. Among identical entries the real one is the one that belongs
to the listening layer (`chapters/…`, `samples/…`, `cover.jpg`, `music/…`), else the first by name - so a chapter MP3 lives at
`chapters/<name>.mp3` and `project/output/chapters/<name>.mp3` is its alias, a voice sample is `samples/<n>.wav` with
`project/work/…wav` an alias, and `project/cover.jpg` an alias of `cover.jpg`. A reader that only listens never meets an
alias of a listening entry unless the same bytes also occur twice in the listening layer; it reads the real entry then. A
reader that unpacks the project writes the alias's path with the real entry's bytes.

## Read-only views (`views/`)

Snapshots, taken at packing time with the very functions Studio uses for those screens, so the JSON is the one the Studio
routes answer: `work.json` = `GET /api/books/<id>/work` ("Việc cần duyệt"), `casting.json` = `/casting` (the chapter table of the
script tab), `names.json` = `/pronunciations` ("Cách đọc tên"). A reader shows them without opening
`project/project.sqlite3`. A view that could not be computed is simply absent; a view that is not JSON, or a name other than
these three, makes the file invalid.

## The listening layer

A reader that only wants to listen extracts exactly the entries named in `book.json`'s `package.files` and never touches
`project/project.sqlite3`, the other `project/` files or `sources/`. The Android app unpacks the listening layer into its
library like an `.abook`, and additionally keeps `project.json`, `project/`, `sources/` and `views/` byte for byte next to it so
that "Lưu" can write the file again (`BookDocumentWriter`); it never opens the database. When a project file is opened as a
project (desktop with Studio), the listening layer is not extracted - the project holds its own copies - except that the music
tracks are copied into the music cache so the project plays its music offline.

## Opening on a computer with the project

If every chapter of the file is already present, byte for byte, in a project of this computer, the file is the same project
(possibly edited elsewhere): no second project is made, the file's edits (`edits.json`) are set aside for the user to
confirm ("N thay đổi - áp vào dự án?") and applied through the same writers the editor uses. A file with chapters the project does not
have (it was continued elsewhere) opens as a new project, as before.

## Rules for readers

- Reject the file if `mimetype` is not the first entry, is compressed, or does not hold the exact media type.
- Reject entries whose size or SHA-256 differs from `project.json`, entries not listed there, more than 1,000,000
  entries, a `project.json` over 64 MiB, or more than 512 GiB in total. Check free disk space before extracting.
- Reject a `version` other than the one the reader supports (3); tell the user to update the app when it is greater.
- `files` must list exactly the archive's entries plus the aliases. An alias must not be in the archive, must name an entry
  that is, must have a media suffix and the same size and hash as that entry.
- `workshop` must be `"present"` or `"pending"`; a `"pending"` file must not contain `project/` entries and must contain `book.json`,
  a `"present"` one must contain `project/project.sqlite3` and `project/book_settings.json`.
- If `book.json` is present, `package.files` must list exactly the listening entries (`cast.json`, `cover.jpg`, `chapters/`,
  `scripts/`, `samples/`, `music/`, `edits.json`, `edits/cover.jpg`) with the same size and SHA-256 as `project.json`, every
  chapter `file` must be one of them, and the edit layer passes the same checks as in an `.abook` (strict, whole file refused on
  any violation).
- A listening-only reader checks free space against the size of what it unpacks, not the whole archive.
- Open into a **new** folder; never replace an existing project. Extract to a temporary folder and rename it only when
  complete.
- The project database stores absolute paths. After extracting, rewrite only the plain path columns: paths under the
  original project folder move under the new folder, and each listed source moves to its `sources/` entry. Settings
  and hashed records inside the database are not changed.
- Nothing inside the file is executed.

## Security considerations

The file is a ZIP of audio, images, text and an SQLite database. Risks are those of archives: path traversal
(prevented by the entry-name rules), decompression bombs (prevented by the entry, size and hash limits and the disk
check), alias tricks (an alias must name a real entry of the same bytes, so it can only repeat data already in the file)
and malformed media or database files. The database is opened only by the application's own code with fixed queries; it
holds no executable content and is not attached to other databases. The file can contain the full text of the book being
produced and the original folder paths of the computer that packed it; it carries no listening data (position, bookmarks,
history).

## Versioning

`version` in `project.json` is an integer. Additions that old readers can ignore keep the version; anything an old
reader would misread raises it. Version 2 (development only) added the listening-layer entries; version 3 made chapter
audio and samples aliases instead of renamed entries, added `workshop`, `aliases`, `views/` and the listener's edit layer.
