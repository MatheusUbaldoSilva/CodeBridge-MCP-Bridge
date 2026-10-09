# RAG-017 — Perfil de latência por etapa

Instrumentação temporária do executor opt-in real, com Jina Text/Code residentes e SQLite/Qdrant persistentes (sem alteração do índice).

| Etapa | Primeira consulta (ms) | Terceira (ms) |
|---|---:|---:|
| Jina Text | 4446 | 1259 |
| Jina Code | 5688 | 1794 |
| Abrir Qdrant | 3540 | 1652 |
| SQLite lexical | 48 | 27 |
| Vetores Text+Code | 150 | 124 |
| Rerank documental | 0.2 | 0.3 |
| Total | 13894 | 4876 |

Experimento adicional de reutilização de um único cliente Qdrant no mesmo processo Python: 7502, 3445 e 3521 ms em três consultas. A reutilização diminui o custo de abertura, mas o tempo warm segue muito acima do teto de 1000 ms. Essa implementação com objeto compartilhado foi apenas protótipo de diagnóstico, não possui validação de concorrência ou ciclo de vida para produção.

Arquivos: benchmarks/rag017_cross_route_stage_profile.json e benchmarks/rag017_qdrant_reuse_smoke.json. Amostras pequenas; sem medição válida de warm p95, RAM/VRAM pico e holdout independente. Gate BLOCKED. Nenhum threshold modificado e nenhum serviço ativado.

Próximo foco: geração dos embeddings com Jina Text/Code (aproximadamente 3 segundos somados até na terceira consulta), desenho de serviço dedicado e medição do custo real do subprocesso/modelo em modo residente. O índice e os contratos do MCP permanecem inalterados.
