# An explicit installer-scoped environment flag inherited by its uninstaller child.
if ($env:ABOOK_INSTALLER_UPGRADE -eq '1') { exit 3 }
exit 0
