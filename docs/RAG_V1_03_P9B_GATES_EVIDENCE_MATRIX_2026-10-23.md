# P9-B ? Matriz de evidencia e criterios de fechamento

Data: 2026-10-23
Estado: ABERTO / release real ainda nao autorizada.
Ultimo commit verificado nesta auditoria: 410c02f.

| Gate | Estado | Prova / criterio pendente |
|---|---|---|
| MCP e RAG vigentes | READY | CBMCP/1 e RAG reportaram READY, geracao v1_delta_1ae1d01ea84f4e |
| Git de trabalho | SINCRONIZADO | HEAD e origin coincidentes, 3 arquivos locais anteriores preservados |
| Integridade de manifesto e fingerprints | TESTADO | Provas fail-closed para hashes, tipos e chaves JSON duplicadas |
| Su?te P9-B | 483 PASS | Regressao de laboratorio, nao substitui teste real |
| Model fallback GPU-CPU | INTEGRACAO SIMULADA PASS | E2E com modelo Jina Code real ainda nao executado |
| NSIS oficial | CANDIDATO ANTIGO | Binario isolado registrado em f458805; nao e release validada para HEAD atual |
| Snapshot de arquivos | HISTORICO | Backup antigo foi verificado para candidato f458805; requer pareamento com release atual |
| Shell HKCU e atalhos | HISTORICO | Snapshot/replay e pos-verificacao de laboratorio, falta rollback real independente |
| Supervisor externo | INCOMPLETO | Validar processo independente capaz de parar, recuperar e monitorar |
| Parada real do MCP e GUI | NAO FEITA | Exige controlador independente para manter reconexao |
| Instalar NSIS em maquina em uso | BLOQUEADO | Nunca executar com pilha ativa e sem rollback atestado |
| Retorno apos falha | NAO CERTIFICADO | Crash, replay e restaura??o arquivos/registro/atalhos comprovados |
| Reconexao publica | NAO CERTIFICADA | CBMCP/1 novo handshake e autorizacao/fila/scheduler/RAG apos update |

## Sequencia para proxima iteracao

1. Construir candidato estritamente de git archive do HEAD aprovado numa arvore descartavel; nao usar build que copia Setup para Desktop.
2. Gerar e validar novo snapshot vinculado ao SHA256 exato do candidato. Jamais reutilizar as provas vinculadas ao f458805 para um novo binario.
3. Auditar isolamento real do supervisor externo da GUI e do MCP que serao parados.
4. Exercitar transacao de rollback em ambiente isolado, incluindo falha parcial e reinicio do supervisor.
5. Somente em janela autorizada, efetuar NSIS real, verificar arquivos, HKCU, atalhos, supervisor e religacao.
6. Exigir handshake MCP CBMCP/1, estado da fila e RAG, hashes do indice publico e audit Git posterior.

Todos os testes de laboratorio continuam sem permissao automatica para implantar.
P9-B nao fecha sem teste NSIS real, rollback independente, retomada MCP/RAG e
auditoria pos-commit. Tres arquivos locais historicos nao devem ser inclu?dos no installer.
