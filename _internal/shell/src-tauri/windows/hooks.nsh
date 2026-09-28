; Hook của bộ cài NSIS (tauri.conf.json > bundle.windows.nsis.installerHooks).
;
; Liên kết .abook: macro APP_ASSOCIATE của Tauri sao lưu giá trị đang có của .abook trước khi ghi giá trị của mình - kể
; cả khi giá trị ấy đã là của chính ABook (bản cập nhật cài đè bản cũ, không gỡ trước). Sau một lần cập nhật, bản sao
; lưu trỏ vào chính ABook, và gỡ app xong .abook vẫn trỏ vào "ABook" không còn tồn tại. Thử 28-09: cài 0.1.0, cập nhật
; lên 0.1.1, gỡ -> sót đúng như thế. Sửa: giữ bản sao lưu gốc qua các lần cập nhật, gỡ xong thì dọn phần của mình.

Var AbookAssociationBackup

!macro NSIS_HOOK_PREINSTALL
  ReadRegStr $AbookAssociationBackup SHCTX "Software\Classes\.abook" "ABook_backup"
  ReadRegStr $0 SHCTX "Software\Classes\.abook" ""
  ${If} $0 != "ABook"
    ; Chưa phải của ABook: đây mới là giá trị "trước khi cài" thật.
    StrCpy $AbookAssociationBackup $0
  ${EndIf}
!macroend

!macro NSIS_HOOK_POSTINSTALL
  WriteRegStr SHCTX "Software\Classes\.abook" "ABook_backup" $AbookAssociationBackup
!macroend

; Gỡ là gỡ hết (chủ sách 28-09: "phụ thuộc nằm hoàn toàn bên trong app, gỡ thì gỡ hết"). Mọi thứ app tải thêm nằm trong
; %LOCALAPPDATA%\ABook\Studio (Python, thư viện, Ollama riêng + model, Git, cache) và bộ nhớ đệm WebView2 nằm trong
; %LOCALAPPDATA%\<mã app> - cả hai LUÔN xoá. Dữ liệu cá nhân (%LOCALAPPDATA%\ABook: chỗ đang nghe, dấu trang, thiết bị
; đã ghép, tuỳ chọn) chỉ xoá khi người dùng tích ô "xoá dữ liệu" của bộ gỡ - gỡ nhầm rồi cài lại không mất chỗ đang nghe.
; Thư viện sách (thư mục người dùng chọn) không bao giờ bị đụng.

; Dừng mọi tiến trình chạy TỪ một thư mục (file đang chạy thì không xoá được). Theo đường dẫn file chạy, không theo tên -
; pythonw.exe, ollama.exe của người dùng ở chỗ khác không bị đụng. ($$ là dấu $ của PowerShell.) Chừa CHÍNH bộ gỡ (cha
; của PowerShell này): bộ cài bản mới gọi bộ gỡ chạy tại chỗ trong thư mục cài (`_?=`) - thử 28-09, không chừa thì bộ gỡ
; tự giết mình, trả -1, và nâng cấp kiểu "gỡ trước khi cài" hỏng.
!macro ABOOK_STOP_PROCESSES_UNDER FOLDER
  nsExec::Exec `powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$$root = '${FOLDER}' + '\'; $$uninstaller = (Get-CimInstance Win32_Process -Filter ('ProcessId=' + $$PID)).ParentProcessId; Get-CimInstance Win32_Process | Where-Object { $$_.ProcessId -ne $$uninstaller -and $$_.ExecutablePath -and $$_.ExecutablePath.StartsWith($$root, [StringComparison]::OrdinalIgnoreCase) } | ForEach-Object { Stop-Process -Id $$_.ProcessId -Force -ErrorAction SilentlyContinue }"`
  Pop $0
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  ; Host Python nhúng của app (con của ABook.exe) - bộ cài của Tauri chỉ dừng ABook.exe.
  !insertmacro ABOOK_STOP_PROCESSES_UNDER "$INSTDIR"
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

    ; Gỡ vì đang CÀI LẠI: bộ cài bản mới (tự tải về, không qua bộ cập nhật) mặc định chọn "gỡ trước khi cài" và gọi
    ; thẳng bộ gỡ này - khi ấy tiến trình ÔNG của PowerShell dưới đây là "ABook_x.y.z_x64-setup.exe". Giữ Studio (20 GB,
    ; người ta chỉ muốn nâng cấp). Gỡ thật (Cài đặt Windows, uninstall.exe) thì xoá. Mã thoát 3 = đang cài lại.
    nsExec::Exec `powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$$me = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $$PID); $$un = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $$me.ParentProcessId); $$gp = $$null; if ($$un) { $$gp = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $$un.ParentProcessId) }; if ($$gp -and $$gp.Name -match 'setup|abook') { exit 3 } else { exit 0 }"`
    Pop $0
    ${If} $0 != 3
      SetShellVarContext current
      !insertmacro ABOOK_STOP_PROCESSES_UNDER "$LOCALAPPDATA\ABook\Studio"
      RMDir /r "$LOCALAPPDATA\ABook\Studio"
      RMDir /r "$LOCALAPPDATA\${BUNDLEID}"
      ${If} $DeleteAppDataCheckboxState = 1
        RMDir /r "$LOCALAPPDATA\ABook"
      ${EndIf}
    ${EndIf}
  ${EndIf}
!macroend
