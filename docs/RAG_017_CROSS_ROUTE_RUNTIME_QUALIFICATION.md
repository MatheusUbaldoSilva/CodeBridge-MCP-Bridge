# RAG-017 — Cross-route: qualificação inicial do executor opt-in

## Integração
`rag/runtime/production_search.py` aceita `experimental_cross_route=False` por padrão. Em opt-in explícito, consulta lexical e vetorial TEXT e CODE sobre o mesmo `SearchQuery`, preserva filtros de projeto, branch, tipos de fonte e path, usa profundidade de candidatos 32, agrega por documento com RRF k=10. O fluxo convencional permanece como antes, sem novo registro do MCP nem ativação no instalador.

## Qualidade reproduzida no benchmark exploratório
Recall@5 0.89, Recall@10 0.95, MRR 0.704806 em 100 perguntas RAG-014, **já utilizadas na seleção de variantes**. Resultados não constituem holdout independente; thresholds congelados 0.80, 0.90 e 0.60.

## Medição real de execução opt-in
`benchmarks/run_rag017_cross_route_runtime_smoke.py` executou duas consultas TEXT com os dois modelos Jina e índice persistente real; fonte `benchmarks/rag017_cross_route_runtime_smoke.json`.

- Busca 1: **8132.45 ms**.
- Busca 2: **8141.65 ms**.
- RSS Python após as consultas: 324136960 e 349855744 bytes, não equivale ao pico total de RAM incluindo subprocessos dos modelos.
- A meta warm p95 congelada é **1000 ms**. Duas amostras não permitem estimar rigorosamente p95, mas mostram um problema severo de latência causado pelo ciclo carga/consulta/descarga de Jina Text e Code a cada consulta.
- Cold, warm p95 representativo e VRAM peak integrada ainda não foram medidos. A compatibilidade com o limiar de VRAM não deve ser inferida do RSS Python.

## Decisão
**Produção BLOCKED.** Não registrar a variante como executor principal, nem alterar o aplicativo instalado, nem o índice persistente. Precisa-se de serviço residente de embeddings Text/Code com memória e exclusão mútua controladas, validação semântica independente, benchmarks cold/warm/RAM/VRAM, e testes end-to-end de isolamento e segurança. O orçamento <= 1000 ms warm p95 deve incluir a busca inteira.

## Próximo passo
Reestruturar lifecycle de modelos para reduzir carga/descarrega por consulta; testar pool, GPU/CPU ou modelo único multiuso conforme limites. Só depois reexecutar métricas imutáveis e considerar aprovação.
