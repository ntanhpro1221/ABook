param([switch] $ResolveOnly)
$ErrorActionPreference = 'Stop'
try {
    if (-not $env:ABOOK_STOP_ROOT) { throw 'missing root' }
    $root = [IO.Path]::GetFullPath($env:ABOOK_STOP_ROOT).TrimEnd('\', '/') + '\'
    if ($ResolveOnly) {
        [Console]::OutputEncoding = [Text.Encoding]::UTF8
        [Console]::Write($root)
        exit 0
    }
    $uninstaller = (Get-CimInstance Win32_Process -Filter ('ProcessId=' + $PID)).ParentProcessId
    $processes = Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $PID -and $_.ProcessId -ne $uninstaller -and $_.ExecutablePath -and
        $_.ExecutablePath.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)
    }
    foreach ($process in $processes) {
        $current = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $process.ProcessId)
        if ($current -and $current.CreationDate -eq $process.CreationDate -and $current.ExecutablePath -eq $process.ExecutablePath) {
            $stopped = Stop-Process -Id $process.ProcessId -Force -PassThru -ErrorAction Stop
            if ($stopped -and -not $stopped.WaitForExit(10000)) { throw 'process did not exit' }
        }
    }
    exit 0
} catch { exit 4 }
