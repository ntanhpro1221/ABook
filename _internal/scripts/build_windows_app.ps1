<#
Dựng bộ cài app Windows ABook (docs/PACKAGING.md):
  giao diện (ui/) -> Python nhúng (kiểm SHA-256) -> gói phụ (--require-hashes) -> mã abook -> chạy thử host
  bằng chính Python nhúng -> cargo tauri build (bộ cài NSIS + chữ ký cập nhật).

    powershell -ExecutionPolicy Bypass -File scripts\build_windows_app.ps1 [-SkipUi] [-SkipBundle] [-SkipResources]

-SkipUi: dùng bản dựng giao diện đang có trong abook\webui\static. -SkipBundle: chỉ dựng thư mục tài nguyên và
chạy thử host (không gọi Tauri). -SkipResources: giữ thư mục tài nguyên đã dựng (dựng lại vỏ/bộ cài nhanh). -TauriConfig:
file JSON gộp đè tauri.conf.json cho riêng lần dựng này (bản thử cập nhật: số phiên bản khác, endpoint http cục bộ) -
không bao giờ dùng cho bản phát hành. Bộ cài + chữ ký cập nhật (.sig) ra shell\src-tauri\target\release\bundle\nsis\.

Khoá ký cập nhật: %USERPROFILE%\.abook-keys\updater.key (sinh bằng `npx tauri signer generate`, NGOÀI repo, không in
ra). Mất khoá = các bản đã cài không tự cập nhật được nữa.
#>
param(
    [switch]$SkipUi,
    [switch]$SkipBundle,
    [switch]$SkipResources,
    [string]$TauriConfig = ""
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # Invoke-WebRequest vẽ thanh tiến độ chậm hơn tải hàng chục lần

$Internal = Split-Path -Parent $PSScriptRoot
$Shell = Join-Path $Internal "shell"
$Tauri = Join-Path $Shell "src-tauri"
$Resources = Join-Path $Tauri "resources"
$Cache = Join-Path $Tauri "target\download-cache"
$SigningKey = Join-Path $env:USERPROFILE ".abook-keys\updater.key"

. (Join-Path $PSScriptRoot "windows_resources.ps1")

function Build-Bundle {
    Step "Tauri build (NSIS + chữ ký cập nhật)"
    if (-not (Test-Path $SigningKey)) { throw "Thiếu khoá ký cập nhật $SigningKey (npx tauri signer generate --ci -w ...)" }
    $env:TAURI_SIGNING_PRIVATE_KEY = [System.IO.File]::ReadAllText($SigningKey)
    $env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = ""
    $env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
    Push-Location $Shell
    try {
        if (-not (Test-Path "node_modules")) { Invoke-Checked { npm ci --no-audit --no-fund } "npm ci (shell)" }
        $config = @()
        if ($TauriConfig) {
            if (-not (Test-Path $TauriConfig)) { throw "Không thấy file cấu hình $TauriConfig" }
            $config = @("--config", (Resolve-Path $TauriConfig).Path)
        }
        # Dựng exe và đóng gói là HAI bước: bước đóng gói ghi ngay vào exe vừa dựng ("Patching ... with bundle type
        # information") và hỏng "file đang bị tiến trình khác dùng" (os error 32) khi trình diệt virus còn đang quét file
        # mới. 28-09: `tauri build` thử lại 3 lần hỏng cả 3 - mỗi lần thử lại dựng lại exe nên lần nào cũng đụng đúng lúc
        # quét. Giờ: dựng một lần, chờ tới khi không ai giữ exe, rồi mới đóng gói; hỏng thì chỉ thử lại bước đóng gói.
        Invoke-Checked { npx tauri build --no-bundle @config } "tauri build --no-bundle"
        $exe = Join-Path $Tauri "target\release\ABook.exe"
        for ($attempt = 1; ; $attempt++) {
            Wait-Unlocked $exe
            & npx tauri bundle --bundles nsis @config
            if ($LASTEXITCODE -eq 0) { break }
            if ($attempt -ge 5) { throw "tauri bundle thất bại (mã $LASTEXITCODE) sau $attempt lần" }
            Write-Host "   tauri bundle hỏng (mã $LASTEXITCODE) - chờ exe rảnh rồi thử lại"
            Start-Sleep -Seconds 5
        }
    } finally {
        Pop-Location
        Remove-Item Env:TAURI_SIGNING_PRIVATE_KEY -ErrorAction SilentlyContinue
    }
    $nsis = Join-Path $Tauri "target\release\bundle\nsis"
    $setup = Get-ChildItem $nsis -Filter "ABook_*_x64-setup.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    Write-LatestJson $setup
    Get-ChildItem $nsis | Where-Object { $_.Name -like "$($setup.BaseName)*" -or $_.Name -eq "latest.json" } | ForEach-Object {
        Write-Host ("   {0}  {1:N1} MB" -f $_.FullName, ($_.Length / 1MB))
    }
}

if (-not $SkipResources) {
    if (-not $SkipUi) { Build-Ui }
    if (-not (Test-Path (Join-Path $Internal "abook\webui\static\index.html"))) {
        throw "Chưa có bản dựng giao diện (abook\webui\static) - bỏ -SkipUi"
    }
    Build-Python
    Copy-App
} elseif (-not (Test-Path (Join-Path $Resources "python\python.exe"))) {
    throw "Chưa có thư mục tài nguyên - bỏ -SkipResources"
}
Test-Host
if (-not $SkipBundle) { Build-Bundle }
