; RAG-017 isolated payload-only test installer. NEVER installs application runtime.
Unicode True
Name "CodeBridge RAG-017 Isolated Payload Test"
OutFile "dist\CodeBridge-RAG017-Isolated-Test.exe"
InstallDir "$TEMP\CodeBridge-RAG017-NSIS-Isolated"
RequestExecutionLevel user
SilentInstall silent
Section "Payload test only"
  SetOutPath "$INSTDIR\rag"
  File /r "..\rag\*.py"
  SetOutPath "$INSTDIR\author_mcp"
  File "..\author_mcp\mcp_server.py"
  File "..\author_mcp\rag_bridge.py"
  SetOutPath "$INSTDIR\installer"
  File "bootstrap.ps1"
SectionEnd
