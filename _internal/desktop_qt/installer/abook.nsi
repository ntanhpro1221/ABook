; Bộ cài Windows của app Qt (docs/QT_INSTALLER.md, Q2). Cài cùng chỗ, cùng khoá gỡ cài, cùng tên exe với bản Tauri, nên
; bản này cài đè lên bản kia là xong, không cần bước chuyển đổi nào.
;
; makensis /DVERSION=0.4.150 /DVERSIONWITHBUILD=0.4.150.0 /DABOOK_DIST=<dist> /DABOOK_FILES=<thư mục files.py> /DOUTFILE=<exe>
;          [/DABOOK_TEST_ROOT=Software\ABookTest-<uuid>] abook.nsi
;
; Bản test (ABOOK_TEST_ROOT): mọi khoá registry nằm dưới HKCU\<ABOOK_TEST_ROOT>, lối tắt nằm trong %ABOOK_TEST_SHELL%, dữ
; liệu là %LOCALAPPDATA% của tiến trình; $INSTDIR, lối tắt và dữ liệu phải nằm dưới %TEMP% của tiến trình (không thì thoát mã 7
; trước khi chạm vào gì), và không có lệnh nào đụng trạng thái chung của shell (bỏ ghim Start, xoá jump list, báo đổi liên kết).
; Lead 31-10: không test nào ghi vào HKCU hay thư mục cài thật.
;
; Gỡ (Q3): bản gỡ thật luôn xoá Studio tải thêm và cache của app Qt; dữ liệu người dùng (%LOCALAPPDATA%\ABook: chỗ đang nghe,
; tuỳ chọn, nhật ký) chỉ khi tích ô "Xoá dữ liệu" (hay /DELETEDATA khi gỡ im lặng). Mỗi lần xoá đệ quy hỏi uninstall_guard.ps1
; trước: thư viện sách đã lưu nằm trong thư mục ấy, tuỳ chọn không đọc được, hay có junction -> giữ nguyên. Cập nhật (/UPDATE)
; không xoá gì của người dùng.

Unicode true
ManifestDPIAware true
ManifestDPIAwareness PerMonitorV2
!ifdef ABOOK_TEST_ROOT
  ; Bản test: không nén cho nhanh dựng (nén không đổi logic nào của bộ cài).
  SetCompress off
!else
  SetCompressor /SOLID lzma
!endif
!include MUI2.nsh
!include FileFunc.nsh
!include LogicLib.nsh
!include "Win\COM.nsh"
!include "Win\Propkey.nsh"
!include nsDialogs.nsh

!macro ABOOK_REQUIRE NAME
  !ifndef ${NAME}
    !error "Thiếu /D${NAME}"
  !endif
!macroend
!insertmacro ABOOK_REQUIRE VERSION
!insertmacro ABOOK_REQUIRE VERSIONWITHBUILD
!insertmacro ABOOK_REQUIRE ABOOK_DIST
!insertmacro ABOOK_REQUIRE ABOOK_FILES
!insertmacro ABOOK_REQUIRE OUTFILE
; makensis chạy trong thư mục của kịch bản này (không /NOCD): mọi đường tương đối dưới đây tính từ đó.
!include "${ABOOK_FILES}\estimated_size.nsh"

!define PRODUCTNAME "ABook"
!define MANUFACTURER "ABook"
!define MAINBINARY "ABook.exe"
; AppUserModelID mà app Qt tự đặt (src/mediacontrols.cpp): lối tắt mang cùng ID thì cửa sổ đang chạy gộp vào lối tắt ấy.
!define AUMID "ABook.Desktop"
!define PLACEHOLDER_INSTALL_DIR "placeholder\${PRODUCTNAME}"
!define TEST_REFUSED 7

!ifdef ABOOK_TEST_ROOT
  !define REG_UNINST "${ABOOK_TEST_ROOT}\Uninstall\${PRODUCTNAME}"
  !define REG_MANU "${ABOOK_TEST_ROOT}\${MANUFACTURER}"
  !define REG_RUN "${ABOOK_TEST_ROOT}\Run"
  !define REG_CLASSES "${ABOOK_TEST_ROOT}\Classes"
!else
  !define REG_UNINST "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCTNAME}"
  !define REG_MANU "Software\${MANUFACTURER}"
  !define REG_RUN "Software\Microsoft\Windows\CurrentVersion\Run"
  !define REG_CLASSES "Software\Classes"
!endif
!define REG_MANUPRODUCT "${REG_MANU}\${PRODUCTNAME}"

Var PassiveMode
Var UpdateMode
Var NoShortcutMode
Var ShellPrograms
Var ShellDesktop
Var ShellPins
Var DataLocal
Var DeleteDataCheckbox
Var DeleteDataState

Name "${PRODUCTNAME}"
BrandingText " "
OutFile "${OUTFILE}"
; Chỉ để trang chọn thư mục tự thêm "\ABook"; chỗ cài thật đặt trong .onInit.
InstallDir "${PLACEHOLDER_INSTALL_DIR}"
RequestExecutionLevel user
VIProductVersion "${VERSIONWITHBUILD}"
VIAddVersionKey "ProductName" "${PRODUCTNAME}"
VIAddVersionKey "FileDescription" "${PRODUCTNAME}"
VIAddVersionKey "LegalCopyright" " "
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "ProductVersion" "${VERSION}"

!define MUI_ICON "..\..\abook\assets\app.ico"
!define MUI_UNICON "..\..\abook\assets\app.ico"

!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipIfPassive
!insertmacro MUI_PAGE_WELCOME
!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipIfPassive
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
; Giữ trang tiến trình lại: dòng chi tiết là thứ duy nhất để đọc khi cài hỏng.
!define MUI_FINISHPAGE_NOAUTOCLOSE
!define MUI_FINISHPAGE_SHOWREADME
!define MUI_FINISHPAGE_SHOWREADME_TEXT "$(createDesktop)"
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION CreateOrUpdateDesktopShortcut
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION RunMainBinary
!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipIfPassive
!insertmacro MUI_PAGE_FINISH

!define MUI_PAGE_CUSTOMFUNCTION_PRE un.SkipIfPassive
!define MUI_PAGE_CUSTOMFUNCTION_SHOW un.ConfirmShow
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE un.ConfirmLeave
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Vietnamese"
LangString createDesktop ${LANG_VIETNAMESE} "Tạo lối tắt trên màn hình nền"
LangString appRunning ${LANG_VIETNAMESE} "ABook đang mở. Bấm OK để đóng ABook rồi làm tiếp."
LangString stopFailed ${LANG_VIETNAMESE} "Chưa đóng được ABook. Bạn hãy đóng app rồi chạy lại."
LangString resourcesLink ${LANG_VIETNAMESE} "Thư mục resources của ABook là một liên kết, bộ cài không xoá nó. Bạn hãy gỡ liên kết ấy rồi chạy lại."
LangString resourcesBusy ${LANG_VIETNAMESE} "Chưa xoá được bản cũ trong thư mục resources. Bạn hãy đóng ABook rồi chạy lại."
LangString deleteData ${LANG_VIETNAMESE} "Xoá dữ liệu ứng dụng (chỗ đang nghe, tuỳ chọn). Thư viện sách vẫn giữ nguyên."
LangString keptFolder ${LANG_VIETNAMESE} "Giữ thư mục để bảo vệ thư viện của bạn:"
LangString bookFile ${LANG_VIETNAMESE} "Sách nói ABook"
LangString projectFile ${LANG_VIETNAMESE} "Dự án sách nói ABook"

; --- Thư mục lối tắt: thật, hay của bản test -------------------------------------------------------------------------------

!macro ABOOK_SETUP_CONTEXT UN
Function ${UN}AbookSetupContext
  SetShellVarContext current
  SetRegView 64
  ${GetOptions} $CMDLINE "/P" $0
  ${IfNot} ${Errors}
    StrCpy $PassiveMode 1
  ${EndIf}
  ${GetOptions} $CMDLINE "/NS" $0
  ${IfNot} ${Errors}
    StrCpy $NoShortcutMode 1
  ${EndIf}
  ${GetOptions} $CMDLINE "/UPDATE" $0
  ${IfNot} ${Errors}
    StrCpy $UpdateMode 1
  ${EndIf}
  ${GetOptions} $CMDLINE "/DELETEDATA" $0
  ${IfNot} ${Errors}
    StrCpy $DeleteDataState ${BST_CHECKED}
  ${EndIf}
  !ifdef ABOOK_TEST_ROOT
    ReadEnvStr $0 "ABOOK_TEST_SHELL"
    StrCpy $ShellPrograms "$0\Programs"
    StrCpy $ShellDesktop "$0\Desktop"
    StrCpy $ShellPins "$0\TaskBar"
    ReadEnvStr $DataLocal "LOCALAPPDATA"
  !else
    StrCpy $ShellPrograms $SMPROGRAMS
    StrCpy $ShellDesktop $DESKTOP
    StrCpy $ShellPins "$APPDATA\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"
    StrCpy $DataLocal $LOCALAPPDATA
  !endif
FunctionEnd

; Bản test chỉ được chạm vào thứ nằm dưới %TEMP% của chính nó: thư mục cài, lối tắt, dữ liệu.
Function ${UN}AbookTestGuard
  !ifdef ABOOK_TEST_ROOT
    ReadEnvStr $0 "ABOOK_TEST_SHELL"
    StrLen $1 "$TEMP\"
    StrCpy $2 $INSTDIR $1
    StrCpy $3 $0 $1
    StrCpy $4 $DataLocal $1
    ${If} $0 == ""
    ${OrIf} $2 != "$TEMP\"
    ${OrIf} $3 != "$TEMP\"
    ${OrIf} $4 != "$TEMP\"
      SetErrorLevel ${TEST_REFUSED}
      Quit
    ${EndIf}
  !endif
FunctionEnd
!macroend
!insertmacro ABOOK_SETUP_CONTEXT ""
!insertmacro ABOOK_SETUP_CONTEXT "un."

; --- Lối tắt (logic của utils.nsh trong bộ cài Tauri, viết lại với AUMID của app Qt) ---------------------------------------

!define /ifndef MAX_PATH 260
!define /ifndef SLGP_RAWPATH 0x4

; Đẩy 1 nếu lối tắt trỏ vào đúng `target`, 0 nếu không (kể cả khi không có file).
!macro ABOOK_IS_SHORTCUT_TARGET SHORTCUT TARGET
  StrCpy $3 0
  !insertmacro ComHlpr_CreateInProcInstance ${CLSID_ShellLink} ${IID_IShellLink} r0 ""
  ${If} $0 P<> 0
    ${IUnknown::QueryInterface} $0 '("${IID_IPersistFile}", .r1)'
    ${If} $1 P<> 0
      ${IPersistFile::Load} $1 '("${SHORTCUT}", ${STGM_READ})'
      System::Alloc ${MAX_PATH}
      Pop $2
      ${IShellLink::GetPath} $0 '(.r2, ${MAX_PATH}, 0, ${SLGP_RAWPATH})'
      ${If} $2 == "${TARGET}"
        StrCpy $3 1
      ${EndIf}
      System::Free $2
      ${IUnknown::Release} $1 ""
    ${EndIf}
    ${IUnknown::Release} $0 ""
  ${EndIf}
  Push $3
!macroend

!macro ABOOK_SET_AUMID SHORTCUT
  !insertmacro ComHlpr_CreateInProcInstance ${CLSID_ShellLink} ${IID_IShellLink} r0 ""
  ${If} $0 P<> 0
    ${IUnknown::QueryInterface} $0 '("${IID_IPersistFile}",.r1)'
    ${If} $1 P<> 0
      ${IPersistFile::Load} $1 '("${SHORTCUT}", ${STGM_READWRITE})'
      ${IUnknown::QueryInterface} $0 '("${IID_IPropertyStore}",.r2)'
      ${If} $2 P<> 0
        System::Call 'Oleaut32::SysAllocString(w "${AUMID}") i.r3'
        System::Call '*${SYSSTRUCT_PROPERTYKEY}(${PKEY_AppUserModel_ID})p.r4'
        System::Call '*${SYSSTRUCT_PROPVARIANT}(${VT_BSTR},,&i4 $3)p.r5'
        ${IPropertyStore::SetValue} $2 '($4,$5)'
        System::Call 'Oleaut32::SysFreeString($3)'
        System::Free $4
        System::Free $5
        ${IPropertyStore::Commit} $2 ""
        ${IUnknown::Release} $2 ""
        ${IPersistFile::Save} $1 '("${SHORTCUT}",1)'
      ${EndIf}
      ${IUnknown::Release} $1 ""
    ${EndIf}
    ${IUnknown::Release} $0 ""
  ${EndIf}
!macroend

; Lối tắt đã trỏ vào exe này (kể cả lối tắt của bản Tauri, cùng đường exe): chỉ đặt lại AUMID. Chưa có: tạo, trừ khi đang
; cập nhật (/UPDATE) hay /NS - người dùng đã xoá lối tắt thì bản cập nhật không tạo lại.
!macro ABOOK_SHORTCUT SHORTCUT
  !insertmacro ABOOK_IS_SHORTCUT_TARGET "${SHORTCUT}" "$INSTDIR\${MAINBINARY}"
  Pop $0
  ${If} $0 = 1
    !insertmacro ABOOK_SET_AUMID "${SHORTCUT}"
  ${ElseIf} $UpdateMode <> 1
  ${AndIf} $NoShortcutMode <> 1
    CreateShortcut "${SHORTCUT}" "$INSTDIR\${MAINBINARY}"
    !insertmacro ABOOK_SET_AUMID "${SHORTCUT}"
  ${EndIf}
!macroend

Function CreateOrUpdateStartMenuShortcut
  !insertmacro ABOOK_SHORTCUT "$ShellPrograms\${PRODUCTNAME}.lnk"
FunctionEnd

Function CreateOrUpdateDesktopShortcut
  !insertmacro ABOOK_SHORTCUT "$ShellDesktop\${PRODUCTNAME}.lnk"
FunctionEnd

; Ghim thanh tác vụ là của người dùng: không bao giờ tạo, chỉ đặt lại AUMID cho ghim đang trỏ vào exe này.
Function UpdatePinnedShortcut
  !insertmacro ABOOK_IS_SHORTCUT_TARGET "$ShellPins\${PRODUCTNAME}.lnk" "$INSTDIR\${MAINBINARY}"
  Pop $0
  ${If} $0 = 1
    !insertmacro ABOOK_SET_AUMID "$ShellPins\${PRODUCTNAME}.lnk"
  ${EndIf}
FunctionEnd

!macro ABOOK_DELETE_SHORTCUT SHORTCUT
  !insertmacro ABOOK_IS_SHORTCUT_TARGET "${SHORTCUT}" "$INSTDIR\${MAINBINARY}"
  Pop $0
  ${If} $0 = 1
    !ifndef ABOOK_TEST_ROOT
      ; Bỏ ghim khỏi Start (trạng thái chung của shell: bản test không bao giờ gọi).
      !insertmacro ComHlpr_CreateInProcInstance ${CLSID_StartMenuPin} ${IID_IStartMenuPinnedList} r0 ""
      ${If} $0 P<> 0
        System::Call 'SHELL32::SHCreateItemFromParsingName(ws, p0, g "${IID_IShellItem}", *p0r1)' "${SHORTCUT}"
        ${If} $1 P<> 0
          ${IStartMenuPinnedList::RemoveFromList} $0 '(r1)'
          ${IUnknown::Release} $1 ""
        ${EndIf}
        ${IUnknown::Release} $0 ""
      ${EndIf}
    !endif
    Delete "${SHORTCUT}"
  ${EndIf}
!macroend

; --- Tiến trình đang chạy + resources\ ----------------------------------------------------------------------------------

; Đóng ABook.exe của thư mục cài và mọi tiến trình chạy từ resources\ (host Python nhúng). Không dừng cả $INSTDIR: nó là
; %LOCALAPPDATA%\ABook, cha của worker Studio đang làm sách. Hỏi trước khi có giao diện đầy đủ; /P và /S đóng luôn.
!macro ABOOK_STOP_APP
  InitPluginsDir
  File "/oname=$PLUGINSDIR\abook-stop-processes.ps1" "stop_processes.ps1"
  File "/oname=$PLUGINSDIR\abook-uninstall-guard.ps1" "uninstall_guard.ps1"
  System::Call 'kernel32::SetEnvironmentVariableW(w "ABOOK_STOP_ROOT", w "$INSTDIR\resources") i .r0'
  System::Call 'kernel32::SetEnvironmentVariableW(w "ABOOK_STOP_EXE", w "$INSTDIR\${MAINBINARY}") i .r1'
  ${If} $0 = 0
  ${OrIf} $1 = 0
    MessageBox MB_OK|MB_ICONSTOP "$(stopFailed)" /SD IDOK
    Abort
  ${EndIf}
  nsExec::Exec 'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\abook-stop-processes.ps1" -Find'
  Pop $0
  ${If} $0 == 3
    ${If} $PassiveMode <> 1
      ${If} ${Cmd} `MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION "$(appRunning)" /SD IDOK IDCANCEL`
        Abort
      ${EndIf}
    ${EndIf}
    nsExec::Exec 'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\abook-stop-processes.ps1"'
    Pop $0
  ${EndIf}
  ${If} $0 != 0
    MessageBox MB_OK|MB_ICONSTOP "$(stopFailed)" /SD IDOK
    Abort
  ${EndIf}
!macroend

; resources\ toàn của app (cả bản Tauri lẫn bản Qt): xoá cả cây, để file thừa của bản cũ không ở lại. Là junction thì dừng -
; RMDir /r không được đi theo liên kết ra ngoài thư mục cài.
!macro ABOOK_REMOVE_RESOURCES
  System::Call 'kernel32::GetFileAttributesW(w "$INSTDIR\resources") i .r0'
  ${If} $0 <> -1
    IntOp $1 $0 & 0x400
    ${If} $1 <> 0
      MessageBox MB_OK|MB_ICONSTOP "$(resourcesLink)" /SD IDOK
      Abort
    ${EndIf}
    RMDir /r "$INSTDIR\resources"
    ${If} ${FileExists} "$INSTDIR\resources\*.*"
      MessageBox MB_OK|MB_ICONSTOP "$(resourcesBusy)" /SD IDOK
      Abort
    ${EndIf}
  ${EndIf}
!macroend

; --- Dữ liệu: dừng rồi xoá, có guard -------------------------------------------------------------------------------------

; Dừng mọi tiến trình chạy TỪ `FOLDER` (worker Studio, Ollama riêng...), theo đường exe như ABOOK_STOP_APP.
!macro ABOOK_STOP_UNDER FOLDER
  System::Call 'kernel32::SetEnvironmentVariableW(w "ABOOK_STOP_ROOT", w "${FOLDER}") i .r0'
  System::Call 'kernel32::SetEnvironmentVariableW(w "ABOOK_STOP_EXE", p 0) i .r1'
  ${If} $0 = 0
    MessageBox MB_OK|MB_ICONSTOP "$(stopFailed)" /SD IDOK
    Abort
  ${EndIf}
  nsExec::Exec 'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\abook-stop-processes.ps1"'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_OK|MB_ICONSTOP "$(stopFailed)" /SD IDOK
    Abort
  ${EndIf}
!macroend

; Xoá đệ quy `FOLDER` chỉ khi uninstall_guard.ps1 trả 0: thư viện sách đã lưu (preferences.json của $DataLocal) không nằm trong
; nó, tuỳ chọn đọc được, không có junction trên đường. Không chắc thì giữ, ghi một dòng chi tiết.
!macro ABOOK_REMOVE_SAFE FOLDER
  ${If} ${FileExists} "${FOLDER}\*.*"
    System::Call 'kernel32::SetEnvironmentVariableW(w "ABOOK_DELETE_TARGET", w "${FOLDER}") i .r0'
    System::Call 'kernel32::SetEnvironmentVariableW(w "ABOOK_PREFERENCES", w "$DataLocal\${PRODUCTNAME}\preferences.json") i .r1'
    StrCpy $2 1
    ${If} $0 <> 0
    ${AndIf} $1 <> 0
      nsExec::Exec 'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\abook-uninstall-guard.ps1"'
      Pop $2
    ${EndIf}
    ${If} $2 == 0
      RMDir /r "${FOLDER}"
    ${Else}
      DetailPrint "$(keptFolder) ${FOLDER}"
    ${EndIf}
  ${EndIf}
!macroend

; --- Liên kết file --------------------------------------------------------------------------------------------------------

; Ghi `.ext` -> `PROGID` và lệnh mở. Giá trị có sẵn của `.ext` (của app khác) giữ ở "ABook_backup" để gỡ trả lại; đã là của
; ABook (cập nhật cài đè) thì giữ bản sao lưu cũ - lỗi của bộ cài Tauri 28-09 (shell/src-tauri/windows/hooks.nsh).
!macro ABOOK_ASSOCIATE EXT PROGID DESCRIPTION ICON MIME
  ReadRegStr $1 HKCU "${REG_CLASSES}\${EXT}" "ABook_backup"
  ReadRegStr $0 HKCU "${REG_CLASSES}\${EXT}" ""
  ${If} $0 != "${PROGID}"
    StrCpy $1 $0
  ${EndIf}
  WriteRegStr HKCU "${REG_CLASSES}\${EXT}" "ABook_backup" $1
  WriteRegStr HKCU "${REG_CLASSES}\${EXT}" "" "${PROGID}"
  WriteRegStr HKCU "${REG_CLASSES}\${EXT}" "Content Type" "${MIME}"
  WriteRegStr HKCU "${REG_CLASSES}\${PROGID}" "" "${DESCRIPTION}"
  WriteRegStr HKCU "${REG_CLASSES}\${PROGID}\DefaultIcon" "" "${ICON}"
  WriteRegStr HKCU "${REG_CLASSES}\${PROGID}\shell" "" "open"
  WriteRegStr HKCU "${REG_CLASSES}\${PROGID}\shell\open\command" "" '"$INSTDIR\${MAINBINARY}" "%1"'
!macroend

; Gỡ thật: `.ext` còn trỏ ABook thì trả giá trị gốc (gốc rỗng: bỏ giá trị); người dùng đã chọn app khác thì để nguyên. Dọn bản
; sao lưu, khoá `.ext` nếu rỗng, và cả ProgId.
!macro ABOOK_UNASSOCIATE EXT PROGID
  ReadRegStr $0 HKCU "${REG_CLASSES}\${EXT}" ""
  ${If} $0 == "${PROGID}"
    ReadRegStr $1 HKCU "${REG_CLASSES}\${EXT}" "ABook_backup"
    ${If} $1 == ""
      DeleteRegValue HKCU "${REG_CLASSES}\${EXT}" ""
    ${Else}
      WriteRegStr HKCU "${REG_CLASSES}\${EXT}" "" $1
    ${EndIf}
    DeleteRegValue HKCU "${REG_CLASSES}\${EXT}" "Content Type"
  ${EndIf}
  DeleteRegValue HKCU "${REG_CLASSES}\${EXT}" "ABook_backup"
  DeleteRegKey /ifempty HKCU "${REG_CLASSES}\${EXT}"
  DeleteRegKey HKCU "${REG_CLASSES}\${PROGID}"
!macroend

!macro ABOOK_NOTIFY_ASSOCIATIONS
  !ifndef ABOOK_TEST_ROOT
    ; SHCNE_ASSOCCHANGED: Explorer đọc lại biểu tượng file (trạng thái chung của shell: bản test không bao giờ gọi).
    System::Call 'shell32::SHChangeNotify(i 0x08000000, i 0, p 0, p 0)'
  !endif
!macroend

; --- Cài ------------------------------------------------------------------------------------------------------------------

Function .onInit
  Call AbookSetupContext
  ${If} $INSTDIR == "${PLACEHOLDER_INSTALL_DIR}"
    !ifdef ABOOK_TEST_ROOT
      ; Bản test luôn được gọi với /D=: không có thì từ chối, không đoán chỗ cài.
      SetErrorLevel ${TEST_REFUSED}
      Quit
    !else
      StrCpy $INSTDIR "$LOCALAPPDATA\${PRODUCTNAME}"
      ReadRegStr $0 HKCU "${REG_MANUPRODUCT}" ""
      ${If} $0 != ""
        StrCpy $INSTDIR $0
      ${EndIf}
    !endif
  ${EndIf}
  Call AbookTestGuard
FunctionEnd

Function SkipIfPassive
  ${IfThen} $PassiveMode = 1 ${|} Abort ${|}
FunctionEnd

Function RunMainBinary
  Exec '"$INSTDIR\${MAINBINARY}"'
FunctionEnd

Section Install
  ; Trang chọn thư mục chạy sau .onInit: kiểm lại chỗ người dùng chọn.
  Call AbookTestGuard
  SetOutPath "$INSTDIR"
  !insertmacro ABOOK_STOP_APP
  !insertmacro ABOOK_REMOVE_RESOURCES
  !include "${ABOOK_FILES}\install_files.nsh"
  ; Mã app chở dạng .py (.pyc làm bộ cài nặng thêm 2,6 MB): biên dịch ở đây, ~1 giây, để lần mở đầu không chậm. Lỗi thì
  ; Python tự biên dịch khi nạp (thư mục cài ghi được). Gỡ cài xoá cả resources\, gồm các __pycache__ này.
  nsExec::Exec '"$INSTDIR\resources\python\python.exe" -E -m compileall -q -j 0 "$INSTDIR\resources\app\abook"'
  Pop $0
  WriteUninstaller "$INSTDIR\uninstall.exe"

  WriteRegStr HKCU "${REG_MANUPRODUCT}" "" "$INSTDIR"
  WriteRegStr HKCU "${REG_UNINST}" "MainBinaryName" "${MAINBINARY}"
  WriteRegStr HKCU "${REG_UNINST}" "DisplayName" "${PRODUCTNAME}"
  WriteRegStr HKCU "${REG_UNINST}" "DisplayIcon" "$\"$INSTDIR\${MAINBINARY}$\""
  WriteRegStr HKCU "${REG_UNINST}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${REG_UNINST}" "Publisher" "${MANUFACTURER}"
  WriteRegStr HKCU "${REG_UNINST}" "InstallLocation" "$\"$INSTDIR$\""
  WriteRegStr HKCU "${REG_UNINST}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
  WriteRegDWORD HKCU "${REG_UNINST}" "NoModify" 1
  WriteRegDWORD HKCU "${REG_UNINST}" "NoRepair" 1
  ; Cỡ của chính các file đã cài (files.py), không phải cả $INSTDIR - trong đó còn Studio và dữ liệu người dùng.
  WriteRegDWORD HKCU "${REG_UNINST}" "EstimatedSize" ${ABOOK_ESTIMATED_KB}
  !insertmacro ABOOK_ASSOCIATE ".abook" "ABook" "$(bookFile)" "$INSTDIR\resources\app\abook\assets\book_file.ico" \
    "application/vnd.ngdtuanh.abook+zip"
  !insertmacro ABOOK_ASSOCIATE ".abookproj" "ABook.Project" "$(projectFile)" \
    "$INSTDIR\resources\app\abook\assets\project_file.ico" "application/vnd.ngdtuanh.abookproj+zip"
  !insertmacro ABOOK_NOTIFY_ASSOCIATIONS

  Call CreateOrUpdateStartMenuShortcut
  ; Trang xong (có ô lối tắt màn hình nền) bị bỏ qua khi /P hay /S.
  ${If} $PassiveMode = 1
  ${OrIf} ${Silent}
    Call CreateOrUpdateDesktopShortcut
  ${EndIf}
  Call UpdatePinnedShortcut
  ${If} $PassiveMode = 1
    SetAutoClose true
  ${EndIf}
SectionEnd

Function .onInstSuccess
  ; /R (bộ cập nhật): mở lại app sau khi cài im lặng hay passive; giao diện đầy đủ đã có ô "chạy" ở trang xong.
  ${If} $PassiveMode = 1
  ${OrIf} ${Silent}
    ${GetOptions} $CMDLINE "/R" $0
    ${IfNot} ${Errors}
      Exec '"$INSTDIR\${MAINBINARY}"'
    ${EndIf}
  ${EndIf}
FunctionEnd

; --- Gỡ -------------------------------------------------------------------------------------------------------------------

Function un.onInit
  Call un.AbookSetupContext
  Call un.AbookTestGuard
FunctionEnd

Function un.SkipIfPassive
  ${IfThen} $PassiveMode = 1 ${|} Abort ${|}
FunctionEnd

; Ô "Xoá dữ liệu" dưới trang xác nhận gỡ, mặc định không tích (gỡ nhầm rồi cài lại không mất chỗ đang nghe).
Function un.ConfirmShow
  FindWindow $1 "#32770" "" $HWNDPARENT
  System::Call 'user32::CreateWindowEx(i ${__NSD_CheckBox_EXSTYLE}, t "${__NSD_CheckBox_CLASS}", t "$(deleteData)", i ${__NSD_CheckBox_STYLE}, i 0, i 120, i 440, i 24, p r1, p 0, p 0, p 0) p .s'
  Pop $DeleteDataCheckbox
  SendMessage $HWNDPARENT ${WM_GETFONT} 0 0 $1
  SendMessage $DeleteDataCheckbox ${WM_SETFONT} $1 1
  ${If} $DeleteDataState = ${BST_CHECKED}
    SendMessage $DeleteDataCheckbox ${BM_SETCHECK} ${BST_CHECKED} 0
  ${EndIf}
FunctionEnd

Function un.ConfirmLeave
  SendMessage $DeleteDataCheckbox ${BM_GETCHECK} 0 0 $DeleteDataState
FunctionEnd

Section Uninstall
  !insertmacro ABOOK_STOP_APP
  !insertmacro ABOOK_REMOVE_RESOURCES
  !include "${ABOOK_FILES}\uninstall_files.nsh"
  Delete "$INSTDIR\uninstall.exe"
  ; Không /r: $INSTDIR còn dữ liệu người dùng thì nó ở lại.
  RMDir "$INSTDIR"

  ${If} $UpdateMode <> 1
    !insertmacro ABOOK_DELETE_SHORTCUT "$ShellPrograms\${PRODUCTNAME}.lnk"
    !insertmacro ABOOK_DELETE_SHORTCUT "$ShellDesktop\${PRODUCTNAME}.lnk"
    !ifndef ABOOK_TEST_ROOT
      ; Jump list của app (trạng thái chung của shell: bản test không bao giờ gọi).
      !insertmacro ComHlpr_CreateInProcInstance ${CLSID_ApplicationDestinations} ${IID_IApplicationDestinations} r1 ""
      ${If} $1 P<> 0
        ${IApplicationDestinations::SetAppID} $1 '("${AUMID}")i.r0'
        ${If} $0 >= 0
          ${IApplicationDestinations::RemoveAllDestinations} $1 ''
        ${EndIf}
        ${IUnknown::Release} $1 ""
      ${EndIf}
    !endif
    DeleteRegValue HKCU "${REG_RUN}" "${PRODUCTNAME}"
    !insertmacro ABOOK_UNASSOCIATE ".abook" "ABook"
    !insertmacro ABOOK_UNASSOCIATE ".abookproj" "ABook.Project"
    !insertmacro ABOOK_NOTIFY_ASSOCIATIONS
    ; Chỗ cài cũ chỉ có ích cho lần cập nhật; gỡ thật thì bỏ, để lần cài sau về chỗ mặc định.
    DeleteRegValue HKCU "${REG_MANUPRODUCT}" ""
    DeleteRegKey /ifempty HKCU "${REG_MANUPRODUCT}"
    DeleteRegKey /ifempty HKCU "${REG_MANU}"
  ${EndIf}
  DeleteRegKey HKCU "${REG_UNINST}"

  ${If} $UpdateMode <> 1
    ; Gỡ là gỡ hết thứ app tải thêm (Studio: Python, thư viện, Ollama riêng + model) và cache của app Qt (QStandardPaths
    ; CacheLocation: org = app = ABook). Dữ liệu người dùng chỉ theo ô "Xoá dữ liệu". Thư viện sách không bao giờ bị đụng.
    !insertmacro ABOOK_STOP_UNDER "$DataLocal\${PRODUCTNAME}\Studio"
    !insertmacro ABOOK_REMOVE_SAFE "$DataLocal\${PRODUCTNAME}\Studio"
    !insertmacro ABOOK_REMOVE_SAFE "$DataLocal\${PRODUCTNAME}\${PRODUCTNAME}"
    ${If} $DeleteDataState = ${BST_CHECKED}
      !insertmacro ABOOK_STOP_UNDER "$DataLocal\${PRODUCTNAME}"
      !insertmacro ABOOK_REMOVE_SAFE "$DataLocal\${PRODUCTNAME}"
    ${EndIf}
  ${EndIf}
  ${If} $PassiveMode = 1
  ${OrIf} $UpdateMode = 1
    SetAutoClose true
  ${EndIf}
SectionEnd
