# RAG-017 — Carga warm e RAM agregada Code-only

Benchmarks executados na branch experimental `rag-017-optimized-inference-after-candidate` com a candidata dual protegida em `rag-017-candidate-cross-route-quality-20261009`. Sem ativação no aplicativo instalado.

Carga: uma consulta cold de 3949,371 ms seguida de 60 consultas warm em batches com 3 threads, `QueryRoute.CODE`, `experimental_cross_route=True`, modelo Jina Code residente e Qdrant reutilizado. **Warm p95 amostral 272,665 ms**, máxima 308,616 ms, mediana 172,933 ms. Algumas consultas retornaram menos que 10 resultados (`all_count_10=false`), o que requer investigação de cobertura. Prompts derivados de 8 templates repetidos, não representam carga real independente.

RAM: 40 embeddings concorrentes com 3 threads; 273 amostras obtidas com API nativa Windows `GetProcessMemoryInfo`; máximo da soma dos working sets do processo Python pai e subprocesso Jina Code **2048,35 MiB**; vetores de 1536 dimensões em todos os casos. Não equivale ao pico completo do aplicativo/serviço instalado, e picos transitórios fora das amostras não foram provados. VRAM em experimento anterior teve uso máximo amostrado de 3204 MiB da GPU.

Os limites originais não foram modificados. Produção **BLOCKED** até avaliação cega independente, RAM/VRAM end-to-end com workload real, estabilidade do serviço gerenciado, segurança de filtros e p95 representativo. Arquivo `benchmarks/rag017_code_only_extended_smoke.json` já modificado antes permanece intocado.
