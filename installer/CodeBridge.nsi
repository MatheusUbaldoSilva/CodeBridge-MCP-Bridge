!include "MUI2.nsh"
!include "WinMessages.nsh"

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
ShowInstDetails show
Icon "..\assets\codebridge.ico"
UninstallIcon "..\assets\codebridge.ico"
BrandingText "CodeBridge MCP Bridge"

VIProductVersion "2.0.0.0"
VIAddVersionKey /LANG=1046 "ProductName" "CodeBridge"
VIAddVersionKey /LANG=1046 "FileDescription" "Instalador e atualizador do CodeBridge MCP Bridge"
VIAddVersionKey /LANG=1046 "FileVersion" "2.0.0-prealpha"
VIAddVersionKey /LANG=1046 "ProductVersion" "2.0.0-prealpha"
VIAddVersionKey /LANG=1046 "CompanyName" "CodeBridge"
VIAddVersionKey /LANG=1046 "LegalCopyright" "Copyright (C) 2026 CodeBridge"

Var IsUpdate

!define MUI_ABORTWARNING
!define MUI_CUSTOMFUNCTION_GUIINIT GuiInit
!define MUI_ICON "..\assets\codebridge.ico"
!define MUI_UNICON "..\assets\codebridge.ico"
!define MUI_BGCOLOR "0B1117"
!define MUI_TEXTCOLOR "E8EEF4"
!define MUI_INSTFILESPAGE_COLORS "E8EEF4 0B1117"
!define MUI_INSTFILESPAGE_PROGRESSBAR "colored"
!define MUI_WELCOMEPAGE_TITLE "CodeBridge Setup"
!define MUI_WELCOMEPAGE_TEXT "Instale o CodeBridge em um computador novo ou atualize uma instalação existente sem perder a configuração da empresa, API key protegida, Tunnel ID ou SSH."

!insertmacro MUI_PAGE_WELCOME

!define MUI_PAGE_CUSTOMFUNCTION_PRE DirectoryPagePre
!define MUI_PAGE_CUSTOMFUNCTION_SHOW DirectoryPageShow
!insertmacro MUI_PAGE_DIRECTORY

!define MUI_PAGE_CUSTOMFUNCTION_SHOW InstFilesShow
!insertmacro MUI_PAGE_INSTFILES

!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "PortugueseBR"

Function ApplyOuterDark
  SetCtlColors $HWNDPARENT 0xE8EEF4 0x0B1117

  GetDlgItem $0 $HWNDPARENT 1034
  SetCtlColors $0 0xE8EEF4 0x0B1117

  GetDlgItem $0 $HWNDPARENT 1037
  SetCtlColors $0 0xE8EEF4 0x0B1117

  GetDlgItem $0 $HWNDPARENT 1038
  SetCtlColors $0 0xAFC0CC 0x0B1117

  GetDlgItem $0 $HWNDPARENT 1028
  SetCtlColors $0 0x9FB0BB 0x0B1117

  GetDlgItem $0 $HWNDPARENT 1256
  SetCtlColors $0 0x9FB0BB 0x0B1117

  GetDlgItem $0 $HWNDPARENT 1
  SetCtlColors $0 0xF1F6F9 0x18232E
  GetDlgItem $0 $HWNDPARENT 2
  SetCtlColors $0 0xF1F6F9 0x18232E
  GetDlgItem $0 $HWNDPARENT 3
  SetCtlColors $0 0xF1F6F9 0x18232E

  GetDlgItem $0 $HWNDPARENT 1035
  SetCtlColors $0 0x33414D 0x0B1117
  GetDlgItem $0 $HWNDPARENT 1045
  SetCtlColors $0 0x33414D 0x0B1117

  ; Windows 10/11: solicita barra de título escura. Em versões antigas a chamada é ignorada.
  System::Call 'dwmapi::DwmSetWindowAttribute(p $HWNDPARENT, i 20, *i 1, i 4)i.r0'
FunctionEnd

Function .onInit
  StrCpy $IsUpdate "0"

  ReadRegStr $0 HKCU "${APP_REGKEY}" "InstallDir"
  StrCmp $0 "" init_done
  IfFileExists "$0\app_rewrite\main.py" 0 init_done

  StrCpy $INSTDIR "$0"
  StrCpy $IsUpdate "1"

init_done:
FunctionEnd

Function GuiInit
  Call ApplyOuterDark

  StrCmp $IsUpdate "1" 0 gui_install
    SendMessage $HWNDPARENT ${WM_SETTEXT} 0 "STR:Atualizar CodeBridge"
    Goto gui_done
  gui_install:
    SendMessage $HWNDPARENT ${WM_SETTEXT} 0 "STR:Instalar CodeBridge"
  gui_done:
FunctionEnd

Function DirectoryPagePre
  StrCmp $IsUpdate "1" 0 show_directory
  Abort
show_directory:
FunctionEnd

Function DirectoryPageShow
  Call ApplyOuterDark
  FindWindow $0 "#32770" "" $HWNDPARENT
  SetCtlColors $0 0xE8EEF4 0x0B1117

  GetDlgItem $1 $0 1019
  SetCtlColors $1 0xE8EEF4 0x0B1117
  GetDlgItem $1 $0 1001
  SetCtlColors $1 0xE8EEF4 0x111922
  GetDlgItem $1 $0 1024
  SetCtlColors $1 0xE8EEF4 0x0B1117
  GetDlgItem $1 $0 1006
  SetCtlColors $1 0xE8EEF4 0x0B1117
FunctionEnd

Function InstFilesShow
  Call ApplyOuterDark
  FindWindow $0 "#32770" "" $HWNDPARENT
  SetCtlColors $0 0xE8EEF4 0x0B1117

  GetDlgItem $1 $0 1006
  SetCtlColors $1 0xE8EEF4 0x0B1117

  GetDlgItem $1 $0 1004
  SetCtlColors $1 0xE8EEF4 0x111922

  GetDlgItem $1 $0 1027
  SetCtlColors $1 0xE8EEF4 0x0B1117

  GetDlgItem $1 $0 1016
  SetCtlColors $1 0xE8EEF4 0x0B1117
FunctionEnd

Section "CodeBridge" SEC_MAIN
  SetShellVarContext current

  StrCmp $IsUpdate "1" 0 installing
    DetailPrint "Atualizando CodeBridge em $INSTDIR..."
    Goto mode_ready
  installing:
    DetailPrint "Instalando CodeBridge em $INSTDIR..."
  mode_ready:

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
  File "updater.py"

  SetOutPath "$INSTDIR\tools"
  File "payload\tools\tunnel-client.exe"
  File "payload\tools\cloudflared.exe"

  DetailPrint "Preparando runtime Python e dependências do CodeBridge..."
  nsExec::Exec '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\installer\bootstrap.ps1" -InstallRoot "$INSTDIR"'
  Pop $0
  StrCmp $0 "0" bootstrap_ok
    MessageBox MB_ICONSTOP|MB_OK "Falha ao preparar o runtime do CodeBridge.$\r$\nConsulte $LOCALAPPDATA\CodeBridge-MCP-Bridge\installer.log."
    Abort
  bootstrap_ok:

  WriteRegStr HKCU "${APP_REGKEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${APP_REGKEY}" "Version" "${APP_VERSION}"
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
    CreateShortcut "$SMPROGRAMS\CodeBridge\Atualizar CodeBridge.lnk" "$INSTDIR\runtime\python\pythonw.exe" '"$INSTDIR\installer\updater.py"' "$INSTDIR\assets\codebridge.ico" 0 SW_SHOWNORMAL "" "Atualizar CodeBridge"
    CreateShortcut "$DESKTOP\CodeBridge 2.0 - MCP Bridge.lnk" "$INSTDIR\runtime\python\pythonw.exe" '"$INSTDIR\app_rewrite\main.py"' "$INSTDIR\assets\codebridge.ico" 0 SW_SHOWNORMAL "" "CodeBridge MCP Bridge"
    FileOpen $1 "$INSTDIR\shortcuts.created" w
    FileWrite $1 "created"
    FileClose $1
  shortcuts_done:

  ; Em atualização, nunca força o usuário a refazer a configuração.
  StrCmp $IsUpdate "1" config_done
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
    Delete "$SMPROGRAMS\CodeBridge\Atualizar CodeBridge.lnk"
    RMDir "$SMPROGRAMS\CodeBridge"
  skip_shortcut_cleanup:

  DeleteRegKey HKCU "${APP_UNINSTKEY}"
  DeleteRegKey HKCU "${APP_REGKEY}"
  RMDir /r "$INSTDIR"
SectionEnd
