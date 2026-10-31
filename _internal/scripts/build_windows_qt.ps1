<#
Đóng gói app máy tính Qt (desktop_qt) thành thư mục như bản cài (docs/QT_INSTALLER.md Q1): dist\ của build.bat +
dist\resources\{python,app} (cùng Python nhúng, cùng mã app với bộ cài Tauri - scripts/windows_resources.ps1), rồi chạy
thử bản đóng gói ở một thư mục không có cây mã nguồn bên trên (desktop_qt/tools/smoke_packaged.py).

    desktop_qt\build.bat package
    desktop_qt\build.bat installer
    powershell -ExecutionPolicy Bypass -File scripts\build_windows_qt.ps1 [-SkipUi] [-SkipResources] [-Installer] [-Dist <thư mục>]

Cần dist\ABookDesk.exe của desktop_qt\build.bat trước. -SkipUi: dùng bản dựng giao diện đang có trong abook\webui\static.
-SkipResources: giữ dist\resources đã dựng, chỉ chạy thử.
-Installer (Q2): thử bộ cài trong hồ sơ giả + gốc registry test (desktop_qt/tools/test_installer.py), rồi dựng
desktop_qt\build\installer\ABook_<ver>_x64-setup.exe (phiên bản của ui\package.json), ký .sig bằng khoá cập nhật của bản Tauri
(%USERPROFILE%\.abook-keys\updater.key, `tauri signer sign`), kiểm chữ ký bằng khoá công khai, và ghi latest.json.
#>
param(
    [switch]$SkipUi,
    [switch]$SkipResources,
    [switch]$Installer,
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
# Bộ cài Qt chở mã app dạng .py và biên dịch lúc cài (installer\abook.nsi): .pyc của Copy-App và của các lượt thử ở trên
# nặng 2,6 MB trong bộ cài. Các lượt chạy thử dưới đây chạy đúng thứ được chở đi.
Get-ChildItem (Join-Path $Resources "app") -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

Step "Chạy thử bản đóng gói (không có cây mã nguồn bên trên)"
$python = Get-BuildPython
# Mọi DLL mà exe/dll/pyd của gói cần phải đi kèm gói hay có sẵn trong Windows (máy dựng có sẵn VC++ nên chạy thử không thấy)
Invoke-Checked { & $python -X utf8 (Join-Path $Qt "tools\check_imports.py") $Dist } "check_imports"
Invoke-Checked { & $python -X utf8 (Join-Path $Qt "tools\smoke_packaged.py") $Dist } "smoke_packaged"
Write-Host ("   {0}: {1} MB" -f $Dist, (Get-SizeMB $Dist))
if (-not $Installer) { return }

$version = (Get-Content (Join-Path $Internal "ui\package.json") -Raw -Encoding UTF8 | ConvertFrom-Json).version
Step "Thử bộ cài $version (hồ sơ giả, gốc registry test)"
Invoke-Checked { & $python -X utf8 (Join-Path $Qt "tools\test_installer.py") $Dist --version $version } "test_installer"

Step "Bộ cài NSIS $version"
$out = Join-Path $Qt "build\installer"
New-Item -ItemType Directory -Force $out | Out-Null
$files = Join-Path $Cache "installer-files"
Invoke-Checked { & $python -X utf8 (Join-Path $Qt "installer\files.py") $Dist $files } "files.py"
# makensis cảnh báo 9000 với tên "setup.exe" (Windows nạp shim tương thích): dựng dưới tên trung tính rồi đổi, như Tauri.
$built = Join-Path $out "abook-installer.exe"
$makensis = Join-Path $env:LOCALAPPDATA "tauri\NSIS\makensis.exe"
Invoke-Checked { & $makensis /V2 /WX "/DVERSION=$version" "/DVERSIONWITHBUILD=$version.0" "/DABOOK_DIST=$Dist" "/DABOOK_FILES=$files" "/DOUTFILE=$built" (Join-Path $Qt "installer\abook.nsi") } "makensis"
$setup = Join-Path $out "ABook_${version}_x64-setup.exe"
Move-Item -Force $built $setup

Step "Chữ ký cập nhật"
$signingKey = Join-Path $env:USERPROFILE ".abook-keys\updater.key"
if (-not (Test-Path $signingKey)) { throw "Thiếu khoá ký cập nhật $signingKey" }
Push-Location (Join-Path $Internal "shell")
try {
    if (-not (Test-Path "node_modules")) { Invoke-Checked { npm ci --no-audit --no-fund } "npm ci (shell)" }
    $env:TAURI_SIGNING_PRIVATE_KEY = [System.IO.File]::ReadAllText($signingKey)
    # Khoá không mật khẩu. PowerShell 5.1 bỏ đối số rỗng khi gọi chương trình ngoài, nên viết '""'. --app-version: trusted
    # comment mang "version:<ver>" như chữ ký của `tauri bundle`, để chữ ký của bản này không dùng được cho bộ cài bản khác.
    Invoke-Checked { npx tauri signer sign --password '""' --app-version $version $setup } "tauri signer sign"
} finally {
    Pop-Location
    Remove-Item Env:TAURI_SIGNING_PRIVATE_KEY -ErrorAction SilentlyContinue
}
Invoke-Checked { & $python -X utf8 (Join-Path $Qt "installer\minisign_verify.py") $setup --version $version } "kiểm chữ ký"
Write-LatestJson (Get-Item $setup)
Get-ChildItem $out | Where-Object { $_.Name -like "ABook_${version}_x64-setup*" -or $_.Name -eq "latest.json" } | ForEach-Object {
    Write-Host ("   {0}  {1:N1} MB" -f $_.FullName, ($_.Length / 1MB))
}
