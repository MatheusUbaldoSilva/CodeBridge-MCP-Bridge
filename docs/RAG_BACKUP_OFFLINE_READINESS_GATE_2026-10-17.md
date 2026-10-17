# Central RAG   Gate de seguranca para backup offline (2026-10-17)

Estado: **LABORATORIO EM DESENVOLVIMENTO**. Nenhuma captura real autorizada.

## Evidencias verificadas nesta rodada

- Captura de fixture sintetica por processo separado da GUI/MCP.
- Restauracao em novo destino e auditoria independente com SHA-256 e
  verificacao semantica de SQLite, manifesto e Qdrant.
- Falha fechada para corrupcao dos tres stores, metadados alterados,
  links/junctions em ancestrais, hardlinks e sidecars SQLite.
- Escritores sinteticos ativos: bloqueio de handles nos tres stores.
- Encerramento do processo pai nao garante que um filho liberou SQLite.
- Supervisor PID: exige observar cada identidade ativa antes de duas
  ausencias consecutivas. Mesmo assim nao comprova quiescencia global.
- Teste mmap: fechamento de descritor inicial nao implica que o
  mapeamento de memoria tenha terminado.

## Evidencias que continuam faltando

1. Janela de manutencao, operador e destino de backup aprovados.
2. Bloqueio de novas consultas/indexacoes e drenagem das operacoes ativas.
3. Flush/fechamento coordenado de SQLite, manifesto e Qdrant.
4. Supervisor externo iniciado antes da parada e independente do MCP,
   com identificacao completa de GUI, adapter, MCP, indexadores e
   processos herdados, incluindo PID + creation time e executavel.
5. Comprovacao integral de handles/arquivos mapeados em memoria.
   O inventario Win32 atual tem entradas sem ExecutablePath e
   permanece BLOCKED, sem presumir seguranca.
6. Copia com janela de imutabilidade e hashes de origem/destino,
   restauracao em processo externo e rollback validado.
7. Auditoria Git/diff/commit, relatorio operacional e consentimento
   separado antes de qualquer tentativa com dados reais.

Os utilitarios sinteticos NUNCA retornam uma autorizacao de producao.
O indice ativo e ponteiro de geracao nao devem mudar neste marco.

## Controles de encerramento CodeBridge

Em NORMAL: desenvolver, auditar e testar com fixtures.
Em PREPARE_WRAP_UP: nao abrir novas frentes; terminar o que for seguro,
salvar checkpoint, conferir Git.
Em WRAP_UP_NOW: interromper novas chamadas de execucao e encerrar.

## Arquivos preexistentes preservados

- benchmarks/rag017_code_only_extended_smoke.json (modificado anteriormente)
- docs/RAG_017_J_VM_ROLLBACK_RUNBOOK_2026-10-10.md (fora do versionamento)

Nao adicionar esses arquivos acidentalmente ao commit do laboratorio.
