RAG-017 — Atalho CodeBridge MCP RAG (2026-10-10)

Criado atalho na área de trabalho do Windows `CodeBridge MCP RAG.lnk`, apontando para PowerShell que executa `benchmarks/CodeBridge_MCP_RAG_Lab.ps1`; ícone original `assets/codebridge.ico`. O script é um laboratório de diagnóstico: verifica imports e dependências do ambiente virtual temporário e lê o canário Qdrant Local persistido no diretório TEMP. Não inicia MCP alternativo, não atualiza o aplicativo e não ativa RAG de produção.

Teste direto do script: gate de dependências `deployment_ready=true` no venv isolado, leitura Qdrant `passed=true`, listener original 8765 ativo, `LAB_EXIT=0`. Observação: o atalho depende dos diretórios TEMP do laboratório; se removidos, o script acusa ambiente ausente e encerra em falha. O script não é GUI RAG e não substitui o CodeBridge original. RAG-017-J segue BLOCKED.
