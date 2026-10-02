# The ABook project file format (`.abookproj`)

Media type: `application/vnd.ngdtuanh.abookproj+zip` · File extension: `.abookproj` · Format version: 1

An `.abookproj` file is one whole audiobook *production project* of ABook (https://github.com/ntanhpro1221/ABook): the
project database, the audio recorded so far, the working files, the chapter sources and the cover, in a single file.
It is for backing a project up or moving it to another computer; opening it gives the same project back in the ABook
Studio. The finished audiobook for listening is a different format, `.abook` (`ABOOK_FILE_FORMAT.md`). The reference
implementation is `_internal/abook/webui/projectfile.py`.

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
| `project.json` | deflate | format, version, producer, creation time, book title, the project's original folder, the chapter sources (original path and entry name), sources that were missing when packing, and the size and SHA-256 of every other entry |
| `cover.jpg` | deflate | copy of the cover, if any, so file browsers can show a thumbnail without reading the project |
| `project/<path>` | stored for audio and images, deflate otherwise | every file of the project folder. `project/project.sqlite3` is a consistent SQLite snapshot (no `-wal`/`-shm`); logs, lock files, partial `.part` files and exported `.abook` files are left out |
| `sources/<n>_<name>` | deflate | chapter source text files that lived outside the project folder; `n` is the chapter number |

## Rules for readers

- Reject the file if `mimetype` is not the first entry, is compressed, or does not hold the exact media type.
- Reject entries whose size or SHA-256 differs from `project.json`, entries not listed there, more than 1,000,000
  entries, a `project.json` over 64 MiB, or more than 512 GiB in total. Check free disk space before extracting.
- Reject a `version` greater than the version the reader supports, and tell the user to update.
- Open into a **new** folder; never replace an existing project. Extract to a temporary folder and rename it only when
  complete.
- The project database stores absolute paths. After extracting, rewrite only the plain path columns: paths under the
  original project folder move under the new folder, and each listed source moves to its `sources/` entry. Settings
  and hashed records inside the database are not changed.
- Nothing inside the file is executed.

## Security considerations

The file is a ZIP of audio, images, text and an SQLite database. Risks are those of archives: path traversal
(prevented by the entry-name rules), decompression bombs (prevented by the entry, size and hash limits and the disk
check), and malformed media or database files. The database is opened only by the application's own code with fixed
queries; it holds no executable content and is not attached to other databases. The file can contain the full text
of the book being produced and the original folder paths of the computer that packed it; it carries no listening data.

## Versioning

`version` in `project.json` is an integer. Additions that old readers can ignore keep the version; anything an old
reader would misread raises it.
