# RAG V1.03-D — Lock interprocesso do supervisor (laboratório)

Data: 2026-10-21. Base: commits da máquina de estados `da0ee3f` e proteção de callbacks `cc50abb`.

## Implementação

- `rag/runtime/incremental_supervisor_lock.py`: lock não bloqueante de um byte via `msvcrt.locking` no Windows, restrito a diretório existente, sem seguir symlink direto nem criar árvore de diretórios.
- `tests/test_incremental_supervisor_lock.py`: exclusão mútua na mesma instância e entre subprocessos independentes; liberação após saída normal e término abrupto; rejeição de caminhos inválidos.

## Limites

Esse primitivo não inicia worker, serviço, scheduler, watchdog ou indexação. Ele não substitui o lease SQLite dos jobs, a verificação de identidade do processo e o fencing token durável; estes serão integrados antes de qualquer execução supervisionada de verdade. Os testes usam diretórios temporários e não alteram o RAG público.
