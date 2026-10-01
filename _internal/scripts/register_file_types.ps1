# Đăng ký hai loại file của ABook cho NGƯỜI DÙNG HIỆN TẠI (HKCU, không cần quyền quản trị):
#   .abook      sách nói đã xong   - icon book_file.ico
#   .abookproj  dự án đang làm     - icon project_file.ico
# kèm thumbnail là BÌA SÁCH (build/windows/abook_thumbnail.dll) và icon loại file nhỏ ở góc thumbnail (TypeOverlay).
#
#   powershell -ExecutionPolicy Bypass -File _internal\scripts\register_file_types.ps1 [-DryRun] [-Unregister]
#
# -DryRun: chỉ in những gì sẽ ghi, không đụng registry. -Unregister: gỡ đúng những khoá này.
# Bấm đúp .abook mở ABook (shell\open\command -> ABook.vbs "<file>" -> app.py -> desktop.py nhập và mở cuốn ấy;
# app đang mở thì cửa sổ đang chạy mở nó). Bấm đúp .abookproj cũng vậy: app mở nó thành một dự án MỚI trong thư viện
# Studio (webui/projectfile.py).
param(
    [switch]$DryRun,
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"

$Internal = Split-Path -Parent $PSScriptRoot
$Assets = Join-Path $Internal "ebook_reader\assets"
$Dll = Join-Path $Internal "build\windows\abook_thumbnail.dll"
$Classes = "HKCU:\Software\Classes"
$HandlerClsid = "{8464156A-A4BD-4FDE-9FDD-57CB16936684}"  # windows/thumbnail/abook_thumbnail.h
$ThumbnailShellEx = "{e357fccd-a995-4576-b01f-234630154e96}"  # IThumbnailProvider

$Launcher = Join-Path $Internal "ABook.vbs"
$Types = @(
    @{ Extension = ".abook"; ProgId = "ABook.Book"; Name = "Sách nói ABook"; Icon = "book_file.ico";
       ContentType = "application/vnd.ngdtuanh.abook+zip"; Opens = $true },
    @{ Extension = ".abookproj"; ProgId = "ABook.Project"; Name = "Dự án sách nói ABook"; Icon = "project_file.ico";
       ContentType = "application/vnd.ngdtuanh.abookproj+zip"; Opens = $true }
)

function Set-Value([string]$Key, [string]$Name, $Value, [string]$Kind = "String") {
    $Shown = if ($Name) { $Name } else { "(mặc định)" }
    if ($DryRun) {
        Write-Output "$Key  $Shown = $Value"
        return
    }
    if (-not (Test-Path -LiteralPath $Key)) {
        New-Item -Path $Key -Force | Out-Null
    }
    if ($Name) {
        New-ItemProperty -LiteralPath $Key -Name $Name -Value $Value -PropertyType $Kind -Force | Out-Null
    } else {
        Set-Item -LiteralPath $Key -Value $Value
    }
}

function Remove-Key([string]$Key) {
    if ($DryRun) {
        Write-Output "gỡ $Key"
    } elseif (Test-Path -LiteralPath $Key) {
        Remove-Item -LiteralPath $Key -Recurse -Force
    }
}

if ($Unregister) {
    foreach ($Type in $Types) {
        # chỉ gỡ khi phần mở rộng vẫn trỏ về ABook - không xoá liên kết người dùng tự đặt cho app khác
        $ExtensionKey = Join-Path $Classes $Type.Extension
        if ((Test-Path -LiteralPath $ExtensionKey) -and ((Get-Item -LiteralPath $ExtensionKey).GetValue("") -eq $Type.ProgId)) {
            Remove-Key $ExtensionKey
        }
        Remove-Key (Join-Path $Classes $Type.ProgId)
    }
    Remove-Key (Join-Path $Classes "CLSID\$HandlerClsid")
} else {
    if (-not (Test-Path -LiteralPath $Dll -PathType Leaf)) {
        throw "Chưa có $Dll - build bằng: runtime\.venv\Scripts\python.exe scripts\build_thumbnail_handler.py"
    }
    $HandlerKey = Join-Path $Classes "CLSID\$HandlerClsid"
    Set-Value $HandlerKey "" "ABook: bìa sách làm thumbnail"
    Set-Value (Join-Path $HandlerKey "InprocServer32") "" $Dll
    Set-Value (Join-Path $HandlerKey "InprocServer32") "ThreadingModel" "Apartment"
    foreach ($Type in $Types) {
        $Icon = Join-Path $Assets $Type.Icon
        if (-not (Test-Path -LiteralPath $Icon -PathType Leaf)) {
            throw "Không thấy icon: $Icon"
        }
        $ExtensionKey = Join-Path $Classes $Type.Extension
        $ProgIdKey = Join-Path $Classes $Type.ProgId
        Set-Value $ExtensionKey "" $Type.ProgId
        Set-Value $ExtensionKey "Content Type" $Type.ContentType
        Set-Value (Join-Path $ExtensionKey "ShellEx\$ThumbnailShellEx") "" $HandlerClsid
        Set-Value $ProgIdKey "" $Type.Name
        Set-Value (Join-Path $ProgIdKey "DefaultIcon") "" "$Icon,0"
        # icon loại file nhỏ ở góc thumbnail: hai loại file cùng một bìa, nhìn góc là phân biệt
        Set-Value $ProgIdKey "TypeOverlay" "$Icon,0"
        if ($Type.Opens) {
            # wscript chạy trình khởi động không hiện cửa sổ đen; đường dẫn file đi tiếp tới app.py
            Set-Value (Join-Path $ProgIdKey "shell") "" "open"
            Set-Value (Join-Path $ProgIdKey "shell\open") "" "Mở bằng ABook"
            Set-Value (Join-Path $ProgIdKey "shell\open\command") "" "`"$env:WINDIR\System32\wscript.exe`" `"$Launcher`" `"%1`""
        }
    }
}

if (-not $DryRun) {
    # báo Explorer vẽ lại icon/thumbnail theo liên kết mới
    Add-Type -Namespace ABook -Name Shell -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("shell32.dll")]
public static extern void SHChangeNotify(int eventId, uint flags, System.IntPtr item1, System.IntPtr item2);
'@
    [ABook.Shell]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)  # SHCNE_ASSOCCHANGED
    Write-Output $(if ($Unregister) { "Đã gỡ đăng ký .abook và .abookproj." } else { "Đã đăng ký .abook và .abookproj." })
}
