# RAG V1.03-D — Patch de validação da fila

Data: 2026-10-21

O diagnóstico do futuro agendamento agora consulta a fila pela função read-only existente inspect_job_queue, exigindo o caminho canônico jobs/incremental_jobs.sqlite3, schema conhecido e consulta SQLite válida. Banco ausente, malformado ou inacessível produz bloqueio. Nenhum banco é criado e o worker/scheduler não é iniciado.

A suíte sintética cobre default OFF, banco inválido, fonte fora do escopo e estrutura SQLite válida com zero ativação.
