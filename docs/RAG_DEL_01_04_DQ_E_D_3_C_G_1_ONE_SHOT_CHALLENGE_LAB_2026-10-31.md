# RAG-DEL-01.04-DQ-E-D-3C-G-1 — Desafio por sessao e recusa de replay (DEV)

## Implementacao
- knowledge_deletion_liveness_parent_lab.py: apos preflight CHILD_VERIFIED, pai gera challenge aleatorio de 256 bits por sessao supervisionada e envia ACK vinculado ao nonce do envelope. Exige SHA256 desse challenge no resultado do filho, alem de projeto, geracao, nonce, request digest, tree digest e flags operacionais falsas. O challenge nao e reutilizado pelo pai.
- knowledge_deletion_liveness_child_lab.py: interpreta unicamente ACK com nonce exato e challenge de 64 caracteres hex lowercase. Faz hash do challenge e devolve challenge_sha256 apos revalidar catalogo, SQLite, manifesto, arvore vetorial e processo pai. Respostas e ACK malformados sao recusados.
- Limite de leitura do ACK ajustado para comportar os 102 caracteres do protocolo. Durante o teste inicial a leitura anterior de 100 caracteres fez falhar o caminho valido; corrigido e validado.

## Evidencias
2 testes acrescentados: parser recusa nonce antigo, challenge curto ou com caracteres invalidos e ACK truncado; resposta com mesmo nonce e request digest de outra sessao falha no hash do challenge novo. 15 testes da bateria supervisionada PASS, incluindo kill pai/filho e locks Win32.
Regressao final: RAG-DEL 432 (426 PASS, 6 SKIP), RAG-AUTO non-MCP 241 (236 PASS, 5 SKIP). Total 673 (662 PASS, 11 SKIP), zero falhas.

## Limites
Este mecanismo dificulta o replay de respostas antigas ENTRE sessoes pois o pai exige challenge aleatorio novo, mas NAO autentica criptograficamente o processo pai/filho perante adversario que consiga ler/manipular o pipe ativo. O worker real foi exercitado apenas em modo scratch supervisionado, sem modelos, Qdrant instalado ou inferencia semantica real. O mecanismo nao habilita deletacao, processamento operacional ou promocao Stable.

Proximo marco DQ-E-D-3C-G-2: analisar identidade do canal e limitacoes de autenticacao do worker/handle em DEV, incluindo falha fechada em eventos de processo, antes de estudar uma homologacao instalada. Journal reconciliation, GUI/MCP loaded-process generation_probe e fila READY_FOR_REVIEW continuam bloqueadores.