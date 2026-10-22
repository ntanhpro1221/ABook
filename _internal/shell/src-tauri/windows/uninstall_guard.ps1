# Decision only: never deletes files. Inputs are data in environment variables.
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
    exit 0
} catch { exit 4 } # Unknown location: preserve data.
