@echo off
rem Sets VCVARS to vcvars64.bat of the newest Visual Studio or Build Tools that has the x64 C++ tools.
rem Never hard-code an edition path: 11-11 the Community IDE was uninstalled and Build Tools took its place.
set "_VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%_VSWHERE%" (
  echo ERROR: vswhere.exe missing - install Visual Studio Build Tools with the C++ workload ^(winget install Microsoft.VisualStudio.BuildTools^)
  exit /b 1
)
set "_VSOUT=%TEMP%\abook_vsinstall_%RANDOM%.txt"
"%_VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath > "%_VSOUT%"
set "_VSINST="
set /p _VSINST=<"%_VSOUT%"
del "%_VSOUT%" >nul 2>&1
if not defined _VSINST (
  echo ERROR: no Visual Studio install has the x64 C++ tools
  exit /b 1
)
set "VCVARS=%_VSINST%\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" (
  echo ERROR: %VCVARS% missing
  set "VCVARS="
  exit /b 1
)
exit /b 0
