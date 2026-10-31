# RAG-DEL-01.04-DQ-E-D-3C-C — Journal e caminhos no worker scratch (DEV)

## Alteracao
O verificador de envelope knowledge_deletion_pin_ipc_lab.py agora falha fechado se existir qualquer rag-del-*.journal.json na raiz TEMP autorizada, inclusive se seu estado for ROLLED_BACK. Volta a verificar a presenca de journal depois da validacao dos hashes/SQLite, para cobrir race entre o inicio e o final da leitura. Rejeita links simbolicos e junctions da pasta intermediaria generations antes de resolver a geracao. Nao arquiva nem deleta journals automaticamente.

## Evidencia
Foram acrescentados 4 testes na suite real worker pinned SQLite:
- Journal ROLLED_BACK bloqueia leitura e permanece intacto.
- Worker isolado recusa journal PREPARED sem confiar em lock do parent.
- Journal inserido durante a validacao dos hashes e detectado antes do sucesso.
- Teste de link simbolico no root de generations condicionado a permissao Windows: SKIP por WinError 1314 (sem privilegio de symlink), nao considerado comprovacao de execucao deste caso.

RAG-DEL: 404 executados, 399 PASS, 5 SKIP, zero falhas.
RAG-AUTO sem MCP: 241 executados, 236 PASS, 5 SKIP, zero falhas.
Total: 645 executados, 635 PASS, 10 SKIP, zero falhas.

## Nao autorizado
Modo de worker real permanece apenas --pinned-scratch-only/--pinned-scratch-snapshot com SQLite TEMP e contagem por projeto. Nao ha inferencia, Qdrant ou deletacao operacional. O guard apenas acrescenta recusa; reconciliacao/arquivamento de journal de verdade exige processo e aprovacao separados. Nao mudou Stable, fila, GUI/MCP instalado, catalogo real ou GitHub.