RAG-LAB.04 — adendo de auditoria de aderencia ao handoff

A referencia normativa exige 04-B hashes completos, paths redirecionados e hardlinks, checkpoints e sidecars; 04-C restore clean room com auditoria em processo diferente; 04-D hashes omitidos, metadados adulterados, arquivo extra, writers concorrentes e mutacao entre leituras; 04-E rollback simulado com ponteiro inalterado.

Evidencias novas nesta sessao
04-B 993668d quatro testes de validacao do snapshot
04-C ddb0717 restauracoes com ponteiro preservado
04-D c544207 falha de copia e staging limpo
04-E e4f4b64 metadados falsificados e nomes/overwrite rejeitados
Complemento 5c8a63e rejeicao de hash omitido e arquivo extra

Testes preexistentes auditados por codigo
- tests/test_offline_fixture_snapshot.py possui teste de writer externo e mutacao durante copia
- tests/test_offline_store_tree_catalog.py cobre hardlink, symlink, arquivo criado durante hashing
- tests/test_offline_fixture_restore.py cobre sidecar, metadata alterada e copia interrompida

Lacunas normativas ainda a validar especificamente no contrato de 04
- Evidencia isolada da auditoria em outro processo para cada restore conforme requisito 04-C
- Matriz consolidada entre contratos 04-B/D e todos os tipos de checkpoints e sidecars reais
- Nenhum ensaio de manutencao real nem prova global de handles ou mmap

Ultima regressao backend 241 offline +83 generation +7 preflight +38 incremental =369 PASS
O estado correto e laboratorio ampliado mas fechamento normativo depende da matriz das lacunas
copy_authorized=false
all_handles_closed=false
production_quiescence_proven=false
production_backup=BLOCKED
