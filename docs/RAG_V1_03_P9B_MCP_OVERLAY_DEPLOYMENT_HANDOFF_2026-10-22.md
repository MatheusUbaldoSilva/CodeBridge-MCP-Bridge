# RAG V1.03 — P9-B | Handoff de implantacao MCP com overlay reversivel

Data: 2026-10-22
Branch: rag-017-optimized-inference-after-candidate
Status: PACOTE DE IMPLANTACAO VALIDADO OFFLINE; NAO APLICADO AO MCP ATIVO.

## Objetivo

Disponibilizar no MCP instalado a ferramenta oficial
codebridge_rag_queue_bootstrap ja publicada na fonte Git.
A ferramenta nao habilita scheduler nem worker; a fila so pode
ser inicializada depois por chamada propria, autorizada e escopada.

## Diagnostico da instalacao

- O servidor MCP publico ativo usa:
  %LOCALAPPDATA%\Programs\CodeBridge\author_mcp\mcp_server.py.
- A fonte Git reside em:
  C:\Users\Matheus\CodeBridge-MCP-Bridge.
- A instalacao ainda possui mcp_server.py antigo e nao inclui alguns
  modulos incrementais da P9-B.
- Por isso uma troca isolada de mcp_server.py nao e segura:
  os imports de bootstrap falhariam na instalacao.
- A tentativa de inspecao adicional do caminho de reinicio controlado
  foi bloqueada pela ferramenta; nao foi contornada.
- O MCP instalado NAO foi reiniciado nem atualizado nesta sessao.

## Entregas versionadas

- installer/rag_p9b_mcp_overlay.py:
  pacote offline com sete arquivos, fontes byte a byte derivadas do
  commit Git e SHA-256, e backup byte-exato dos arquivos preexistentes.
  Normaliza CRLF somente para validar o worktree Windows; o pacote
  utiliza os bytes canonicos dos objetos Git.
  Recusa alteracoes nao commitadas, destino dentro da instalacao,
  overwrite de pacote, fontes ausentes, symlinks de destino e
  divergencia no backup instalado.
- tests/test_rag_p9b_mcp_overlay.py:
  valida pacote, backup, hash, nao alteracao da instalacao,
  CRLF, arquivo sujo, sobrescrita e integridade.
- benchmarks/rag_p9b_offline_overlay_smoke.py:
  extrai a sobreposicao para diretorio TEMP, sobre uma copia
  dos modulos Python instalados. Usa o Python portatil existente
  para carregar o MCP e confirmar apenas execute=false.
- tests/test_rag_p9b_offline_overlay_smoke.py:
  negativa para pacote invalido, Python ausente e falha de import,
  confirmando que o smoke nao declara implantacao ao vivo.

## Prova real executada

- STAGED_PORTABLE_MCP_OK:
  import MCP com Python portatil funcionou usando arquivos staged.
- OFFLINE_MCP_OVERLAY_SMOKE_PASS:
  tool=codebridge_rag_queue_bootstrap, count=18,
  preview_state=BOOTSTRAP_PLAN_ONLY,
  public_generation=v1_delta_1ae1d01ea84f4e.
- Pacote de sete arquivos validado no armazenamento LOCALAPPDATA:
  %LOCALAPPDATA%\CodeBridge-MCP-Bridge\release_staging\P9B_16fecab\MCP_P9B_REVERTIBLE.zip
- SHA-256 do ZIP:
  417a7282746c0e3f5055f37c1f6eef0bdbe7287705c87631fd28f7877531b9b7
- Estado do pacote: OVERLAY_VERIFIED_AND_NOT_INSTALLED.
- Testes unitarios: 8 do empacotador + 4 do smoke, todos PASS.
- Nenhum arquivo da instalacao, index ativo ou fila de producao
  foi alterado durante esses procedimentos.

## Condicoes para continuar sem risco

1. Antes de atualizar MCP, comprovar caminho de gerenciamento e reinicio,
   restauração do arquivo anterior e conexao alternativa independente.
2. Confirmar que o ZIP ainda verifica exatamente os bytes instalados.
   Se a instalacao mudou, ABORTAR o overlay e auditar de novo.
3. Aplicar atualizacao pela rotina oficial do CodeBridge quando recuperacao
   estiver comprovada; nao contornar bloqueios da ferramenta.
4. Reiniciar exclusivamente pelo ciclo de vida oficial do MCP;
   confirmar nova ferramenta via cliente MCP realmente conectado.
5. Chamar codebridge_rag_queue_bootstrap sem parametros primeiro.
   Somente chamar execute=true usando aprovacao vinculada ao ponteiro
   depois do preflight e verificacao publica.
6. Comprovar SQLite v2 e fence v1 presentes, sem jobs e sem scheduler.
7. Executar um UNICO job real supervisionado em etapa separada.
8. Somente apos validacao total executar auditoria Git, patch notes
   e fechamento P9-B.

## Integridade e pendencias

- O RAG publico permanece READY na geracao
  v1_delta_1ae1d01ea84f4e (211 documentos, 8774 chunks).
- Fila real jobs/incremental_jobs.sqlite3 continua ausente.
- Ferramenta nova existe em Git e no bundle, nao no MCP ativo.
- Trabalhos historicos preexistentes permanecem intocados:
  benchmark JSON modificado, rollback runbook nao versionado e
  rascunho incremental_installed_queue_init.py nao versionado.

## Commits desta sessao

- 4d6b767: pacote offline com backup e hash.
- 16fecab: normalizacao CRLF e bytes canonicos Git.
- cc85074: importacao/smoke com Python portatil instalado.

P9-B continua EM ANDAMENTO. Esta evidencia nao concede ativacao.
