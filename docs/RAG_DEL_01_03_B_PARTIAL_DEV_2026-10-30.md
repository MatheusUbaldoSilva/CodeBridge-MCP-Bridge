# RAG-DEL-01.03-B — Planejamento e transferência vetorial limitada (DEV)
Data: 2026-10-30
Estado: IMPLEMENTAÇÃO PARCIAL; **não homologado para dados reais**.

- `rag/runtime/knowledge_deletion_vectors.py`: revalida a seleção via prévia privada, compara a geração e o manifesto ativo, exclui os caminhos selecionados do planejamento, gera recibos determinísticos de chunks sobreviventes e divide por coleção/modelo em lotes <=256.
- `rag/runtime/knowledge_deletion_vector_copy.py`: recebe clientes Qdrant fornecidos pelo chamador; exige confirmação, fonte verificada e estágio isolado. Reutiliza validadores de ID, namespace, SHA, dimensão e payload do RAG-AUTO-05, grava um lote e faz readback de todos os pontos.
- Teste de integra??o com Qdrant Local tempor?rio: um vetor CODE de dimens?o 1536 foi transferido e relido, sem GPU, sem alterar ?ndice real.
- Testes isolados: `test_rag_del_01_03_b_vectors.py` (5) e `test_rag_del_01_03_b_copy.py` (6).

## Bloqueios antes de usar dados reais
1. Garantir identidade dos clientes Qdrant por caminhos canônicos isolados, não apenas flags declaradas pelo chamador.
2. Integrar checkpoint durável idempotente e recuperação de lotes com verificação pós-restart.
3. Testar Qdrant temporário com vetores válidos e falhas injetadas, incluindo dimensões e isolamento entre projetos.
4. Conferir SQLite/manifesto da geração candidata e recibos completos no RAG-DEL-01.03-C.
5. Não abrir Qdrant ativo para escrita, não ativar catálogo nem alterar Stable/público.

O código desta subfase é uma biblioteca para testes, não está ligado à GUI e não contém fluxo operacional de exclusão.
