# RAG-DEL-01.04-DQ-E-D-3C-B — SQLite privada pinada no entrypoint real (DEV)

## Implementacao
O modulo knowledge_deletion_semantic_snapshot_lab.py valida uma PinnedSemanticRequestV1, recupera a SQLite pelo ID da geracao **a partir do scratch TEMP previamente aprovado**, nao do usuario, abre a SQLite por URI mode=ro com PRAGMA query_only e conta exclusivamente registros do namespace private solicitado em rag_documents. Revalida catalogo, manifest e hash SQLite apos a leitura. Nao executa modelos, Qdrant, busca semantica ou altera SQL.

isolated_project_worker.py recebeu o modo opt-in --pinned-scratch-snapshot, estritamente laboratorio. A entrada legada segue sem mudanca. A interface operacional MCP e os indices reais nao tem acesso a esse modo pela rota de busca.

## Testes
7 testes novos PASS:
- SQLite com dois documentos privados e um documento de namespace alheio retorna apenas 2.
- Provas de nonce, geracao, projeto e hash da requisicao.
- Nenhuma chamada ao resolver operacional ou motor semantico.
- Alteracao de bytes SQLite com mesmo numero de linhas e rejeitada.
- Manifesto adulterado, projeto alheio, geracao errada e raiz fora TEMP rejeitados.
- Arquivos catalogo/SQLite/manifest permanecem inalterados apos leitura.

RAG-DEL 400 testes (396 PASS, 4 SKIP), RAG-AUTO non-MCP 241 (236 PASS, 5 SKIP), total 641 (632 PASS, 9 SKIP), zero falhas.

## Nao homologado
A leitura conta registros em SQLite sintetica, NAO faz embeddings nem inferencia, nem prova liveness do parent sozinha. A integracao de inferencia real pinada e atestacao do MCP/GUI instalado permanecem PENDENTES. Nao houve atualizacao Stable, fila, catalogo real, instalador ou GitHub.

Proxima etapa DQ-E-D-3C-C: endurecer o contrato contra journal pendente, links/junctions de geracao e falhas do child durante a sessao pai; so depois avaliar stub-model do caminho real com workspace aprovado.