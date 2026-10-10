RAG-017 — Build experimental NSIS em 2026-10-10

NSIS 3.12 encontrado em C:\Program Files (x86)\NSIS\makensis.exe. Backup do executavel antigo e checksum em %TEMP%\CodeBridge-RAG017-BuildBackup-20261010. Hash antigo SHA256 093796A410B142C420938DB4BB6506BCB879C5D9E0A00551A0F5BEAA5B9023F1.

Compilacao NSIS com /V2 /INPUTCHARSET UTF8 CodeBridge.nsi retornou NSIS_EXIT=0. Binario experimental installer/dist/CodeBridge-Setup.exe: 27200862 bytes; SHA256 20DD51181163E06AEA35586FCA8FE73267C2F677E3358A5410A86B70E55D034F. Checksum atualizado. Inspecao do arquivo com 7z l -slt retornou exit code 0: 83 arquivos Python RAG, inclusive rag/contracts.py e rag/runtime/production_search.py, alem de author_mcp/mcp_server.py e installer/bootstrap.ps1.

Foi corrigida a descoberta do NSIS no gate de preflight. O gate nao prova compilacao sozinho; a evidencia vem do comando e da inspecao descritos. Instalar em ambiente limpo, validar as dependencias Python nativas e comprovar rollback continuam pendentes. Nenhum instalador foi executado, MCP ativo preservado na porta 8765 e RAG-017-J continua BLOCKED.
