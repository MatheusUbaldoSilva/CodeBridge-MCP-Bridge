# RAG-017-H — Índice persistente READY

## Resultado técnico confirmado
A indexação real do projeto CodeBridge foi construída com Jina Text e Jina Code, em staging isolado, validada e publicada no diretório `%LOCALAPPDATA%/CodeBridge/rag`. Uma nova execução do Python verificou o índice em disco, a integridade do SQLite e uma consulta semântica completa.

| Indicador | Valor |
|---|---:|
| Fontes elegíveis | 210 |
| Caminhos negados pelas políticas de ingestão | 2980 |
| Fontes não suportadas | 2 |
| Documentos publicados | 210 |
| Chunks publicados | 8761 |
| Vetores de texto (Qdrant) | 7627 |
| Vetores de código (Qdrant) | 1134 |
| Entradas no manifest | 210 |
| Estado reportado após reabertura | READY |

Fontes autorizadas nesta indexação inicial: `rag`, `author_mcp` e `docs` da cópia de trabalho CodeBridge. Arquivos sensíveis e diretórios excluídos não foram indexados.

## Mudanças
- `rag/runtime/production_publish.py`: valida o estágio, verifica integridade do SQLite, ausência de chunks órfãos e correspondência exata entre chunks e pontos vetoriais; somente então permite uma primeira publicação com SQLite, Qdrant e manifest. A publicação recusa sobrescrever um índice de produção preexistente. Uma falha reverte componentes que acabaram de ser publicados.
- O manifest recebe os caminhos, SHA256, tamanho e mtime das fontes, com revisão pinada dos modelos. O conteúdo das fontes é revalidado antes da publicação para detectar alterações entre staging e promoção.
- `rag/runtime/status.py`: estado READY passa a exigir os três componentes persistentes e projetos READY correspondentes, evitando falso positivo em publicação incompleta.
- `tests/test_rag_status_snapshot.py`: atualizados testes antigos em que manifest/SQLite isolados eram considerados suficientes.
- `tests/test_rag_017_h_publication.py`: testes de falha segura e recusa de sobrescrita.

## Testes reais
- `benchmarks/run_rag017h_persistence_smoke.py`: staging e publicação em diretório temporário, reabertura, recusa de sobrescrita e integridade do SQLite.
- `benchmarks/run_rag017h_real_build.py`: execução real com 210 fontes autorizadas, 8761 chunks e contagens vetoriais iguais às do SQLite.
- `benchmarks/verify_rag017h_production.py`: processo novo, status READY, verificação do manifest e teste semântico; cinco hits, primeiro caminho `rag/runtime/query_classifier.py`.
- Suite automatizada RAG completa; revisão Git, diff, commit, push e auditoria pós-commit exigidos.

## Restrições e gates
- **READY significa consistência técnica do snapshot inicial, não aprovação de qualidade e não indexação contínua.** RAG-017-I permanece BLOCKED: Recall@5 0,77 (meta 0,80), Recall@10 0,83 (meta 0,90) e MRR 0,532 (meta 0,60).
- O índice atual representa um snapshot das fontes no momento da construção. Commits ou alterações subsequentes devem acionar reindexação controlada antes de tratá-lo como atualizado.
- Não há atualização automática de fontes nem publicação incremental segura para índices já existentes: a primeira publicação recusa substituição para impedir perda de dados. As próximas fases deverão implementar versionamento/merge/rollback antes de permitir reindexação do mesmo projeto.
- O aplicativo instalado não foi substituído ou reiniciado. Os executores estão no checkout versionado e a busca real foi validada a partir do código-fonte. Implantação/ativação MCP do instalado permanece tarefa separada.
- Não houve modificação dos pesos dos modelos ou dos limiares para produzir este READY.
