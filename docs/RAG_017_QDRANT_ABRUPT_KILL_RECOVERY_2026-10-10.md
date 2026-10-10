RAG-017 — Recuperação básica após kill de processo (2026-10-10)

Teste Qdrant Local feito no venv temporário Python 3.13.15. `benchmarks/rag017_qdrant_crash_recovery.py` criou índice descartável em `%TEMP%\CodeBridge-RAG017-CrashProbe-20261010`; coleção `crash_probe`, um registro ID 71, payload `after-abrupt-kill`. Saída antes da interrupção: `ready_to_kill=true`, `count=1`.

O PID 11640 foi confirmado via Win32_Process como processo do canário antes de `Stop-Process -Force`. Reabertura por novo processo recuperou contagem 1 e payload correto, com `recovered=true`, `RECOVERY_EXIT=0`. Listener CodeBridge MCP original manteve PID 12776 na porta 8765.

Limite: o kill ocorreu APÓS o upsert com wait=True e contagem confirmada. Não simula crash DURANTE uma gravação nem prova resistência a corrupção, restauração de snapshots, multi-processo ou rollback do instalador. Produção RAG-017-J continua BLOCKED.
