"""Nhạc của tôi: nhạc người dùng tự nhập, dùng làm nhạc nền ngoài danh mục trên mây (docs/MUSIC_IMPORT.md).

Kho nhạc là của TỪNG MÁY (thư mục dữ liệu của app, không nằm trong sách): mỗi file chép vào `files/<sha1 nội dung>.<đuôi>`
(nhập hai lần cùng một file thì chỉ một bản), kèm sổ `library.json` ghi tên bài, nghệ sĩ, độ dài, độ to và - khi đã phân tích -
không khí của bài. Link của bài là `local:<sha1>` (music_plan.LOCAL_PREFIX), ở mọi chỗ nhận link danh mục.

Nhập nhạc KHÔNG cần mô-đun "Phân tích nhạc" (docs/MUSIC_IMPORT.md): độ dài + thẻ đọc bằng mutagen (thuần Python, có sẵn trong bộ cài), phát
và đóng gói vào .abook dùng nguyên file. Chưa có mô-đun thì bài chưa có độ to đo (app dùng mức mặc định) và chưa phân tích; có
mô-đun rồi (`measure_missing`, `analyze_pending`) thì bù cả hai.

Phân tích: `analyze(path)` trả mục theo hình danh mục (valence, arousal, tension, sd, vetVar, emotions, confidence,
fitsUnderNarration, loudness) hay None. Model nghe chỉ-âm-thanh (music_student.py) cắm vào qua `set_analyzer`; khi chưa có gói
model hay thư viện, `analyze` trả None và bài ở trạng thái "chưa phân tích": KHÔNG BAO GIỜ bịa số. Bài chưa phân tích không bao giờ được
máy tự chọn nhưng ghim tay được; bài đã phân tích vào danh sách ứng viên tự động như bài danh mục (music_select không đổi), trừ bài có vẻ có lời
hát (`vocalsLikely`): lời át chữ đọc nên máy không tự chọn, người dùng ghim tay hay bấm "Vẫn dùng làm nhạc nền" (`vocalsOk`) thì vẫn dùng.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Callable

from ..io_utils import atomic_write_json
from . import music_catalog, music_plan, music_scenes

INDEX_FILE = "library.json"
INDEX_VERSION = 1
MAX_TRACK_BYTES = 1 << 30  # 1 GiB: một bản nhạc dài hơn thế không phải nhạc nền
_TAG_MAX = 200
_CHUNK = 1 << 20


class MusicImportError(Exception):
    """Một file không nhập được. Câu chữ để người dùng đọc (tên file + lý do)."""


# ---- phân tích ----------------------------------------------------------------------------------------------------------
_analyzer: Callable[[Path], dict[str, Any] | None] | None = None


def set_analyzer(analyzer: Callable[[Path], dict[str, Any] | None] | None) -> None:
    """Cắm bộ phân tích âm thanh (model chỉ-nghe của phiên Nhạc); None = gỡ."""
    global _analyzer
    _analyzer = analyzer


_analyzer_id: str = ""


def set_analyzer_id(identifier: str) -> None:
    """Mã của bản model đang cắm (music_student.model_id): ghi cạnh mỗi kết quả phân tích để biết bài nào do bản cũ phân tích."""
    global _analyzer_id
    _analyzer_id = identifier


def analyzer_id() -> str:
    return _analyzer_id


def analyzer_available() -> bool:
    return _analyzer is not None


def analyze(path: Path) -> dict[str, Any] | None:
    """Mục theo hình danh mục cho file nhạc ở `path` (đã làm sạch bằng `clean_analysis`), hay None khi chưa có bộ phân tích
    hoặc nó không cho ra kết quả dùng được - khi đó bài là "chưa phân tích"."""
    if _analyzer is None:
        return None
    try:
        return clean_analysis(_analyzer(Path(path)))
    except Exception:  # noqa: BLE001 - model lỗi thì bài chưa phân tích, không làm hỏng việc nhập
        return None


def _finite(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def clean_analysis(result: Any) -> dict[str, Any] | None:
    """Kết quả của bộ phân tích -> khoá của một bài danh mục: valence / arousal (bắt buộc, kẹp -1..1), tension, sd, vetVar
    (phương sai dư của bộ đoán từng trục, >= 0: music_select cộng vào khoảng cách), emotions (13 cường độ 0..1), confidence, `fitsUnderNarration` -> `background`, `loudness` (số LUFS hay {lufs, speechBand}) ->
    lufs / speechBand, `vocals` (0..1) + `vocalsLikely` (bool, đầu dò lời hát - bài có vẻ có lời không được máy TỰ chọn), family / style nếu có. Thiếu valence hoặc arousal -> None (không điền số nào thay bộ phân tích)."""
    if not isinstance(result, dict):
        return None
    valence, arousal = _finite(result.get("valence")), _finite(result.get("arousal"))
    if valence is None or arousal is None:
        return None
    out: dict[str, Any] = {"valence": _clip(valence, -1.0, 1.0), "arousal": _clip(arousal, -1.0, 1.0)}
    tension = _finite(result.get("tension"))
    if tension is not None:
        out["tension"] = tension
    sd = result.get("sd")
    if isinstance(sd, dict):
        kept = {axis: max(0.0, number) for axis, value in sd.items() if (number := _finite(value)) is not None}
        if kept:
            out["sd"] = kept
    vet_var = result.get("vetVar")
    if isinstance(vet_var, dict):
        kept = {axis: max(0.0, number) for axis, value in vet_var.items() if (number := _finite(value)) is not None}
        if kept:
            out["vetVar"] = kept
    emotions = result.get("emotions")
    if isinstance(emotions, dict):
        kept = {name: _clip(number, 0.0, 1.0) for name in music_scenes.EMOTION_CLASSES
                if (number := _finite(emotions.get(name))) is not None}
        if kept:
            out["emotions"] = kept
    for source, target in (("confidence", "confidence"), ("fitsUnderNarration", "background")):
        number = _finite(result.get(source))
        if number is not None:
            out[target] = _clip(number, 0.0, 1.0)
    loudness = result.get("loudness")
    lufs = _finite(loudness.get("lufs") if isinstance(loudness, dict) else loudness)
    band = _finite(loudness.get("speechBand") if isinstance(loudness, dict) else result.get("speechBand"))
    if lufs is not None:
        out["lufs"] = lufs
    if band is not None:
        out["speechBand"] = band
    vocals = _finite(result.get("vocals"))
    if vocals is not None:
        out["vocals"] = _clip(vocals, 0.0, 1.0)
    if isinstance(result.get("vocalsLikely"), bool):
        out["vocalsLikely"] = result["vocalsLikely"]
    for key in ("family", "style"):
        if isinstance(result.get(key), str) and result[key]:
            out[key] = result[key]
    if out.get("family") not in (None, *music_plan.FAMILIES):
        del out["family"]
    return out


def auto_excluded(info: dict[str, Any]) -> bool:
    """Bài nhập này bị loại khỏi danh sách TỰ chọn vì có vẻ có lời hát và người dùng chưa cho phép."""
    return bool(info.get("vocalsLikely")) and not info.get("vocalsOk")


# ---- đọc file ------------------------------------------------------------------------------------------------------------
def read_tags(path: Path) -> dict[str, Any]:
    """Đọc file nhạc bằng tinytag (thuần Python, MIT, chép vào gói ở abook/vendor/tinytag - KHÔNG cần ffmpeg): {duration (giây), title, artist, album,
    genre}. Thẻ có thể thiếu (key vắng). Hỗ trợ cả sáu đuôi app nhận (mp3, m4a, ogg, opus, flac, wav). Không đọc được như âm thanh hay không có
    độ dài -> MusicImportError."""
    from ..vendor.tinytag import TinyTag

    try:
        tag = TinyTag.get(str(path))
    except Exception as exc:  # tinytag ném nhiều loại lỗi tuỳ định dạng hỏng ở chỗ nào
        raise MusicImportError("không đọc được như một bản nhạc") from exc
    if not tag.samplerate and not tag.duration:
        raise MusicImportError("không đọc được như một bản nhạc")
    duration = float(tag.duration or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise MusicImportError("không biết bài dài bao lâu")
    out: dict[str, Any] = {"duration": round(duration, 2)}
    for key in ("title", "artist", "album", "genre"):
        text = str(getattr(tag, key, None) or "").strip()
        if text:
            out[key] = text[:_TAG_MAX]
    return out


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


# ---- kho nhạc ------------------------------------------------------------------------------------------------------------
class LocalMusic:
    """Kho "Nhạc của tôi" của máy này. `carried`: thư mục bộ đệm nhạc, nơi file của sách mở từ `.abookproj` được chép vào
    (projectfile.copy_music) - bài người khác ghim vẫn phát được dù không nằm trong kho của máy này."""

    def __init__(self, root: Path, carried: Path | None = None) -> None:
        self.root = Path(root)
        self.carried = Path(carried) if carried is not None else None
        self._lock = threading.RLock()
        self._index: dict[str, dict[str, Any]] | None = None

    # -- sổ ---------------------------------------------------------------------------------------------------------------
    def _tracks(self) -> dict[str, dict[str, Any]]:
        if self._index is None:
            try:
                data = json.loads((self.root / INDEX_FILE).read_text(encoding="utf-8"))
                found = data.get("tracks") if isinstance(data, dict) and data.get("version") == INDEX_VERSION else None
            except (OSError, ValueError):
                found = None
            self._index = {digest: entry for digest, entry in (found or {}).items()
                           if re.fullmatch(r"[0-9a-f]{40}", digest) and isinstance(entry, dict)}
        return self._index

    def _save(self) -> None:
        atomic_write_json(self.root / INDEX_FILE, {"version": INDEX_VERSION, "tracks": self._tracks()})

    def _path(self, digest: str, entry: dict[str, Any]) -> Path:
        return self.root / "files" / f"{digest}.{entry.get('ext', 'mp3')}"

    # -- đọc --------------------------------------------------------------------------------------------------------------
    @staticmethod
    def link(digest: str) -> str:
        return music_plan.LOCAL_PREFIX + digest

    def info(self, digest: str, entry: dict[str, Any]) -> dict[str, Any]:
        """Một bài theo hình danh mục (kèm khoá giao diện): link, title, creator, duration, source "local", lufs, và các khoá của
        phân tích nếu đã có. `analysed` cho giao diện; `name` là tên file gốc."""
        info: dict[str, Any] = {"link": self.link(digest), "title": entry.get("title") or Path(entry.get("name", "")).stem or "Bài nhạc",
                                "creator": entry.get("artist") or "", "duration": round(entry.get("duration") or 0),
                                "source": "local", "analysed": bool(entry.get("analysis")), "name": entry.get("name") or "",
                                "bytes": entry.get("bytes") or 0, "added": entry.get("added") or 0}
        for key in ("album", "genre"):
            if entry.get(key):
                info[key] = entry[key]
        if entry.get("lufs") is not None:
            info["lufs"] = entry["lufs"]
        info.update(entry.get("analysis") or {})
        if entry.get("vocalsOk"):
            info["vocalsOk"] = True  # người dùng bấm "Vẫn dùng làm nhạc nền": máy được tự chọn dù đầu dò báo có lời
        if entry.get("lufs") is not None:
            info["lufs"] = entry["lufs"]  # số đo từ chính file thắng số của bộ phân tích
        return info

    def entries(self) -> list[dict[str, Any]]:
        """Mọi bài trong kho, mới nhập trước."""
        with self._lock:
            return sorted((self.info(digest, entry) for digest, entry in self._tracks().items()),
                          key=lambda info: (-float(info["added"]), info["title"].lower()))

    def lookup(self, links: list[str]) -> dict[str, dict[str, Any]]:
        """Thông tin của các link `local:` có trong kho (link khác / không có thì vắng)."""
        with self._lock:
            tracks = self._tracks()
            found = {}
            for link in links:
                digest = music_plan.local_hash(link)
                if digest is not None and digest in tracks:
                    found[link] = self.info(digest, tracks[digest])
            return found

    def file(self, link: str) -> Path | None:
        """File của bài: trong kho, không thì trong bộ đệm nhạc (bài sách mang theo). Không có -> None."""
        digest = music_plan.local_hash(link)
        if digest is None:
            return None
        with self._lock:
            entry = self._tracks().get(digest)
            if entry is not None:
                path = self._path(digest, entry)
                if path.is_file():
                    return path
        if self.carried is not None:
            for extension in music_plan.TRACK_EXTENSIONS:
                path = self.carried / f"{digest}.{extension}"
                if path.is_file():
                    return path
        return None

    def near(self, valence: float, arousal: float, radius: int = 1, grid: int = 5) -> list[dict[str, Any]]:
        """Ứng viên tự động quanh (valence, arousal), như `MusicCatalog.near`: chỉ bài ĐÃ phân tích (có không khí) và còn file. Bài có vẻ
        có lời hát (`vocalsLikely`) không được máy tự chọn (lời át chữ đọc) trừ khi người dùng bấm "Vẫn dùng làm nhạc nền" (`vocalsOk`);
        ghim tay không đi qua đây nên vẫn dùng được."""
        wanted_v, wanted_a = music_catalog.cell_of(valence, arousal, grid)
        out = []
        for info in self.entries():
            if not info["analysed"] or self.file(info["link"]) is None or auto_excluded(info):
                continue
            v, a = music_catalog.cell_of(float(info["valence"]), float(info["arousal"]), grid)
            if abs(v - wanted_v) <= radius and abs(a - wanted_a) <= radius:
                out.append(info)
        return out

    # -- ghi --------------------------------------------------------------------------------------------------------------
    def set_vocals_ok(self, digest: str, ok: bool) -> bool:
        """Người dùng bấm (hay bỏ) "Vẫn dùng làm nhạc nền" cho một bài có vẻ có lời: cờ `vocalsOk` ở mục của bài trong sổ (không nằm trong
        `analysis` nên phân tích lại không làm mất). False nếu bài không còn trong kho."""
        with self._lock:
            entry = self._tracks().get(digest)
            if entry is None:
                return False
            if ok:
                entry["vocalsOk"] = True
            else:
                entry.pop("vocalsOk", None)
            self._save()
            return True

    def import_file(self, source: Path, fallback: dict[str, str] | None = None) -> tuple[dict[str, Any], bool]:
        """Nhập một file: kiểm đuôi và đọc được như âm thanh, chép vào kho theo mã sha1 nội dung, đo độ to, phân tích nếu có bộ
        phân tích. Trả (thông tin bài, đã có sẵn trong kho?). File trùng nội dung với bài đã có thì không chép lại.
        `fallback` {"title", "artist"}: tên bài / nghệ sĩ dùng khi thẻ trong file không có (bài mang theo trong file sách)."""
        source = Path(source)
        extension = source.suffix.lower().lstrip(".")
        if not source.is_file():
            raise MusicImportError(f"“{source.name}”: không thấy file này.")
        if extension not in music_plan.TRACK_EXTENSIONS:
            raise MusicImportError(f"“{source.name}”: chưa nhập được định dạng này - dùng {', '.join('.' + e for e in music_plan.TRACK_EXTENSIONS)}.")
        if source.stat().st_size > MAX_TRACK_BYTES:
            raise MusicImportError(f"“{source.name}”: file quá lớn để làm nhạc nền (tối đa 1 GB).")
        digest = _sha1(source)
        with self._lock:
            known = self._tracks().get(digest)
            if known is not None and self._path(digest, known).is_file():
                return self.info(digest, known), True
            try:
                tags = read_tags(source)
            except MusicImportError as exc:
                raise MusicImportError(f"“{source.name}”: {exc}.") from exc
            target = self.root / "files" / f"{digest}.{extension}"
            target.parent.mkdir(parents=True, exist_ok=True)
            part = target.with_name(f".{target.name}.{secrets.token_hex(4)}.part")
            try:
                shutil.copyfile(source, part)
                os.replace(part, target)
            except OSError as exc:
                raise MusicImportError(f"“{source.name}”: không chép được vào kho nhạc ({exc.strerror or exc}).") from exc
            finally:
                with contextlib.suppress(OSError):
                    part.unlink(missing_ok=True)
            entry: dict[str, Any] = {"ext": extension, "name": source.name, "bytes": target.stat().st_size,
                                     "added": time.time(), "duration": tags["duration"],
                                     "title": tags.get("title") or (fallback or {}).get("title") or "",
                                     "artist": tags.get("artist") or (fallback or {}).get("artist") or "", "album": tags.get("album") or "",
                                     "genre": tags.get("genre") or "", "analysis": None, "lufs": None}
            entry["lufs"] = music_plan.measured_lufs(target)  # độ to thật của file - cue_gain_db dùng; chưa có ffmpeg thì None (mức mặc định)
            entry["analysis"] = analyze(target)
            if entry["analysis"]:
                entry["by"] = analyzer_id()
            self._tracks()[digest] = entry
            self._save()
            return self.info(digest, entry), False

    def remove(self, digest: str) -> bool:
        """Xoá một bài khỏi kho (file + số đo cạnh nó). Sách đã đóng gói / xuất vẫn mang bản của nó; đoạn đang ghim bài này
        trên máy này sẽ chọn bài khác (bài không còn dùng được)."""
        with self._lock:
            entry = self._tracks().pop(digest, None)
            if entry is None:
                return False
            self._save()
            path = self._path(digest, entry)
            for leftover in (path, path.with_suffix(music_plan.LUFS_SIDECAR)):
                with contextlib.suppress(OSError):
                    leftover.unlink(missing_ok=True)
            return True

    def analyze_pending(self) -> int:
        """Phân tích các bài chưa phân tích (khi bộ phân tích có mặt hay vừa cập nhật). Trả số bài vừa được phân tích."""
        done = 0
        with self._lock:
            for digest, entry in self._tracks().items():
                path = self._path(digest, entry)
                if entry.get("analysis") or not path.is_file():
                    continue
                result = analyze(path)
                if result is not None:
                    entry["analysis"] = result
                    entry["by"] = analyzer_id()
                    done += 1
            if done:
                self._save()
        return done

    def valence_pending(self, version: str) -> list[tuple[str, Path]]:
        """(mã, file) các bài đã phân tích mà valence chưa phải V hợp bản `version` (music_valence): bài mới nhập, bài vừa phân tích lại (mục mới thay
        mục cũ nên mất dấu `valenceBy`) và bài đo bằng bản V hợp cũ hơn."""
        with self._lock:
            return [(digest, path) for digest, entry in self._tracks().items()
                    if isinstance(entry.get("analysis"), dict) and entry["analysis"].get("valenceBy") != version
                    and (path := self._path(digest, entry)).is_file()]

    def set_valence(self, digest: str, valence: float, by: str) -> bool:
        """Ghi V hợp đè lên valence của trò và đánh dấu nguồn (`analysis["valenceBy"]`). V hợp cùng thang với danh mục nên không còn `vetVar.valence`
        (các trục khác giữ). False nếu bài đã bị xoá hay không còn mục phân tích."""
        with self._lock:
            entry = self._tracks().get(digest)
            analysis = entry.get("analysis") if entry is not None else None
            if not isinstance(analysis, dict):
                return False
            analysis["valence"], analysis["valenceBy"] = _clip(float(valence), -1.0, 1.0), by
            if isinstance(analysis.get("vetVar"), dict):
                analysis["vetVar"].pop("valence", None)
                if not analysis["vetVar"]:
                    del analysis["vetVar"]
            self._save()
            return True

    def stale_count(self) -> int:
        """Số bài đã phân tích bằng một bản model khác bản đang cắm (mới cập nhật): kết quả cũ vẫn dùng được, người dùng tự quyết có phân
        tích lại không (`reanalyse`) - không bao giờ tự chạy."""
        if _analyzer is None or not _analyzer_id:
            return 0
        with self._lock:
            return sum(1 for entry in self._tracks().values() if entry.get("analysis") and entry.get("by") != _analyzer_id)

    def reanalyse(self) -> int:
        """Phân tích lại các bài `stale_count` đếm bằng bản model đang cắm. Không phân tích được bài nào thì giữ kết quả cũ của nó."""
        if _analyzer is None or not _analyzer_id:
            return 0
        done = 0
        with self._lock:
            for digest, entry in self._tracks().items():
                path = self._path(digest, entry)
                if not entry.get("analysis") or entry.get("by") == _analyzer_id or not path.is_file():
                    continue
                result = analyze(path)
                if result is not None:
                    entry["analysis"], entry["by"] = result, _analyzer_id
                    done += 1
            if done:
                self._save()
        return done

    def measure_missing(self) -> int:
        """Đo độ to các bài nhập lúc máy chưa có ffmpeg (mô-đun "Phân tích nhạc" vừa tải xong). Trả số bài vừa có số đo."""
        done = 0
        with self._lock:
            for digest, entry in self._tracks().items():
                path = self._path(digest, entry)
                if entry.get("lufs") is not None or not path.is_file():
                    continue
                value = music_plan.measured_lufs(path)
                if value is not None:
                    entry["lufs"] = value
                    done += 1
            if done:
                self._save()
        return done
