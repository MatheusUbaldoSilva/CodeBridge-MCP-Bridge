# RAG-017 — Experimento real de reranking multi-passage

## Objetivo
Testar hipótese de que o cross-encoder BGE perde evidência por examinar somente um trecho de cada arquivo. Não alterar o gate congelado, não modificar índice e não habilitar ranking experimental em produção.

## Implementação
- `rag/ranking/multi_passage_reranker.py`: recebe somente candidatos já filtrados pelas buscas lexical/vetorial, agrupa por projeto/documento/caminho/branch e seleciona até 3 chunks distintos por fonte e 20 fontes no total (máximo 60 trechos).
- Prioriza os chunks por contribuição geral ao ranking de recuperação; chama `cross_encoder_rerank` local e reúne o melhor score de cada documento mais apoio fraco de um segundo trecho.
- Mantém um resultado por arquivo, limites de lote, deduplicação por chunk e erro para misturar projetos. A versão **não foi integrada ao MCP instalado**.
- `benchmarks/evaluate_rag017_multi_passage.py` utiliza os mesmos modelos Jina para obter candidatos, e o BGE Reranker v2 M3 GGUF Q4_K_M no endpoint local.
- `benchmarks/rag017_multi_passage_evaluation.json` registra os resultados reais.

## Evidência: 100 consultas conhecidas
| Medida | Reranker por documento (sem BGE) | BGE single-passage | BGE multi-passage | Meta |
|---|---:|---:|---:|---:|
| Recall@5 | 0.82 | 0.66 | **0.80** | 0.80 |
| Recall@10 | 0.91 | 0.81 | **0.90** | 0.90 |
| MRR | 0.596595 | 0.431397 | **0.549897** | 0.60 |
| P95 somente etapa BGE | — | 474.77 ms | **757.05 ms** | incluir no warm p95 total <=1000 ms |

**Resultado: regressão relativamente ao melhor ranking por documento, melhora relativamente ao BGE single-passage.** Não se pode declarar o gate PASS: MRR não alcançou 0.60, dataset não é holdout independente, e não há medição de latência/memória integrada completa.

## Restrições e próximos passos
- Variantes adicionais (máximo por passagem, média, top dois, reranking de snippets) são hipóteses a testar em validação independente, não ajustes guiados pelas mesmas 100 perguntas.
- A política de 1400 caracteres por trecho pode limitar a informação de arquivos extensos, devendo ser medida com textos independentes.
- Modelo usado é versão GGUF de terceiro; hash e origem documentados em `docs/RAG_017_BGE_CROSS_ENCODER_REAL_EVALUATION.md`.
- O índice persistente foi consultado somente em modo leitura, sem reindexação ou alteração.
- RAG-017-J permanece aguardando solução efetiva dos thresholds.
