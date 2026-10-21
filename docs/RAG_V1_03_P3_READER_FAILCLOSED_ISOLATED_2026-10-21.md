# RAG V1.03 P3 ? Leitor de producao testado com fixture isolada

Data: 2026-10-21. Base: commit 2f1361f. Nenhuma escrita no RAG publicado.

Quatro testes novos em tests/test_p3_production_read_fail_closed_isolated.py avaliam as funcoes reais de leitura e rollback versionado, mas com raiz de testes temporaria e locks substituidos apenas no contexto dos testes:

1. Sem ponteiro, leitura do legado; com ponteiro valido, leitura da candidata.
2. Journal PREPARED impede consulta tanto antes quanto depois da escrita de pointer.
3. Manifesto incompleto e ponteiro JSON corrompido recusados (fail-closed).
4. Recuperacao de jornal pendente para legacy preserva os dois bancos e a candidata, remove jornal e recoloca leitura no legado.

320 testes incrementais, 64 do instalador e 4 destes testes de P3 passaram. Git auditado antes de commitar.

Estes testes nao comprovam lock multiprocesso nem troca de ponteiro no MCP instalado; nenhuma ativacao/publicacao e autorizada. P3 segue bloqueada ate prova de processo real de escritor/leitor e aprovacao especifica.
