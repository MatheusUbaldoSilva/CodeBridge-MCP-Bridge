# CodeBridge RAG V1.03 — P9-B: patch notes de identidade de processos

Data: 2026-10-22
Status: P9-B ABERTA. Auditoria de seguranca e testes; nenhuma atualizacao NSIS aplicada.

## Mudancas implementadas

- Commit 9d7e496: installer/rag_p9b_mcp_process_topology.py agora registra create_time
  e recusa atribuir MCP a um processo pai criado depois do proprio filho.
  Reporta parent_creation_time_conflicts sem autorizar encerramento.
- Commit a238dc3: app_rewrite/author_mcp_manager.py valida cronologia ancestral
  e evita confundir PID reutilizado com dono vivo do MCP.
- Commit 6437bd6: app_rewrite/author_mcp_manager.py recusa reciclagem se
  identidade ancestral for desconhecida ou houver AccessDenied.
- Commit ce75020: revalida create_time dos PIDs imediatamente antes de
  reciclagem, abortando todo o lote em caso de reutilizacao de PID.
- Regressao: tests/test_rag_p9b_mcp_process_topology.py adicionou dois casos;
  tests/test_process_lifecycle_recovery.py adicionou dois casos.

## Evidencias

- 9/9 testes de topologia: PASS.
- 11/11 testes de recuperacao com Python portatil (psutil): PASS.
- 5/5 testes do preflight NSIS: PASS.
- Suite integrada P9-B + lifecycle + process guard: 86 testes PASS.
- Auditoria do sistema real com Python portatil: MCP PID 9300 independente
  da GUI PID 1376 e pai registrado ausente. Houve ao menos um conflito
  cronologico de PID no inventario global do Windows.
- Hash NSIS revalidado e492b2b9287201a4cdd9b306143868d1ab976a8f1b1ec427875dc3216b891af9.
- Hash snapshot revalidado daab08743893cd06914e5ea7c2de7cec35a5119342e479476b9d69fb3f77c93c.
- Baseline instalado INSTALLED_BASELINE_MATCH de 236 arquivos; arquivo de
  reversao verificado para 258 destinos NSIS, sem alterar a instalacao.
- Remote Desktop MatheusPC online e executando leitura externa simples:
  INDEPENDENT_RECOVERY_CHANNEL_READY; GUI e MCP ainda vivos.
- Git: commits 9d7e496, a238dc3, 6437bd6 e ce75020 publicados na branch de desenvolvimento.

## Limitacoes e proximos passos

- Evidencia de PID/processo nao demonstra quiescencia de handles ou mmap.
- Python global 3.13 nao tem psutil; as suites dependentes rodam com Python
  portatil do CodeBridge. Nao instalar pacotes globais para contornar isso.
- Nao houve encerramento de GUI/MCP, troca de arquivos instalados,
  inicializacao de fila, ativacao de scheduler ou publicacao de indice.
- Proxima acao: confirmar supervisor independente para janela real e
  procedimentos oficiais de encerramento, install, rollback e reconexao.
- Preservar os tres arquivos locais anteriores sem stage, overwrite ou clean.
- Gate P9-B permanece BLOCKED ate prova real de parada e reinicio seguros.

Nao confundir progresso de testes com aprovacao de producao.
