# P9-B ? Handoff de continuidade: rollback e recupera??o

Data: 2026-10-22
Estado: P9-B ABERTA; PRODUCAO NAO ATUALIZADA.
Branch: rag-017-optimized-inference-after-candidate
HEAD verificado na preparacao: 7859f76425570787404df0791525239bae04e285

## Evidencia operacional ja comprovada

- Parada graciosa real de GUI/MCP/adapter/tunnel e recuperacao
  por agente elevado externo em ciclo anterior.
- Reconexao publica do MCP CBMCP/1 confirmada apos reboot
  supervisionado; esta prova nao e prova de update NSIS.
- RAG instalado READY, 211 documentos, 8774 chunks.
- Regressao integrada 264 testes PASS nesta continuacao.
- Git na branch de desenvolvimento sincronizado com origin.
- Remote Desktop independente conectado e guard mostra
  GUI PID8516, adapter PID2800, MCP PID11024 e tunnel PID10600.
- Nenhum NSIS executado, nenhuma mutacao no registro HKCU,
  nos atalhos reais ou no RAG nesta fase.

## Backup do preview limpo (na maquina Windows)

Diretorio sob LOCALAPPDATA:
CodeBridge-MCP-Bridge/release_staging/P9B_CURRENT_2d99ed4

Instalador: CodeBridge-P9B-CURRENT-2d99ed4-GUARDED-Preview.exe
SHA256: 0898124096989d62fd438395bc6f01baa031516f2579860daf275471272e3223
Commit exato usado no build: 2d99ed46435b44d25d5200cfa74a18f1ec24c4a8

ZIP dos 236 arquivos existentes e 22 novos destinos:
FULL_NSIS_PREINSTALL_SNAPSHOT.zip
SHA256: ad8d8c6397a1421a5858fb2f1b1746cfbda941d378cedd7b268b3931bb5fdf0d

ZIP dos dois registros HKCU e cinco atalhos:
NSIS_SHELL_REGISTRY_SHORTCUT_SNAPSHOT.zip
SHA256: 7d2e39b928e829b7be8d23e03def48e97127d78e093f183f159c58c633d2e511

Preimagem de crash atual (somente leitura de HKCU/atalhos):
READ_ONLY_LIVE_CRASH_PREIMAGE_20261022.zip
SHA256: 14d201a576a3827925a8fd4819263840c88e569f992f837763d05438443749b9

## Como continuar com seguranca

1. Conferir Git, status do instalador e as tres alteracoes
   locais antigas sem tocar nelas.
2. Construir coordenador independente capaz de consumir ZIP de
   preimagem e journal apos uma interrupcao real, com guard
   de processos e confer?ncia posterior. Prova de scratch
   ja executada, mas nao provar como rollback real concluido.
3. Tratar criacao/remocao de 22 novos arquivos somente se seus
   hashes e propriedade pelo NSIS forem confirmados.
4. Executar NSIS oficial somente com controlador elevado
   independente, snapshot integral/restauro provados e guard
   de processos revalidado imediatamente antes da escrita.
5. Verificar instalacao, reconexao publica CBMCP/1, RAG READY
   e bootstrap da fila incremental apenas em modo PLAN_ONLY
   antes de ativar qualquer worker.
6. Encerrar P9-B somente apos auditoria Git, diff, commit e
   auditoria pos-commit. Depois realizar merge para main e
   publicacao oficial do instalador.

## Arquivos locais anteriores protegidos (nao incluir sem auditoria)

- benchmarks/rag017_code_only_extended_smoke.json (modified)
- docs/RAG_017_J_VM_ROLLBACK_RUNBOOK_2026-10-10.md (untracked)
- rag/runtime/incremental_installed_queue_init.py (untracked)

Nao assumir que preview compilado equivale a versao oficial,
nem que recuperacao de scratch garante recuperacao de producao.
