# RAG-017 — Avaliação real do BGE cross-encoder (intervenção isolada)

## Configuração verificada
- Origem do checkpoint: `BAAI/bge-reranker-v2-m3` (Apache-2.0). Arquivo GGUF Q4_K_M convertido por `bortunac/bge-reranker-v2-m3-Q4_K_M-GGUF`; checkpoint convertido por terceiro, **não equivalente a auditoria de autenticidade do fornecedor original**.
- Modelo local: `%LOCALAPPDATA%/CodeBridge/models/bge-reranker-v2-m3-Q4_K_M-isolated/bge-reranker-v2-m3-q4_k_m.gguf`; 438374880 bytes; SHA256 `EFEE6434F8B888B414A3765D8A531E9513A9FEE64A0CF51126620D11E7BC71B6`.
- `llama.cpp`: build 10819, commit 6a1a922d2. Servidor exclusivamente em `127.0.0.1:8081`, modelo Q4, `--reranking --pooling rank -c 4096 -b 4096 -ub 4096 -ngl 99`.
- RTX 3050 6 GB: leitura pontual de uso total de GPU com reranker carregado 527 MiB/6144 MiB (baseline livre próximo de 99 MiB); **não é pico de VRAM de todo benchmark**.
- `/reranking` devolveu scores reais distintos para documento pertinente e irrelevante (6,342 e -11,002). O endpoint trabalha com logits não normalizados; não são probabilidades.
- O adaptador truncou conteúdo a 1400 caracteres por candidato uniformemente. A configuração inicial de batch 512 falhou com 1052 tokens; batch 2048 falhou com 2089 tokens; a configuração acima concluiu as 100 queries.

## Resultados das 100 queries congeladas

Artefato: `benchmarks/rag017_cross_encoder_real_evaluation.json`, produzido pelo runner `benchmarks/evaluate_rag017_cross_encoder.py`.

| Métrica | Baseline documento | Após BGE rerank | Meta |
|---|---:|---:|---:|
| Recall@5 | 0,82 | **0,66** | >= 0,80 |
| Recall@10 | 0,91 | **0,81** | >= 0,90 |
| MRR | 0,596595 | **0,431397** | >= 0,60 |
| Latência p95 adicional | — | **474,77 ms** | considerar orçamento warm completo |

**Decisão: não ativar este reranker.** Houve regressão significativa nos três critérios, inclusive em relação ao melhor baseline por documento. O gate permanece **BLOCKED**.

## Limitações diagnósticas
- Não houve validação com consultas independentes; o conjunto é usado para explorar estratégias.
- O segundo estágio avaliou apenas um `SearchResult.content` representativo de cada documento, não todos seus chunks; possível perda de evidência. Essa hipótese ainda não foi comprovada.
- A janela de entrada e o truncamento podem afetar fontes de código extensas; a política de conteúdo precisa ser testada em corpus independente.
- O benchmark mediu latência adicional do reranker, mas não o p95 cold-to-warm completo nem pico simultâneo de RAM/VRAM do pipeline total.
- Índice SQLite/Qdrant/manifest não sofreu alterações; CodeBridge MCP instalado não foi reiniciado nem modificado.

## Próximo experimento recomendado
Avaliar estratégia semântica *multi-passage* com representatividade da fonte, sem ajustes especiais para IDs do dataset, medir Recall@5, Recall@10, MRR em conjunto independente e latências totais. O modelo BGE permanece isolado, **sem ativação automática**. RAG-017-J permanece pendente.

## Política de fechamento
Regressão completa, diff check, commit, push e auditoria pós-commit; nenhuma declaração de produção READY apenas pelo carregamento do modelo.
