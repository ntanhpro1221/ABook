param([switch] $Find, [int] $GraceSeconds = 0)
# Stop every process started FROM the installed app: exactly $env:ABOOK_STOP_EXE, or any executable under
# $env:ABOOK_STOP_ROOT. Matched by executable path, never by name, so a pythonw.exe elsewhere is untouched.
# Spares itself and its parent (the uninstaller runs in place with _?= when a newer installer calls it).
# Logic of shell/src-tauri/windows/stop_processes.ps1 plus the exact exe and -Find.
# Exit: 0 nothing left running, 3 (-Find) something is running, 4 error.
$ErrorActionPreference = 'Stop'
try {
    if (-not $env:ABOOK_STOP_ROOT) { throw 'missing root' }
    $root = [IO.Path]::GetFullPath($env:ABOOK_STOP_ROOT).TrimEnd('\', '/') + '\'
    $exe = if ($env:ABOOK_STOP_EXE) { [IO.Path]::GetFullPath($env:ABOOK_STOP_EXE) } else { $null }
    $parent = (Get-CimInstance Win32_Process -Filter ('ProcessId=' + $PID)).ParentProcessId
    $processes = @(Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $PID -and $_.ProcessId -ne $parent -and $_.ExecutablePath -and (
            $_.ExecutablePath.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) -or
            ($exe -and $_.ExecutablePath.Equals($exe, [StringComparison]::OrdinalIgnoreCase)))
    })
    if ($Find) { if ($processes.Count) { exit 3 } else { exit 0 } }
    # -GraceSeconds (cập nhật từ trong app): app vừa chạy bộ cài rồi tự tắt, host còn đang ghi nốt - chờ nó thoát êm,
    # chỉ dừng cứng những gì còn chạy khi hết hạn.
    $deadline = [DateTime]::UtcNow.AddSeconds($GraceSeconds)
    while ([DateTime]::UtcNow -lt $deadline -and @($processes | Where-Object {
            $current = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $_.ProcessId)
            $current -and $current.CreationDate -eq $_.CreationDate }).Count) {
        Start-Sleep -Milliseconds 250
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
