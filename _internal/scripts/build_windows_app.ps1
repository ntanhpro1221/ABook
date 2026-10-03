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

# Python nhúng: bản ổn định mới nhất còn bản vá nhị phân (server đồng bộ nghe cả mạng LAN). Nâng: đổi số + băm (tải về,
# Get-FileHash), dựng lại, chạy thử.
$PythonVersion = "3.14.7"
$PythonTag = "314"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$PythonSha256 = "d297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15"

function Step([string]$Text) { Write-Host "== $Text" -ForegroundColor Cyan }

function Invoke-Checked([scriptblock]$Command, [string]$Label) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Label thất bại (mã $LASTEXITCODE)" }
}

function Wait-Unlocked([string]$Path, [int]$Seconds = 300) {
    # Mở chỉ-đọc, KHÔNG chia sẻ: được nghĩa là không còn ai (trình diệt virus, bộ lập chỉ mục) mở file. Chỉ đọc để chính
    # phép thử không làm trình diệt virus quét lại (nó quét khi file mở-để-ghi được đóng).
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ($true) {
        try { [System.IO.File]::Open($Path, "Open", "Read", "None").Dispose(); return }
        catch {
            if ((Get-Date) -gt $deadline) { throw "Sau $Seconds giây $Path vẫn bị giữ: $($_.Exception.Message)" }
            Start-Sleep -Milliseconds 500
        }
    }
}

function Get-BuildPython {
    # Python của máy dựng chỉ để chạy pip (cài wheel cho Python nhúng, đúng nền tảng/phiên bản của nó).
    $runtime = Join-Path $Internal "runtime\.venv\Scripts\python.exe"
    if (Test-Path $runtime) { return $runtime }
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    throw "Cần một Python có pip trên máy dựng (runtime\.venv hay python trong PATH)"
}

function Build-Ui {
    Step "Dựng giao diện (ui/)"
    Push-Location (Join-Path $Internal "ui")
    try {
        if (-not (Test-Path "node_modules")) { Invoke-Checked { npm ci --no-audit --no-fund } "npm ci" }
        Invoke-Checked { npm run build } "npm run build"
    } finally { Pop-Location }
}

function Build-Python {
    Step "Python nhúng $PythonVersion"
    if (Test-Path $Resources) { Remove-Item $Resources -Recurse -Force }
    New-Item -ItemType Directory -Force $Cache | Out-Null
    $zip = Join-Path $Cache "python-$PythonVersion-embed-amd64.zip"
    if (-not (Test-Path $zip) -or (Get-FileHash $zip -Algorithm SHA256).Hash -ne $PythonSha256) {
        Invoke-WebRequest -UseBasicParsing -Uri $PythonUrl -OutFile "$zip.part"
        Move-Item "$zip.part" $zip -Force
    }
    $actual = (Get-FileHash $zip -Algorithm SHA256).Hash
    if ($actual -ne $PythonSha256) { throw "SHA-256 của Python nhúng không khớp: $actual" }
    $python = Join-Path $Resources "python"
    Expand-Archive -Path $zip -DestinationPath $python
    # sys.path của Python nhúng do file ._pth quyết định (PYTHONPATH bị bỏ qua): thư viện chuẩn, chính nó, mã app, gói
    # phụ. Không "import site": không có site-packages của người dùng lọt vào.
    $pth = @("python$PythonTag.zip", ".", "..\app", "Lib\site-packages") -join "`r`n"
    [System.IO.File]::WriteAllText((Join-Path $python "python$PythonTag._pth"), $pth + "`r`n")

    Step "Gói phụ (Pillow, psutil, requests) - chỉ đúng wheel đã ghi băm"
    $buildPython = Get-BuildPython
    Invoke-Checked {
        & $buildPython -m pip install --disable-pip-version-check --no-deps --no-compile --require-hashes `
            --only-binary=:all: --platform win_amd64 --python-version $PythonVersion --implementation cp `
            --target (Join-Path $python "Lib\site-packages") -r (Join-Path $Shell "python\requirements.txt")
    } "pip install"
}

function Copy-App {
    Step "Mã abook"
    $app = Join-Path $Resources "app"
    New-Item -ItemType Directory -Force $app | Out-Null
    # robocopy: mã thoát 0-7 là thành công.
    & robocopy (Join-Path $Internal "abook") (Join-Path $app "abook") /E /XD __pycache__ /XF *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy thất bại (mã $LASTEXITCODE)" }
    foreach ($file in @("pyproject.toml", "uv.lock", "LICENSE")) {
        $source = Join-Path $Internal $file
        if (Test-Path $source) { Copy-Item $source $app }
    }
    # Danh sách thư viện của Studio tải thêm (webui/studio_setup.py đọc ở thư mục app).
    Copy-Item (Join-Path $Shell "python\studio-requirements.txt") $app
    Copy-VcRuntime (Join-Path $app "vcruntime")
    Invoke-Checked { & (Join-Path $Resources "python\python.exe") -m compileall -q -j 0 (Join-Path $app "abook") } "compileall"
}

function Copy-VcRuntime([string]$Target) {
    # VC++ runtime app-local cho Studio (webui/studio_setup.py chép vào thư mục Python của Studio). Đo 28-09 trên Studio
    # cài thật: torch/onnxruntime... nạp msvcp140.dll, msvcp140_1.dll từ System32 - tức cần VC++ Redistributable, thứ
    # Windows sạch không có. Lấy đúng các file Microsoft cho phân phối lại (thư mục Redist của Visual Studio trên máy dựng).
    $vs = & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -products * -property installationPath | Select-Object -First 1
    $crt = Get-ChildItem (Join-Path $vs "VC\Redist\MSVC") -Directory | Sort-Object Name -Descending |
        ForEach-Object { Get-ChildItem (Join-Path $_.FullName "x64") -Directory -Filter "Microsoft.VC*.CRT" -ErrorAction SilentlyContinue } |
        Select-Object -First 1
    if (-not $crt) { throw "Không thấy VC++ runtime để phân phối lại (Visual Studio > VC\Redist\MSVC\<bản>\x64\Microsoft.VC*.CRT)" }
    New-Item -ItemType Directory -Force $Target | Out-Null
    # vccorlib140.dll là của C++/CX (UWP) - không thư viện nào của Studio dùng.
    Get-ChildItem $crt.FullName -Filter *.dll | Where-Object { $_.Name -ne "vccorlib140.dll" } | Copy-Item -Destination $Target
    Write-Host "   VC++ runtime: $($crt.FullName)"
}

function Test-Host {
    # Host chạy bằng chính Python nhúng, dữ liệu app tạm: báo sẵn sàng, trả /api/app, phục vụ trang, thoát khi ống đóng.
    Step "Chạy thử host"
    $smokeData = Join-Path $Cache "smoke"
    if (Test-Path $smokeData) { Remove-Item $smokeData -Recurse -Force }
    New-Item -ItemType Directory -Force $smokeData | Out-Null
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = Join-Path $Resources "python\python.exe"
    $info.Arguments = "-m abook.webui.host --version smoke --fake-runner"
    $info.WorkingDirectory = Join-Path $Resources "app"
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $info.EnvironmentVariables["ABOOK_PREFERENCES"] = (Join-Path $smokeData "preferences.json")
    $info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8"
    $process = [System.Diagnostics.Process]::Start($info)
    try {
        $line = $process.StandardOutput.ReadLine()
        if (-not $line) { throw "Host không báo sẵn sàng: $($process.StandardError.ReadToEnd())" }
        $url = ($line | ConvertFrom-Json).ready
        $base, $query = $url.Split("?", 2)
        $state = Invoke-RestMethod -UseBasicParsing -Uri ($base.TrimEnd("/") + "/api/app") -Headers @{ "X-Ebook-Token" = $query.Substring(2) }
        if ($state.version -ne "smoke" -or -not $state.dialogs) { throw "Host trả lời sai: $($state | ConvertTo-Json -Compress)" }
        $page = Invoke-WebRequest -UseBasicParsing -Uri $url
        if ($page.StatusCode -ne 200 -or $page.Content -notmatch "<div id=`"root`"") { throw "Trang giao diện không phục vụ" }
        $process.StandardInput.Close()  # vỏ đi: host phải tự thoát
        if (-not $process.WaitForExit(15000)) { throw "Host không thoát khi ống đóng" }
        if ($process.ExitCode -ne 0) { throw "Host thoát với mã $($process.ExitCode): $($process.StandardError.ReadToEnd())" }
    } finally {
        if (-not $process.HasExited) { $process.Kill() }
    }
    Write-Host "   host OK"
}

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

function Write-LatestJson([System.IO.FileInfo]$Setup) {
    # Tệp bộ cập nhật đọc (tauri.conf.json > plugins.updater.endpoints = releases/latest/download/latest.json): đính kèm
    # nó cùng bộ cài vào GitHub Release vX.Y.Z. Ghi chú = mục của phiên bản ấy trong CHANGELOG (trống nếu chưa có).
    $version = [regex]::Match($Setup.Name, "^ABook_(.+)_x64-setup\.exe$").Groups[1].Value
    $signature = [System.IO.File]::ReadAllText("$($Setup.FullName).sig").Trim()
    $changelog = [System.IO.File]::ReadAllText((Join-Path $Internal "docs\CHANGELOG.md"), [System.Text.Encoding]::UTF8)
    $section = [regex]::Match($changelog, "(?ms)^## \[$([regex]::Escape($version))\][^\n]*\n(.*?)(?=^## \[|\z)")
    $latest = [ordered]@{
        version = $version
        notes = if ($section.Success) { $section.Groups[1].Value.Trim() } else { "" }
        pub_date = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        platforms = [ordered]@{
            "windows-x86_64" = [ordered]@{
                signature = $signature
                url = "https://github.com/ntanhpro1221/ABook/releases/download/v$version/$($Setup.Name)"
            }
        }
    }
    $path = Join-Path $Setup.DirectoryName "latest.json"
    [System.IO.File]::WriteAllText($path, ($latest | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding $false))
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
