"""Read bounded ZIP metadata over HTTP Range; download/inflate only a pinned member."""
from __future__ import annotations

import os
import struct
import urllib.request
import zipfile
import zlib
from pathlib import Path

from . import studio_setup


class _Remote:
    def __init__(self, url, size, cancelled):
        self.url, self.size, self.cancelled, self.position = url, size, cancelled, 0

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset + (self.position if whence == 1 else self.size if whence == 2 else 0)
        return self.position

    def read(self, size=-1):
        if self.cancelled():
            raise studio_setup.Cancelled()
        size = min(size if size >= 0 else self.size, self.size - self.position)
        if not 0 <= self.position <= self.size or not 0 <= size <= 131072:
            raise studio_setup.SetupError("ZIP metadata vượt giới hạn đã ghim.")
        if not size:
            return b""
        end = self.position + size - 1
        request = urllib.request.Request(self.url, headers={"Range": f"bytes={self.position}-{end}"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status != 206 or response.headers.get("Content-Range") != f"bytes {self.position}-{end}/{self.size}":
                    raise studio_setup.RangeUnavailable("Máy chủ không hỗ trợ tải riêng FFmpeg (HTTP Range). Thử lại sau.")
                data = response.read(size + 1)
        except studio_setup.TRANSPORT_ERRORS as error:
            raise studio_setup.SetupError("Không tải được ZIP metadata. Thử lại.") from error
        if len(data) != size:
            raise studio_setup.SetupError("ZIP metadata tải chưa đủ cỡ. Thử lại.") from ConnectionError("short ZIP metadata")
        self.position += size
        return data


def member_offset(item, archive_size, member, exe_size, crc, cancelled):
    remote = _Remote(item.url, archive_size, cancelled)
    with zipfile.ZipFile(remote) as bundle:
        info = bundle.getinfo(member)
    if (info.compress_type, info.compress_size, info.file_size, info.CRC, info.flag_bits & 1) != (zipfile.ZIP_DEFLATED, item.size, exe_size, crc, 0):
        raise studio_setup.SetupError("FFmpeg trong ZIP không đúng bản đã ghim.")
    remote.seek(info.header_offset)
    header = remote.read(30)
    signature, name_size, extra_size = struct.unpack("<4s22xHH", header)
    if signature != b"PK\x03\x04" or remote.read(name_size).decode("utf-8") != member:
        raise studio_setup.SetupError("Header FFmpeg trong ZIP không hợp lệ.")
    offset = info.header_offset + 30 + name_size + extra_size
    if offset < 0 or offset + item.size > archive_size:
        raise studio_setup.SetupError("Vị trí FFmpeg ngoài ZIP đã ghim.")
    return offset


def inflate(source: Path, target: Path, size: int, sha256: str, crc: int, cancelled) -> None:
    decoder, count, checksum = zlib.decompressobj(-15), 0, 0
    try:
        with source.open("rb") as compressed, target.open("wb") as output:
            while chunk := compressed.read(65536):
                if cancelled():
                    raise studio_setup.Cancelled()
                data = decoder.decompress(chunk)
                count += len(data)
                if count > size:
                    raise studio_setup.SetupError("FFmpeg giải nén vượt cỡ đã ghim.")
                checksum = zlib.crc32(data, checksum)
                output.write(data)
        if not decoder.eof or decoder.unused_data or count != size or checksum != crc or studio_setup._sha256(target) != sha256:
            raise studio_setup.SetupError("FFmpeg giải nén không đúng bản đã ghim (SHA-256/CRC/cỡ).")
    except BaseException:
        if target.exists():
            os.remove(target.resolve())
        raise
