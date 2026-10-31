# Decision only: never deletes files. Inputs are data in environment variables.
# Logic of shell/src-tauri/windows/uninstall_guard.ps1, plus: a reparse point anywhere INSIDE the target refuses too. NSIS
# RMDir /r follows junctions, so a junction below the data folder would empty a folder outside it (test_installer.py, 31-10).
# Exit: 0 delete, 3 the saved library lies in the target, 4 unknown (unreadable settings, reparse point): preserve data.
$ErrorActionPreference = 'Stop'
try {
    function Canonical([string] $path) {
        $full = [IO.Path]::GetFullPath($path).TrimEnd('\', '/')
        # Reject reparse points rather than guess the destination of junctions.
        $cursor = $full
        while ($cursor) {
            if (Test-Path -LiteralPath $cursor) {
                $entry = Get-Item -LiteralPath $cursor -Force
                if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'reparse point' }
            }
            $parent = [IO.Path]::GetDirectoryName($cursor)
            if ($parent -eq $cursor) { break }
            $cursor = $parent
        }
        return $full
    }
    $prefs = $env:ABOOK_PREFERENCES
    if (-not $prefs) { $prefs = Join-Path $env:LOCALAPPDATA 'ABook\preferences.json' }
    $target = Canonical $env:ABOOK_DELETE_TARGET
    if (Test-Path -LiteralPath $prefs) {
        $data = Get-Content -LiteralPath $prefs -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not ($data -is [pscustomobject])) { throw 'invalid preferences' }
        if ($data.libraryRoot) {
            if (-not ($data.libraryRoot -is [string])) { throw 'invalid libraryRoot' }
            $library = Canonical $data.libraryRoot
            if ($library.Equals($target, [StringComparison]::OrdinalIgnoreCase) -or
                $library.StartsWith($target + '\', [StringComparison]::OrdinalIgnoreCase)) { exit 3 }
        }
    }
    # Walk the target without ever entering a reparse point: the first one found refuses.
    if (Test-Path -LiteralPath $target -PathType Container) {
        $pending = New-Object System.Collections.Generic.Stack[IO.DirectoryInfo]
        $pending.Push([IO.DirectoryInfo]::new($target))
        while ($pending.Count) {
            foreach ($entry in $pending.Pop().EnumerateFileSystemInfos()) {
                if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'reparse point inside' }
                if ($entry -is [IO.DirectoryInfo]) { $pending.Push($entry) }
            }
        }
    }
    exit 0
} catch { exit 4 } # Unknown location: preserve data.
