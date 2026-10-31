<#
Đóng gói app máy tính Qt (desktop_qt) thành thư mục như bản cài (docs/QT_INSTALLER.md Q1): dist\ của build.bat +
dist\resources\{python,app} (cùng Python nhúng, cùng mã app với bộ cài Tauri - scripts/windows_resources.ps1), rồi chạy
thử bản đóng gói ở một thư mục không có cây mã nguồn bên trên (desktop_qt/tools/smoke_packaged.py).

    desktop_qt\build.bat package
    powershell -ExecutionPolicy Bypass -File scripts\build_windows_qt.ps1 [-SkipUi] [-SkipResources] [-Dist <thư mục>]

Cần dist\ABookDesk.exe của desktop_qt\build.bat trước. -SkipUi: dùng bản dựng giao diện đang có trong abook\webui\static.
-SkipResources: giữ dist\resources đã dựng, chỉ chạy thử.
#>
param(
    [switch]$SkipUi,
    [switch]$SkipResources,
    [string]$Dist = ""
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # Invoke-WebRequest vẽ thanh tiến độ chậm hơn tải hàng chục lần

$Internal = Split-Path -Parent $PSScriptRoot
$Qt = Join-Path $Internal "desktop_qt"
if (-not $Dist) { $Dist = Join-Path $Qt "dist" }
$Resources = Join-Path $Dist "resources"
$Cache = Join-Path $Qt "build\package-cache"

. (Join-Path $PSScriptRoot "windows_resources.ps1")

if (-not (Test-Path (Join-Path $Dist "ABookDesk.exe"))) { throw "Chưa có $Dist\ABookDesk.exe - chạy desktop_qt\build.bat trước" }
if (-not $SkipResources) {
    if (-not $SkipUi) { Build-Ui }
    if (-not (Test-Path (Join-Path $Internal "abook\webui\static\index.html"))) {
        throw "Chưa có bản dựng giao diện (abook\webui\static) - bỏ -SkipUi"
    }
    Build-Python
    Copy-App
} elseif (-not (Test-Path (Join-Path $Resources "python\python.exe"))) {
    throw "Chưa có $Resources - bỏ -SkipResources"
}
Test-Host

Step "Chạy thử bản đóng gói (không có cây mã nguồn bên trên)"
$python = Get-BuildPython
Invoke-Checked { & $python -X utf8 (Join-Path $Qt "tools\smoke_packaged.py") $Dist } "smoke_packaged"
Write-Host ("   {0}: {1} MB" -f $Dist, (Get-SizeMB $Dist))
