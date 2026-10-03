"""Giọng của chính máy Windows: Windows.Media.SpeechSynthesis (OneCore - nơi giọng tiếng Việt "An" của gói ngôn ngữ nằm), gọi qua một đoạn
PowerShell 5.1 (WinRT dùng được từ PowerShell, không cần thêm gói Python). Đoạn ấy ghi WAV và mốc từng chữ (`IncludeWordBoundaryMetadata`:
mỗi SpeechCue có giờ bắt đầu và vị trí ký tự trong chữ đem đọc; không có độ dài - một chữ kết thúc khi chữ sau bắt đầu).

Chạy ẩn (CREATE_NO_WINDOW, không nháy cửa sổ). Máy không có giọng vi-* thì danh sách rỗng (không đọc giọng khác ngôn ngữ). Chưa dùng SAPI5
(System.Speech) vì WinRT chạy được trên cả máy dev (đã thử với giọng en-US) - xem tests/test_readaloud.py.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
import wave
from pathlib import Path

from .mapping import Boundary
from .model import Synthesis, Voice, VoiceError

PREFIX = "device:"
TIMEOUT = 120.0

# Chỉ ASCII: PowerShell 5.1 đọc file .ps1 không có BOM theo bảng mã ANSI. Vào / ra bằng file JSON UTF-8.
SCRIPT = r"""param([string]$Request, [string]$Result)
$ErrorActionPreference = 'Stop'
$req = [IO.File]::ReadAllText($Request, [Text.Encoding]::UTF8) | ConvertFrom-Json
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]
$null = [Windows.Media.Core.SpeechCue, Windows.Media.Core, ContentType=WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $type) { $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op)); $null = $t.Wait(-1); $t.Result }
function Save($obj) { [IO.File]::WriteAllText($Result, (ConvertTo-Json -InputObject $obj -Compress -Depth 5), (New-Object Text.UTF8Encoding($false))) }
if ($req.mode -eq 'list') {
  $voices = @([Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | ForEach-Object { @{ id = $_.Id; name = $_.DisplayName; language = $_.Language } })
  Save @{ voices = $voices }
  exit 0
}
$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.Id -eq $req.voice } | Select-Object -First 1
if ($null -eq $voice) { Save @{ error = 'voice' }; exit 0 }
$synth.Voice = $voice
$synth.Options.IncludeWordBoundaryMetadata = $true
$stream = Await ($synth.SynthesizeTextToStreamAsync($req.text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
$cues = @()
foreach ($track in $stream.TimedMetadataTracks) {
  if ($track.Id -ne 'SpeechWord') { continue }
  foreach ($cue in $track.Cues) {
    $c = [Windows.Media.Core.SpeechCue]$cue
    $cues += @{ text = $c.Text; start = [int]$c.StartTime.TotalMilliseconds; char = $c.StartPositionInInput }
  }
}
$in = [IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream)
$ms = New-Object IO.MemoryStream
$in.CopyTo($ms)
[IO.File]::WriteAllBytes($req.out, $ms.ToArray())
Save @{ cues = $cues }
"""

_lock = threading.Lock()
_listed: list[Voice] | None = None


def available() -> bool:
    return os.name == "nt" and shutil.which("powershell.exe") is not None


def _run(folder: Path, request: dict) -> dict:
    """Chạy đoạn PowerShell với `request` (JSON), trả JSON nó ghi ra."""
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "windows-voice.ps1"
    if not script.is_file() or script.read_bytes() != SCRIPT.encode("ascii"):
        script.write_bytes(SCRIPT.encode("ascii"))
    with tempfile.TemporaryDirectory(dir=folder) as work:
        base = Path(work)
        request = {**request, "out": str(base / "out.wav")}
        (base / "request.json").write_bytes(json.dumps(request, ensure_ascii=False).encode("utf-8"))
        try:
            done = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script),
                 "-Request", str(base / "request.json"), "-Result", str(base / "result.json")],
                capture_output=True, timeout=TIMEOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as error:
            raise VoiceError("Giọng của máy đọc quá lâu.", "timeout") from error
        except OSError as error:
            raise VoiceError(f"Không chạy được PowerShell: {error}") from error
        result_file = base / "result.json"
        if done.returncode != 0 or not result_file.is_file():
            detail = done.stderr.decode("utf-8", "replace").strip().splitlines()
            raise VoiceError("Giọng của máy lỗi: " + (detail[0] if detail else f"mã {done.returncode}"))
        result = json.loads(result_file.read_bytes().decode("utf-8"))
        if isinstance(result, dict) and result.get("error") == "voice":
            raise VoiceError("Máy không còn giọng này.", "voice")
        wav = base / "out.wav"
        if wav.is_file():
            result["audio"] = wav.read_bytes()
        return result


def voices(folder: Path, *, language: str = "vi", refresh: bool = False) -> list[Voice]:
    """Giọng cài trên máy thuộc ngôn ngữ `language` ("vi" -> vi-VN...). Hỏi PowerShell một lần rồi nhớ."""
    global _listed
    if not available():
        return []
    with _lock:
        if _listed is None or refresh:
            try:
                raw = _run(folder, {"mode": "list"}).get("voices") or []
            except VoiceError:
                raw = []
            _listed = [Voice(PREFIX + item["id"], str(item["name"]).removeprefix("Microsoft ").strip(), "device", False, False,
                             str(item.get("language", "")))
                       for item in raw if str(item.get("language", "")).lower().startswith("vi-")]
        return [voice for voice in _listed if voice.language.lower().startswith(language.lower())]


def synthesize(folder: Path, native_id: str, text: str) -> Synthesis:
    """Đọc `text` bằng giọng `native_id` (mã Windows, không có tiền tố): WAV + các mảnh (một chữ kết thúc khi chữ sau bắt đầu)."""
    result = _run(folder, {"mode": "speak", "voice": native_id, "text": text})
    audio = result.get("audio")
    if not audio:
        raise VoiceError("Giọng của máy không trả về âm thanh.", "empty")
    with wave.open(io.BytesIO(audio)) as handle:
        duration = handle.getnframes() * 1000 // max(1, handle.getframerate())
    cues = result.get("cues") or []
    if isinstance(cues, dict):  # ConvertTo-Json bỏ mảng khi chỉ có một phần tử
        cues = [cues]
    pieces: list[Boundary] = []
    for index, cue in enumerate(cues):
        end = cues[index + 1]["start"] if index + 1 < len(cues) else duration
        pieces.append(Boundary(str(cue["text"]), int(cue["start"]), max(int(cue["start"]), int(end)),
                               cue.get("char") if isinstance(cue.get("char"), int) else None))
    return Synthesis(audio, pieces, duration, "wav", "audio/wav")
