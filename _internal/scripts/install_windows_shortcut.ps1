param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"

$AppName = "ABook"
# Tên cũ của app (trước 27-09): lối tắt mang tên này mà trỏ đúng trình khởi động dưới đây thì gỡ, để không còn hai mục.
$LegacyNames = @("Ebook Reader")
$Launcher = Join-Path $ProjectRoot "_internal\ABook.vbs"
$Icon = Join-Path $ProjectRoot "_internal\ebook_reader\assets\app.ico"
$ProgramsRoot = [Environment]::GetFolderPath([Environment+SpecialFolder]::Programs)
$RootShortcutPath = Join-Path $ProjectRoot "$AppName.lnk"
$StartMenuShortcutPath = Join-Path $ProgramsRoot "$AppName.lnk"
$IconLocation = "$Icon,0"

if (-not (Test-Path -LiteralPath $Launcher -PathType Leaf)) {
    throw "Không tìm thấy launcher: $Launcher"
}
if (-not (Test-Path -LiteralPath $Icon -PathType Leaf)) {
    throw "Không tìm thấy icon: $Icon"
}
if ([string]::IsNullOrWhiteSpace($ProgramsRoot)) {
    throw "Không xác định được thư mục Start Menu của người dùng."
}

New-Item -ItemType Directory -Force -Path $ProgramsRoot | Out-Null
$Shell = New-Object -ComObject WScript.Shell

function Set-AppShortcut([string]$ShortcutPath) {
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $NeedsSave = -not (Test-Path -LiteralPath $ShortcutPath -PathType Leaf) `
        -or $Shortcut.TargetPath -ne $Launcher `
        -or -not [string]::IsNullOrEmpty($Shortcut.Arguments) `
        -or $Shortcut.WorkingDirectory -ne $ProjectRoot `
        -or $Shortcut.IconLocation -ne $IconLocation

    if ($NeedsSave) {
        $Shortcut.TargetPath = $Launcher
        $Shortcut.Arguments = ""
        $Shortcut.WorkingDirectory = $ProjectRoot
        $Shortcut.IconLocation = $IconLocation
        $Shortcut.Description = $AppName
        $Shortcut.Save()
    }
}

function Remove-LegacyShortcut([string]$ShortcutPath) {
    if (-not (Test-Path -LiteralPath $ShortcutPath -PathType Leaf)) {
        return
    }
    if ($Shell.CreateShortcut($ShortcutPath).TargetPath -eq $Launcher) {
        Remove-Item -LiteralPath $ShortcutPath -Force
    }
}

# Windows maps the app window to its Start Menu entry through the AppUserModelID the app sets on itself
# (ebook_reader/desktop_shell.py: APP_USER_MODEL_ID). Without the same ID on the shortcut, the media card in
# Windows+A (and the media key overlay) cannot show the "ABook" name and icon for the player.
$AppUserModelId = "EbookReader.Desktop"

function Get-ShortcutAppId([string]$ShortcutPath) {
    $ShellApp = New-Object -ComObject Shell.Application
    $Folder = $ShellApp.Namespace((Split-Path -Parent $ShortcutPath))
    $Item = $Folder.ParseName((Split-Path -Leaf $ShortcutPath))
    return [string]$Item.ExtendedProperty("System.AppUserModel.ID")
}

function Set-ShortcutAppId([string]$ShortcutPath) {
    if ((Get-ShortcutAppId $ShortcutPath) -eq $AppUserModelId) {
        return
    }
    # Compiled only when the ID is missing: this script runs on every start.
    if (-not ("EbookReaderShortcutIdentity" -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class EbookReaderShortcutIdentity {
    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    struct PropertyKey { public Guid FormatId; public int PropertyId; }

    [StructLayout(LayoutKind.Explicit)]
    struct PropVariant { [FieldOffset(0)] public ushort Type; [FieldOffset(8)] public IntPtr Pointer; }

    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IPropertyStore {
        [PreserveSig] int GetCount(out uint count);
        [PreserveSig] int GetAt(uint index, out PropertyKey key);
        [PreserveSig] int GetValue(ref PropertyKey key, out PropVariant value);
        [PreserveSig] int SetValue(ref PropertyKey key, ref PropVariant value);
        [PreserveSig] int Commit();
    }

    [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    static extern void SHGetPropertyStoreFromParsingName(string path, IntPtr bindContext, int flags, ref Guid riid,
        [MarshalAs(UnmanagedType.Interface)] out IPropertyStore store);

    public static void Set(string path, string id) {
        Guid iid = typeof(IPropertyStore).GUID;
        IPropertyStore store;
        SHGetPropertyStoreFromParsingName(path, IntPtr.Zero, 2, ref iid, out store); // GPS_READWRITE
        PropertyKey key = new PropertyKey { FormatId = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), PropertyId = 5 };
        PropVariant value = new PropVariant { Type = 31, Pointer = Marshal.StringToCoTaskMemUni(id) }; // VT_LPWSTR
        try {
            Marshal.ThrowExceptionForHR(store.SetValue(ref key, ref value));
            Marshal.ThrowExceptionForHR(store.Commit());
        } finally {
            Marshal.FreeCoTaskMem(value.Pointer);
            Marshal.ReleaseComObject(store);
        }
    }
}
'@
    }
    [EbookReaderShortcutIdentity]::Set($ShortcutPath, $AppUserModelId)
}

Set-AppShortcut $RootShortcutPath
Set-AppShortcut $StartMenuShortcutPath
foreach ($LegacyName in $LegacyNames) {
    Remove-LegacyShortcut (Join-Path $ProjectRoot "$LegacyName.lnk")
    Remove-LegacyShortcut (Join-Path $ProgramsRoot "$LegacyName.lnk")
}
# Only the Start Menu entry: Windows resolves the ID there, and the root shortcut is a tracked file in the repo.
Set-ShortcutAppId $StartMenuShortcutPath
Write-Output $RootShortcutPath, $StartMenuShortcutPath
