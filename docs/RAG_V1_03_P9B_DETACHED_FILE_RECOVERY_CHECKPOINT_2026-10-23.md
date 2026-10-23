# RAG V1.03 P9-B ? Checkpoint de rollback externo de arquivos

Data: 2026-10-23
Estado: P9-B ABERTO ? NSIS OFICIAL NAO EXECUTADO

## Resultado observado

- CodeBridge 2.0.11-prealpha READY durante desenvolvimento
- Gate externo rejeitou cutover devido a GUI/MCP ativos
- Instalacao atual nao foi interrompida nem atualizada
- Snapshot anterior: 236 arquivos existentes e 22 destinos novos
- Regressao: 362 testes P9B PASS usando psutil externo de staging
- Tres alteracoes locais historicas preservadas

## Incrementos tecnicos

- 26c0620: rejeitar links simbolicos ancestrais dos atalhos
- adb7f03: isolar laboratorio do diretorio real instalado
- 17c6913: validar ancestrais na pos-verificacao de atalhos
- 973f842: comparar SHA256 dos destinos novos antes de possivel remocao
- 9146b54: reunir evidencias independentes arquivo preimagem journal parada ownership
- a682f8a: executor de rollback de arquivos jornalado e desabilitado por padrao
- eb651c6: validar historico de recuperacao e bloquear replay concluido
- 1794fc4: teste de interrupcao e retomada idempotente com journal duravel

## Limites e proximos passos

Rollback de arquivos NAO significa rollback integral NSIS. HKCU e atalhos precisam de supervisor externo e pos-verificacao independente.

DETACHED_FILES_RESTORED_SHELL_PENDING indica somente arquivos restaurados. Nao autoriza declarar instalacao recuperada.

Pendencias:
1. Validar supervisor externo elevado e desligamento real controlado
2. Integrar restauracao completa de registro e atalhos com journal duravel
3. Provar crash/replay do conjunto completo
4. Executar apenas em janela aprovada o NSIS oficial verificado
5. Validar CBMCP/1 publico, bootstrap RAG e fila/scheduler
6. Auditoria Git pos-commit e patch notes no fechamento

## Nao tocar em arquivos anteriores

- benchmarks/rag017_code_only_extended_smoke.json
- docs/RAG_017_J_VM_ROLLBACK_RUNBOOK_2026-10-10.md
- rag/runtime/incremental_installed_queue_init.py

Nao executar NSIS dentro do MCP a ser desligado.
Nao apagar SQLite WAL/SHM nem modificar o indice RAG ativo.
