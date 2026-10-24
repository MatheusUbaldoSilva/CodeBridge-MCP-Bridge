# RAG V1.03-D — Contrato inicial do ciclo de vida do supervisor

Data: 2026-10-21
Estado: LABORATÓRIO SINTÉTICO, SEM AGENDADOR EM PRODUÇÃO
Escopo: máquina de estados do supervisor incremental em laboratório, sem ativação do agendador instalado.

## Alterações

- `rag/runtime/incremental_supervisor_lifecycle.py`: máquina de estados imutável STOPPED → STARTING → RUNNING → STOPPING → STOPPED; transições de falha para FAILED; reset explícito antes de nova partida; rejeição de start duplicado e sinais fora de ordem.
- `tests/test_incremental_supervisor_lifecycle.py`: testes de partida/parada, duplicidade, falha, stop durante inicialização e stop redundante.

## Limites e próximos gates

Essa implementação **não** cria processo, timer, scheduler, lock interprocesso, banco SQLite ou job. Não modifica o índice RAG e mantém `safe_to_publish=false`. A exclusão mútua é somente lógica dentro de um snapshot, não garante proteção entre processos Windows. Antes de habilitar execução real, devem existir trava interprocesso verificável, tratamento de término abrupto, heartbeat, fencing token e testes sintéticos com dois processos independentes.

Publicação de geração pública continua separada e não autorizada por esta etapa.
