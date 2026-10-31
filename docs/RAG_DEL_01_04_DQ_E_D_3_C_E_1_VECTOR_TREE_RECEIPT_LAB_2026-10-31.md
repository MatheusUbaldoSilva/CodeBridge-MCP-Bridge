# RAG-DEL-01.04-DQ-E-D-3C-E-1 — Recibo deterministico da arvore Qdrant TEMP (DEV)

## Entrega
knowledge_deletion_vector_tree_receipt_lab.py implementa VectorTreeReceiptLab congelado e VectorFileReceiptLab com schema, project_id, generation_id, hash do catalogo, nonce, caminhos relativos, tamanhos, SHA256 e diretorios, mais tree_sha256 canonico. Rejeita redirecionamentos por symlink/junction/reparse points, arquivos especiais, acesso fora do TemporaryDirectory, limite maior que 256 arquivos ou 16 MiB. Hash dos arquivos verifica metadados antes/depois de cada leitura. O recibo exige envelope pinado de catalogo/SQLite/manifesto e revalida antes e depois da leitura.

knowledge_deletion_semantic_injected_lab.py calcula o recibo antes de chamar apenas o stub sintetico e o verifica apos ele retornar, enquanto os locks do pai continuam detidos. Nao cria credencial de autorizacao.

## Provas
Adicionados 7 testes ao conjunto de stub: ordem deterministica de files e diretorios, tamper de vetor com tamanho inalterado, inclusao/exclusao de arquivos, inclusao de diretorio vazio, nonce divergente, limite 16 MiB e tentativa symlink. Este ultimo foi SKIP por WinError 1314 (falta de privilegio Windows). Os testes existentes de locks e namespace seguem PASS.

Regressoes: RAG-DEL 417 executados (411 PASS, 6 SKIP), RAG-AUTO sem MCP 241 executados (236 PASS, 5 SKIP). Total 658 executados, 647 PASS, 11 SKIP, zero falhas.

## Restricoes
O recibo e apenas comprovacao de conteudo no laboratorio, nao um snapshot transacional de Qdrant, nem prova de liveness do pai/filho ou do worker instalado. Nao impede alteracao adversaria entre verificacoes sem uma sessao lock-aware operacional e nao autentica processos. Qdrant real nao foi lido; uso de modelo semantico real, Stable, fila operacional, indices publicos, exclusao e Github permanecem bloqueados.

Proximo DQ-E-D-3C-E-2: protocolo de vida pai-filho, cancelamento, crash e writer contention Win32 estritamente TEMP, com timeouts e recuperacao fail-closed.