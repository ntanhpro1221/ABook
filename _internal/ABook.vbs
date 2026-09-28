Option Explicit

Dim shell
Dim fileSystem
Dim internalRoot
Dim projectRoot
Dim launcher
Dim command
Dim windowStyle

Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")
internalRoot = fileSystem.GetParentFolderName(WScript.ScriptFullName)
projectRoot = fileSystem.GetParentFolderName(internalRoot)
launcher = fileSystem.BuildPath(internalRoot, "scripts\start_windows.ps1")
command = "powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File """ & launcher & """"
windowStyle = 1

' Bam dup mot file sach (.abook): Windows goi script nay kem duong dan file (register_file_types.ps1).
' App dang mo thi cua so dang chay mo file ay; console cua trinh khoi dong chi thu nho duoi thanh tac vu.
If WScript.Arguments.Count > 0 Then
    command = command & " -OpenFile """ & WScript.Arguments(0) & """"
    windowStyle = 7
End If

shell.Run command, windowStyle, False
