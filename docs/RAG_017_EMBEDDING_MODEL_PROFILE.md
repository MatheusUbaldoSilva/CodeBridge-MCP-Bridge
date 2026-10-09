# RAG-017 — Perfil individual de embeddings Jina

Instrumentação experimental de 5 perguntas sequenciais com os modelos Jina Text e Code residentes; resultados completos em `benchmarks/rag017_embedding_model_profile.json`.

| Amostra | Text (ms) | Code (ms) | GPU usada (MiB) |
|---:|---:|---:|---:|
| 1 | 2052 | 4476 | 5903 |
| 2 | 1008 | 2003 | 5913 |
| 3 | 1811 | 1905 | 5913 |
| 4 | 1638 | 1614 | 5903 |
| 5 | 1500 | 1482 | 5913 |

Text: vetor 1024 dimensões; Code: 1536 dimensões. GPU RTX 3050 6144 MiB, amostras pós-inferência. Após fechar os dois processos: 88 MiB, nenhum llama-server.exe em execução. O RSS agregado de subprocessos e picos transitórios de VRAM não foram medidos.

Conclusão: a combinação de embeddings consome ~3 segundos até aquecida, excedendo o teto warm p95 de 1.000ms antes mesmo das buscas. Co-residência deixa cerca de 230 MiB de margem livre no dispositivo, risco operacional. O gate continua BLOCKED. Não ativar o pool, não enfraquecer thresholds, não modificar produção.

Próxima investigação: perfil de latência/qualidade de roteamento semântico com geração de apenas um dos vetores e recuperação cruzada baseada em índices compatíveis, ou avaliar uma arquitetura de embeddings mais eficiente; qualquer proposta precisa passar em holdout independente e limites de RAM/VRAM e latência.
