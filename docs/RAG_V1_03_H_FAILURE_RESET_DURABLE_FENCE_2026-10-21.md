# RAG V1.03-H ? Falha e reset com fencing duravel

Data: 2026-10-21. Base: `266ce73`.

Dois testes adicionais do supervisor de laboratorio validam: falha deliberada de callback coloca o runner em FAILED, impede novo ciclo ate reset explicito e, apos reset, emite token duravel maior invalidando o anterior; ausencia de callback bloqueia sem criar lock nem base SQLite.

Sem mudanca de execucao de worker, scheduler, publicacao de geracao ou indice real. Testes estritamente sinteticos.
