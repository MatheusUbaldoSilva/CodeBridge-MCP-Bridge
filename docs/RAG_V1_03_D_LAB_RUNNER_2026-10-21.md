# RAG V1.03-D — Runner de laboratório isolado

Data: 2026-10-21. Base `7155bcd`.

- `rag/runtime/incremental_supervisor_lab_runner.py`: integra máquina de estados e lock Windows para executar somente um callback sintético por chamada explícita; falha exige reset. Sem loop, scheduler, fila ou serviço.
- `tests/test_incremental_supervisor_lab_runner.py`: ciclo seguro, ausência de callback, falha com reset e exclusão mútua contra subprocesso real independente.

**Não é implantação de produção.** Lock de arquivo é transitório e a geração do estado é local à instância; falta fencing durável e validação de identidade/reinício antes da operação contínua. O índice público permanece protegido e nenhuma publicação é autorizada.
