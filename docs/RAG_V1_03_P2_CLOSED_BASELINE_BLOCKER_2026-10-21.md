# RAG V1.03 P2 ? Baseline fechado bloqueado por quiescencia nao comprovada

Data: 2026-10-21. Base Git `2e71a3688f826746baeb0791a4dc637c58283c3a`.

A P1 autorizada ja gerou e validou um delta de uma fonte em `C:\Users\Matheus\AppData\Local\Temp\codebridge-rag-p1-isolated\build-f836f40ee74b42ce9ba1b6334efb96be`, com 1 documento, 2 chunks e 2 vetores. Esse bundle nao contem o legacy completo.

Nesta P2, `inspect_backup_prerequisites` foi executado somente para leitura sobre as tres fontes instaladas e retornou `state=BLOCKED`, `issues=[APPLICATION_QUIESCENCE_NOT_CONFIRMED]`, 210 documentos, 8761 chunks, 210 entradas de manifesto, `copy_authorized=false`, `publication_authorized=false`. A ausencia de sidecars SQLite verificada em um instante nao prova ausencia de escritores ou transacoes posteriores.

A API Qdrant Local de snapshot nativo nao disponibiliza as operacoes necessarias no backend instalado. `test_production_backup_preflight.py`: 7 PASS e `test_offline_lab04_qdrant_native_snapshot_limit.py`: 1 PASS. Assim, nao copiar a pasta Qdrant publica aberta nem efetuar merge usando uma copia nao consistente.

## Decisao de seguranca

Manter `GO_LIVE_BLOCKED` e o MCP, GUI, worker e scheduler no estado anterior. Nenhuma copia ou publicacao de SQLite/Qdrant publico foi executada. O indice atual com 210 documentos permanece em uso e nao deve ser alterado.

Proximo passo P2-A: desenhar janela de manutencao coordenada, provar quiescencia real de todos os consumidores/escritores, obter aprovacao do operador para interromper apenas os processos pertinentes e capturar snapshot fechado validando hashes antes e depois. Se nao houver aprovacao ou prova de quiescencia, nao copiar baseline e continuar somente com ensaios sinteticos em diretorios temporarios. A autorizacao anterior contemplou apenas indexacao isolada de `rag/runtime/incremental_scheduler_gate.py`, nao indisponibilidade do RAG publico.
