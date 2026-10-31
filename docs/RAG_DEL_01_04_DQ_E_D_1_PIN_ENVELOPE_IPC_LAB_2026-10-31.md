# RAG-DEL-01.04-DQ-E-D-1 — Envelope pinado IPC sintetico (DEV)

## Implementado em laboratorio
- PrivateReadPinEnvelopeV1 imutavel (dataclass frozen e slots) com schema_version, project_id, generation_id, source_revision, catalog_sha256, sqlite_sha256, manifest_sha256 e nonce aleatorio.
- envelope_from_private_lab_pin: gera envelope apenas dentro de uma sessao privada semantica temporaria e ativa; usa hashes do catalogo/SQLite/manifesto.
- verify_private_pin_envelope_lab: valida os campos estritos, rejeita caminhos em envelope, revisao trocada, namespace publico, artefatos alterados e roots fora de TemporaryDirectory. Usa SQLite apenas mode=ro e fecha handle explicitamente.
- knowledge_deletion_pin_worker_lab: subprocesso real de teste que recebe somente JSON e raiz TEMP controlada, valida a mesma geracao e devolve estado estruturado sem iniciar inferencia/Qdrant.
- Modo --hold-for-ack do worker LAB permite verificar outro processo tentando cutover durante a sessao de leitura ativa.

## Testes
10 testes DQ-E-D-1 PASS, inclusive Win32 reader ativo bloqueando writer, handshake com subprocesso, adulteracao de manifest, mudanca de geracao, namespace, schema, nonce e falha fora de sessao/raiz temporaria.
RAG-DEL: 363 executados, 359 PASS + 4 SKIP, zero falhas.
RAG-AUTO (sem pacote MCP): 241 executados, 236 PASS + 5 SKIP, zero falhas.
Total 604 testes, 595 PASS + 9 SKIP, zero falhas.

## Limite de seguranca
O worker valida identidade e hashes mas NAO consegue provar por si que o processo pai permanece vivo nem que os locks estao retidos. A retencao foi provada em testes multiprocessos com a sessao externa de laboratorio e writer lock concorrente. Nenhum token de autorizacao operacional e emitido, resultados possuem parent_locks_attested_by_worker=False, operational_use_allowed=False e activation_authorized=False.

Este codigo nao substitui isolated_project_worker.py, nao cria interface MCP operacional, nao altera GUI/Stable/indices reais, nao inicia modelos e nao habilita exclusao real.

Proxima fase DQ-E-D-2: separar wrapper legado que adquire lock semantico e executor que exige lock JA retido. Testar compatibilidade, excecoes e timeout no DEV antes de alterar qualquer processo instalado.