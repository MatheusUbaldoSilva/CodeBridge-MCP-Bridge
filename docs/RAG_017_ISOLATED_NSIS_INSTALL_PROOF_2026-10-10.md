RAG-017 — Instalador NSIS isolado: execução validada em 2026-10-10

O arquivo installer/RAG017_Isolated_Test.nsi é um instalador exclusivamente de teste, que copia fontes do pacote rag/, mcp_server.py, rag_bridge.py e bootstrap.ps1. Não possui rotinas de registro, criação de atalhos, inicialização de processos, bootstrap de dependências ou desinstalação do CodeBridge principal.

A primeira revisão de testes falhou por barras invertidas duplicadas no arquivo NSIS. Normalizadas as barras, os 2 testes de segurança passaram. Build com NSIS 3.12: exit code 0; binário de teste 196873 bytes. Execução em pasta inédita %TEMP%\CodeBridge-RAG017-Isolated-Retest-20261010 por Start-Process -Wait: exit code 0; 83 arquivos Python RAG presentes; comparação de HKCU:\Software\CodeBridge antes/depois sem mudanças; listener MCP original 8765 preservado.

Limites: esta é apenas uma prova do payload-only sem dependências instaladas, sem executores MCP em produção e sem ativação experimental. A checagem de registro cobre a chave examinada, não todos os efeitos externos possíveis. Rollback integral do NSIS principal e validação do Python embutido ainda pendentes. Build dual e RAG-017-J BLOCKED.
