# RAG V1.03-D — Gate de schema completo de fila

Data: 2026-10-21. Implementação sintética, sem agendamento ativo.

Após inspect_job_queue, o gate consulta SQLite em modo read-only e exige user_version=2 e colunas obrigatórias tanto de jobs (proveniência, lease, vencimentos) quanto de staging_receipts (manifesto e contagens). Uma fila apenas parcialmente compatível é bloqueada. Mesmo a fila sintética totalmente válida não concede autorização nem inicia worker, scheduler ou publicação.

Testes: cinco cenários locais, incluindo esquema incompleto recusado, banco sintético compatível, negação default e fonte fora do escopo. Nenhum armazenamento público é escrito.
