# RAG-DEL-01.04-DQ-E-D-3C-E — Liveness parent/child e pin de vetores (PLANEJADO)

Status: NAO IMPLEMENTADO. Base: dev-local c0361ea. Nenhum indício de que o worker instalado recebeu suporte ao novo protocolo.

## O que esta efetivamente provado
- DQ-E-D-3C-A: codigo do entrypoint real suporta apenas validacao de envelope pinado em TMP, sem modelo.
- DQ-E-D-3C-B: mesmo entrypoint abre SQLite pinada em mode=ro e limita count ao namespace autorizado, sem Qdrant.
- DQ-E-D-3C-C: journal pendente incluindo ROLLED_BACK e redirecionamento de generations fail-closed.
- DQ-E-D-3C-D: injected callback sintetico recebe SearchStoragePaths pinado; rejeita stale/foreign results e tamper de manifesto; nao e worker semantico real.

## Lacunas
1. O envelope V1 nao inclui hash/manifesto verificavel da arvore de vetores Qdrant. Presenca de pasta qdrant nao comprova seu conteudo nem sua geracao.
2. O child pode validar arquivos mas nao atesta sozinho que o pai continua com generation(shared) e semantic(exclusive). Um processo pai morto ou desconectado precisa invalidar o contrato ou interromper o worker de modo fail-closed.
3. Request digest SHA256 e nonce correlacionam mensagens mas nao fazem autenticacao nem prova de liveness.
4. Worker real em modo legado ainda resolve projetos pelo catalogo. Seu modo pinned de inferencia com Qdrant nao foi implementado.
5. GUI Stable/candidato ainda nao tem leitor publico pinado e MCP conectado nao expos generation_probe na ultima auditoria; fila operacional tem READY_FOR_REVIEW pendente; journals sao bloqueadores ate reconciliacao auditada.

## DQ-E-D-3C-E-1 — Fingerprint dos vetores
- Definir e versionar receipt hash/manifesto da arvore Qdrant da geracao aprovada (arquivos ordenados, paths canonicos, tipos, tamanho, SHA256 e protecao de links).
- Validar antes e apos inferencia sem manter lock na ordem inversa e sem violar throughput/heartbeat da fila.
- Nao deixar o cliente escolher caminhos nem apontar para indices instalados a partir do protocolo TEMP.
- Adicionar testes de alteracao de um arquivo vetor, symlink/junction (se privilegio disponivel), rename/TOCTOU.

## DQ-E-D-3C-E-2 — Liveness, cancelamento e processo
- Handoff controlado por canal pai-filho com encerramento imediatamente observavel e protecao contra reutilizacao de nonce/resultado atrasado.
- Provar concorrencia com writer real Win32 em scratch, queda forcada do pai/child, timeout e recuperacao do lock, sem deixar modelo rodando orfao.
- Diferenciar resultado meramente verificado de atestacao do lock retido durante toda a inferencia.
- Executar regressao RAG-DEL/RAG-AUTO e auditoria Git seletiva por fase.

## Criterios de ativacao (ainda BLOQUEADOS)
Somente quando o worker real, GUI instalada e MCP exposto estiverem atestados, os journals e a fila revisados e houver autorizacao especifica para piloto reversivel considerar cutover. Nunca promover Stable, GitHub ou executar exclusao real automaticamente.