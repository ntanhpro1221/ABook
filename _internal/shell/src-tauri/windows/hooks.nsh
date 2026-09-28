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

!macro NSIS_HOOK_POSTUNINSTALL
  ${If} $UpdateMode <> 1
    ; APP_UNASSOCIATE đã trả lại giá trị gốc; gốc là "không có gì" thì bỏ luôn giá trị rỗng và khoá rỗng.
    ReadRegStr $0 SHCTX "Software\Classes\.abook" ""
    ${If} $0 == ""
      DeleteRegValue SHCTX "Software\Classes\.abook" ""
    ${EndIf}
    DeleteRegValue SHCTX "Software\Classes\.abook" "ABook_backup"
    DeleteRegKey /ifempty SHCTX "Software\Classes\.abook"
  ${EndIf}
!macroend
