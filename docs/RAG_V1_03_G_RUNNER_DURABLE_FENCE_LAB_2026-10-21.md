# RAG V1.03-G ? Runner isolado com geracao duravel opcional

Data: 2026-10-21. Base: `e3bcf31`.

`SupervisorLabRunner` aceita `durable_store` opcional sem alterar o fluxo legado. Quando informado, adquire primeiro o lock real do Windows e emite a nova geracao SQLite antes de executar a maquina de estados e callback inofensivo. O resultado expoe `durable_generation` sem confundir com o contador local do `SupervisorSnapshot`.

Falha de emissao, base fora do escopo ou impossibilidade de observar a geracao retornam `DURABLE_FENCE_UNAVAILABLE`, sem iniciar callback. Ausencia de callback permanece bloqueada, sem criar banco.

Escopo estrito: laboratorio isolado em diretorio temporario, callback inofensivo e nenhum worker, scheduler ou publicacao. Este mecanismo nao comprova integridade de processo nao cooperativo nem quiescencia de dados reais e nao constitui autorizacao de producao.
