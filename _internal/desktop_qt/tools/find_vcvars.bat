@echo off
rem Sets VCVARS to vcvars64.bat of the newest Visual Studio or Build Tools that has the x64 C++ tools.
rem Never hard-code an edition path: 11-11 the Community IDE was uninstalled and Build Tools took its place.
rem No %%VAR%% inside ( ) blocks: Build Tools live under "Program Files (x86)" and the ")" would end the block.
set "_VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "%_VSWHERE%" goto have_vswhere
echo ERROR: vswhere.exe missing - install Visual Studio Build Tools with the C++ workload: winget install Microsoft.VisualStudio.BuildTools
exit /b 1
:have_vswhere
set "_VSOUT=%TEMP%\abook_vsinstall_%RANDOM%.txt"
"%_VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath > "%_VSOUT%"
set "_VSINST="
set /p _VSINST=<"%_VSOUT%"
del "%_VSOUT%" >nul 2>&1
if defined _VSINST goto have_install
echo ERROR: no Visual Studio install has the x64 C++ tools
exit /b 1
:have_install
set "VCVARS=%_VSINST%\VC\Auxiliary\Build\vcvars64.bat"
if exist "%VCVARS%" exit /b 0
echo ERROR: "%VCVARS%" missing
set "VCVARS="
exit /b 1
