# RAG-017 — Auditoria observacional do runtime MCP (2026-10-10)

Máquina autorizada MatheusPC. Branch experimental `rag-017-optimized-inference-after-candidate`, HEAD inicial `16f3fa7`. Não houve alteração de processos, instalação, configuração ou registro de executores.

Evidências observadas via ferramentas Windows:
- Processo Python MCP PID 12776 (iniciado em 2026-10-08 às 21:26:22); listener TCP local `127.0.0.1:8765` atribuído ao mesmo PID.
- Processo tunnel-client PID 2988 (iniciado em 2026-10-08 às 21:26:24); listener local `127.0.0.1:8080`.
- GET `http://127.0.0.1:8080/readyz`: HTTP 200.
- GET convencional `http://127.0.0.1:8765/mcp`: HTTP 406; não foi enviada requisição MCP negociada, logo não representa diagnóstico conclusivo de falha.
- GET `http://127.0.0.1:8765/readyz`: HTTP 404; nenhuma rota /readyz nesse endpoint comprovada.
- Working set observado em uma leitura: Python MCP 21.577.728 bytes; tunnel-client 17.293.312 bytes. Não é pico nem consumo agregado de produção.

**Limitações:** Win32_Process não forneceu CommandLine/ExecutablePath no contexto de acesso atual. Sem instrumentar o processo MCP vivo ou obter estado autenticado via protocolo, não se comprovou configuração real carregada, executor RAG registrado, flags experimentais em runtime ou fallback. Testes do código de integração no commit anterior confirmam defaults desativados, mas isso não prova a configuração do processo instalado.

Gate de produção **BLOCKED**. Não se alterou a build dual tagueada `rag-017-candidate-cross-route-quality-20261009`, nem se ativou Code-only. Holdout independente permanece pendente.
