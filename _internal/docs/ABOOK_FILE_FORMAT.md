# The ABook file format (`.abook`)

Media type: `application/vnd.ngdtuanh.abook+zip` · File extension: `.abook` · Format version: 1

An `.abook` file is one finished audiobook produced by ABook (https://github.com/ntanhpro1221/ABook): the audio of every
chapter, the text with who speaks each line, the cast of characters and the cover, in a single file that the ABook apps
for Windows and Android open. The reference implementation is `_internal/abook/webui/bookfile.py`.

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
| `scripts/<n>.json` | deflate | the lines of chapter `n`: text, kind (narration / dialogue / thought / heading), speaker, emotion, intensity, pace, volume, and the time span inside the chapter MP3 |
| `samples/<n>.wav` | stored | short voice sample of a character |

## Rules for readers

- Reject the file if `mimetype` is not the first entry, is compressed, or does not hold the exact media type.
- Reject entries whose size or SHA-256 differs from `book.json`, more than 20,000 entries, JSON entries over 32 MiB,
  or more than 64 GiB in total.
- Reject a `package.version` greater than the version the reader supports, and tell the user to update.
- Nothing inside the file is executed. The file carries no listening data (position, bookmarks, history) and no
  identifier of the person or device that made it.

## Security considerations

The file is a ZIP of media and JSON. Risks are the usual ones for archives: path traversal (prevented by the fixed
entry names), decompression bombs (prevented by the entry, size and hash limits), and malformed MP3/JPEG/WAV data, which
readers hand to their platform's media decoders. The format has no active content and no external references.

## Versioning

`package.version` in `book.json` is an integer. Additions that old readers can ignore keep the version; anything an old
reader would misread raises it.
