# RAG-017 — Investigação corretiva do gate BLOCKED (antes de J)

## Motivação e critério
O usuário solicitou resolver o gate de qualidade antes de seguir ao RAG-017-J. **Não mudar os thresholds**: Recall@5 >= 0.80, Recall@10 >= 0.90, MRR >= 0.60. O gate segue BLOCKED até cumprir os três em avaliação válida.

## Experimento controlado com corpus fixo
Script: `benchmarks/run_rag017_quality_ablation.py`. Resultado: `benchmarks/rag017_quality_ablation.json`.

- Usa **o índice persistente único existente**, com as mesmas 100 queries congeladas e ground truth.
- Testa depths 10, 20, 40, ranking RRF+dedup e a política offline de diversidade com uma fonte distinta por caminho.
- Não altera o índice persistente, modelos ou implementação de produção.

| Profundidade | Variante | Recall@5 | Recall@10 | MRR |
|---|---|---:|---:|---:|
| 10 | Base | 0.76 | 0.83 | 0.50342 |
| 10 | Fontes diversas | 0.81 | 0.83 | 0.52402 |
| 20 | Base | 0.69 | 0.84 | 0.49288 |
| 20 | Fontes diversas | 0.81 | 0.88 | 0.53255 |
| 40 | Base | 0.64 | 0.75 | 0.45073 |
| 40 | Fontes diversas | 0.77 | 0.89 | 0.50249 |

O resultado não chega ao conjunto das metas. A diversidade de caminhos melhora a cobertura nos primeiros resultados, mas o MRR continua insuficiente. Aumentar depth indiscriminadamente pode reduzir qualidade da ordenação.

## Conclusão
Não implantar a política de diversidade como correção comprovada do gate: este é um estudo exploratório usando o mesmo dataset para investigar e comparar variantes (risco de overfitting). Exigir validação adicional sem regras por ID, comparações robustas e regressão de latência, RAM, VRAM e isolamento entre projetos. Múltiplos chunks do mesmo arquivo podem ser relevantes; um item por fonte deve ser configurável e testado sem prejudicar recuperação por trecho.

Também há diferença entre o corpus atual persistente (210 documentos) e o replay RAG-017-F (205), não comparar diferenças percentuais entre eles como A/B controlado.

**Resultado do trabalho corretivo: diagnóstico melhorado, gate ainda BLOCKED.** RAG-017-J não deve certificar go-live.
