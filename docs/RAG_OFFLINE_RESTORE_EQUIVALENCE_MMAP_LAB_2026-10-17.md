# RAG   Equivalencia de restauracao e limite mmap (laboratorio)
Estado: LABORATORIO SOMENTE, NAO AUTORIZA BACKUP REAL.

A funcao `rag.runtime.offline_restore_equivalence.audit_restored_fixture`
compara hashes SHA-256 de todos os arquivos do snapshot e da restauracao,
alem de revalidar em cada copia a consistencia semantica entre SQLite,
manifesto e Qdrant via `validate_incremental_bundle`. O laboratorio
abrange dois projetos e rejeita alteracoes sintéticas em SQLite,
manifesto e arquivos Qdrant. Nao ativa geracao nem ponteiro de producao.

O teste `test_offline_mmap_limit` cria um processo filho que abre o
manifesto sintetico com `mmap.ACCESS_READ`, fecha o descritor inicial,
mas preserva o mapeamento ate terminar naturalmente. O probe de handles
pode ou nao classificar o caso como legivel; em nenhuma hipotese libera
captura. Esse ensaio NAO prova deteccao universal de mappings de
memoria ou consumidores desconhecidos.

Todos os resultados permanecem `production_authorized=false`,
`copy_authorized=false` e/ou `publication_authorized=false`.
Prova global de parada exigira supervisor externo e manutencao
explicitamente autorizada, sem encerrar o MCP pela propria conexao.
