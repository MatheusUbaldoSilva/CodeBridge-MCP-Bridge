!include "MUI2.nsh"

!define APP_NAME "CodeBridge"
!define APP_VERSION "2.0.0-prealpha"
!define APP_PUBLISHER "CodeBridge"
!define APP_REGKEY "Software\CodeBridge"
!define APP_UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodeBridge"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "dist\CodeBridge-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\CodeBridge"
InstallDirRegKey HKCU "${APP_REGKEY}" "InstallDir"
RequestExecutionLevel user
Unicode True
SetCompressor /SOLID lzma
Icon "..\assets\codebridge.ico"
UninstallIcon "..\assets\codebridge.ico"
BrandingText "CodeBridge MCP Bridge"

VIProductVersion "2.0.0.0"
VIAddVersionKey /LANG=1046 "ProductName" "CodeBridge"
VIAddVersionKey /LANG=1046 "FileDescription" "Instalador do CodeBridge MCP Bridge"
VIAddVersionKey /LANG=1046 "FileVersion" "2.0.0-prealpha"
VIAddVersionKey /LANG=1046 "ProductVersion" "2.0.0-prealpha"
VIAddVersionKey /LANG=1046 "CompanyName" "CodeBridge"
VIAddVersionKey /LANG=1046 "LegalCopyright" "Copyright (C) 2026 CodeBridge"

!define MUI_ABORTWARNING
!define MUI_ICON "..\assets\codebridge.ico"
!define MUI_UNICON "..\assets\codebridge.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "PortugueseBR"

Section "CodeBridge" SEC_MAIN
  SetShellVarContext current

  SetOutPath "$INSTDIR"
  File "..\requirements.txt"
  File "..\README.md"

  SetOutPath "$INSTDIR\docs"
  File "..\docs\INSTALLER.md"

  SetOutPath "$INSTDIR\app_rewrite"
  File "..\app_rewrite\*.py"

  SetOutPath "$INSTDIR\app_rewrite\web_terminal"
  File /r "..\app_rewrite\web_terminal\*"

  SetOutPath "$INSTDIR\author_mcp"
  File "..\author_mcp\adapter_server.py"
  File "..\author_mcp\http_client.py"
  File "..\author_mcp\mcp_server.py"
  File "..\author_mcp\persistent_ledger.py"
  File "..\author_mcp\protocol.py"
  File "..\author_mcp\runtime_client.py"
  File "..\author_mcp\requirements.txt"

  SetOutPath "$INSTDIR\assets"
  File "..\assets\*.*"

  SetOutPath "$INSTDIR\installer"
  File "bootstrap.ps1"
  File "company_setup.py"

  SetOutPath "$INSTDIR\tools"
  File "payload\tools\tunnel-client.exe"
  File "payload\tools\cloudflared.exe"

  DetailPrint "Preparando runtime Python e dependencias do CodeBridge..."
  nsExec::Exec '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\installer\bootstrap.ps1" -InstallRoot "$INSTDIR"'
  Pop $0
  StrCmp $0 "0" bootstrap_ok
    MessageBox MB_ICONSTOP|MB_OK "Falha ao preparar o runtime do CodeBridge.$\r$\nConsulte $LOCALAPPDATA\CodeBridge-MCP-Bridge\installer.log."
    Abort
  bootstrap_ok:

  WriteRegStr HKCU "${APP_REGKEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${APP_UNINSTKEY}" "DisplayName" "CodeBridge"
  WriteRegStr HKCU "${APP_UNINSTKEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${APP_UNINSTKEY}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "${APP_UNINSTKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${APP_UNINSTKEY}" "DisplayIcon" "$INSTDIR\assets\codebridge.ico"
  WriteRegStr HKCU "${APP_UNINSTKEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${APP_UNINSTKEY}" "NoModify" 1
  WriteRegDWORD HKCU "${APP_UNINSTKEY}" "NoRepair" 1
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  IfSilent shortcuts_done
    CreateDirectory "$SMPROGRAMS\CodeBridge"
    CreateShortcut "$SMPROGRAMS\CodeBridge\CodeBridge.lnk" "$INSTDIR\runtime\python\pythonw.exe" '"$INSTDIR\app_rewrite\main.py"' "$INSTDIR\assets\codebridge.ico" 0 SW_SHOWNORMAL "" "CodeBridge MCP Bridge"
    CreateShortcut "$SMPROGRAMS\CodeBridge\Configurar CodeBridge.lnk" "$INSTDIR\runtime\python\pythonw.exe" '"$INSTDIR\installer\company_setup.py"' "$INSTDIR\assets\codebridge.ico" 0 SW_SHOWNORMAL "" "Configurar CodeBridge"
    CreateShortcut "$DESKTOP\CodeBridge 2.0 - MCP Bridge.lnk" "$INSTDIR\runtime\python\pythonw.exe" '"$INSTDIR\app_rewrite\main.py"' "$INSTDIR\assets\codebridge.ico" 0 SW_SHOWNORMAL "" "CodeBridge MCP Bridge"
    FileOpen $1 "$INSTDIR\shortcuts.created" w
    FileWrite $1 "created"
    FileClose $1
  shortcuts_done:

  IfSilent config_done
    ExecWait '"$INSTDIR\runtime\python\pythonw.exe" "$INSTDIR\installer\company_setup.py"'
  config_done:
SectionEnd

Section "Uninstall"
  SetShellVarContext current

  IfFileExists "$INSTDIR\shortcuts.created" 0 skip_shortcut_cleanup
    Delete "$DESKTOP\CodeBridge 2.0 - MCP Bridge.lnk"
    Delete "$SMPROGRAMS\CodeBridge\CodeBridge.lnk"
    Delete "$SMPROGRAMS\CodeBridge\Configurar CodeBridge.lnk"
    RMDir "$SMPROGRAMS\CodeBridge"
  skip_shortcut_cleanup:

  DeleteRegKey HKCU "${APP_UNINSTKEY}"
  DeleteRegKey HKCU "${APP_REGKEY}"
  RMDir /r "$INSTDIR"
SectionEnd
