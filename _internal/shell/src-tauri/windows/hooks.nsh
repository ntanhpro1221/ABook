; Hook của bộ cài NSIS (tauri.conf.json > bundle.windows.nsis.installerHooks).
;
; Liên kết .abook: macro APP_ASSOCIATE của Tauri sao lưu giá trị đang có của .abook trước khi ghi giá trị của mình - kể
; cả khi giá trị ấy đã là của chính ABook (bản cập nhật cài đè bản cũ, không gỡ trước). Sau một lần cập nhật, bản sao
; lưu trỏ vào chính ABook, và gỡ app xong .abook vẫn trỏ vào "ABook" không còn tồn tại. Thử 28-09: cài 0.1.0, cập nhật
; lên 0.1.1, gỡ -> sót đúng như thế. Sửa: giữ bản sao lưu gốc qua các lần cập nhật, gỡ xong thì dọn phần của mình.

; .abookproj (dự án Studio đóng gói, ProgId "ABook.Project") cùng cách.

Var AbookAssociationBackup
Var AbookProjAssociationBackup
!define ABOOK_HOOK_DIR "${__FILEDIR__}"

; Tauri calls the old uninstaller from PageReinstall, BEFORE PREINSTALL. MUI GUI init runs
; before that page, including passive mode. A silent Tauri install skips PageReinstall;
; updater invocations additionally carry Tauri's explicit /UPDATE flag.
!define MUI_CUSTOMFUNCTION_GUIINIT AbookInstallerContext
Function AbookInstallerContext
  System::Call 'kernel32::SetEnvironmentVariableW(w "ABOOK_INSTALLER_UPGRADE", w "1") i .r0'
FunctionEnd

; Check the actual saved library before EVERY recursive removal. Unreadable settings preserve data.
!macro ABOOK_REMOVE_SAFE FOLDER
  System::Call 'kernel32::SetEnvironmentVariableW(w "ABOOK_DELETE_TARGET", w "${FOLDER}") i .r0'
  ${If} $0 == 0
    Abort
  ${EndIf}
  nsExec::Exec 'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\abook-uninstall-guard.ps1"'
  Pop $0
  ${If} $0 == 0
    RMDir /r "${FOLDER}"
  ${Else}
    DetailPrint "Giu thu muc de bao ve thu vien cua ban: ${FOLDER}"
  ${EndIf}
!macroend

!macro NSIS_HOOK_PREINSTALL
  ReadRegStr $AbookAssociationBackup SHCTX "Software\Classes\.abook" "ABook_backup"
  ReadRegStr $0 SHCTX "Software\Classes\.abook" ""
  ${If} $0 != "ABook"
    ; Chưa phải của ABook: đây mới là giá trị "trước khi cài" thật.
    StrCpy $AbookAssociationBackup $0
  ${EndIf}
  ReadRegStr $AbookProjAssociationBackup SHCTX "Software\Classes\.abookproj" "ABook_backup"
  ReadRegStr $0 SHCTX "Software\Classes\.abookproj" ""
  ${If} $0 != "ABook.Project"
    StrCpy $AbookProjAssociationBackup $0
  ${EndIf}
!macroend

!macro NSIS_HOOK_POSTINSTALL
  ; Do not pass upgrade intent to the app launched by the finish page.
  System::Call 'kernel32::SetEnvironmentVariableW(w "ABOOK_INSTALLER_UPGRADE", p 0) i .r0'
  WriteRegStr SHCTX "Software\Classes\.abook" "ABook_backup" $AbookAssociationBackup
  WriteRegStr SHCTX "Software\Classes\.abookproj" "ABook_backup" $AbookProjAssociationBackup
!macroend

; Gỡ là gỡ hết (chủ sách 28-09: "phụ thuộc nằm hoàn toàn bên trong app, gỡ thì gỡ hết"). Mọi thứ app tải thêm nằm trong
; %LOCALAPPDATA%\ABook\Studio (Python, thư viện, Ollama riêng + model, Git, cache) và bộ nhớ đệm WebView2 nằm trong
; %LOCALAPPDATA%\<mã app> - cả hai LUÔN xoá. Dữ liệu cá nhân (%LOCALAPPDATA%\ABook: chỗ đang nghe, dấu trang, thiết bị
; đã ghép, tuỳ chọn; cùng cách sắp cửa sổ ở %APPDATA%\<mã app>) chỉ xoá khi người dùng tích ô "xoá dữ liệu" của bộ gỡ - gỡ nhầm rồi cài lại không mất chỗ đang nghe.
; Thư viện sách (thư mục người dùng chọn) không bao giờ bị đụng.

; Dừng mọi tiến trình chạy TỪ một thư mục (file đang chạy thì không xoá được). Theo đường dẫn file chạy, không theo tên -
; pythonw.exe, ollama.exe của người dùng ở chỗ khác không bị đụng. ($$ là dấu $ của PowerShell.) Chừa CHÍNH bộ gỡ (cha
; của PowerShell này): bộ cài bản mới gọi bộ gỡ chạy tại chỗ trong thư mục cài (`_?=`) - thử 28-09, không chừa thì bộ gỡ
; tự giết mình, trả -1, và nâng cấp kiểu "gỡ trước khi cài" hỏng.
!macro ABOOK_STOP_PROCESSES_UNDER FOLDER
  System::Call 'kernel32::SetEnvironmentVariableW(w "ABOOK_STOP_ROOT", w "${FOLDER}") i .r0'
  ${If} $0 == 0
    MessageBox MB_OK|MB_ICONSTOP "Không đọc được đường dẫn cần gỡ. Bạn hãy chạy lại bộ gỡ."
    Abort
  ${EndIf}
  nsExec::Exec 'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\abook-stop-processes.ps1"'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_OK|MB_ICONSTOP "Không dừng được tiến trình ABook. Bạn hãy đóng app rồi chạy lại bộ gỡ."
    Abort
  ${EndIf}
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  InitPluginsDir
  File /oname=$PLUGINSDIR\abook-stop-processes.ps1 "${ABOOK_HOOK_DIR}\stop_processes.ps1"
  File /oname=$PLUGINSDIR\abook-uninstall-guard.ps1 "${ABOOK_HOOK_DIR}\uninstall_guard.ps1"
  File /oname=$PLUGINSDIR\abook-upgrade-mode.ps1 "${ABOOK_HOOK_DIR}\upgrade_mode.ps1"
  nsExec::Exec 'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\abook-upgrade-mode.ps1"'
  Pop $0
  ${If} $0 == 3
    StrCpy $UpdateMode 1
  ${ElseIf} $0 != 0
    MessageBox MB_OK|MB_ICONSTOP "Chưa xác định được chế độ gỡ. Bạn hãy đóng app rồi chạy lại bộ cài."
    Abort
  ${EndIf}
  ; Host Python nhúng của app (con của ABook.exe) - bộ cài của Tauri chỉ dừng ABook.exe. CHỈ thư mục resources: cài cho
  ; người dùng hiện tại thì $INSTDIR là %LOCALAPPDATA%\ABook, cũng là cha của Studio và dữ liệu người dùng. Dừng cả
  ; $INSTDIR là giết worker Studio đang làm sách (nó sống ngoài app) mỗi khi chạy tay bộ cài bản mới ("gỡ trước khi cài") -
  ; giữa pha phân tích là ra một quyển sách khác. Gỡ thật thì POSTUNINSTALL dừng Studio trước khi xoá.
  !insertmacro ABOOK_STOP_PROCESSES_UNDER "$INSTDIR\resources"
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  ${If} $UpdateMode <> 1
    ; APP_UNASSOCIATE đã trả lại giá trị gốc; gốc là "không có gì" thì bỏ luôn giá trị rỗng và khoá rỗng.
    ReadRegStr $0 SHCTX "Software\Classes\.abook" ""
    ${If} $0 == ""
      DeleteRegValue SHCTX "Software\Classes\.abook" ""
    ${EndIf}
    DeleteRegValue SHCTX "Software\Classes\.abook" "ABook_backup"
    DeleteRegKey /ifempty SHCTX "Software\Classes\.abook"
    ReadRegStr $0 SHCTX "Software\Classes\.abookproj" ""
    ${If} $0 == ""
      DeleteRegValue SHCTX "Software\Classes\.abookproj" ""
    ${EndIf}
    DeleteRegValue SHCTX "Software\Classes\.abookproj" "ABook_backup"
    DeleteRegKey /ifempty SHCTX "Software\Classes\.abookproj"

    SetShellVarContext current
    !insertmacro ABOOK_STOP_PROCESSES_UNDER "$LOCALAPPDATA\ABook\Studio"
    !insertmacro ABOOK_REMOVE_SAFE "$LOCALAPPDATA\ABook\Studio"
    !insertmacro ABOOK_REMOVE_SAFE "$LOCALAPPDATA\${BUNDLEID}"
    ${If} $DeleteAppDataCheckboxState = 1
      !insertmacro ABOOK_STOP_PROCESSES_UNDER "$LOCALAPPDATA\ABook"
      !insertmacro ABOOK_REMOVE_SAFE "$LOCALAPPDATA\ABook"
      ; Kích thước, vị trí cửa sổ (tauri-plugin-window-state).
      !insertmacro ABOOK_REMOVE_SAFE "$APPDATA\${BUNDLEID}"
    ${EndIf}
  ${EndIf}
!macroend
