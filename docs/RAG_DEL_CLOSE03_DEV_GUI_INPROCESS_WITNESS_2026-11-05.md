# CLOSE-03 ? Evid?ncia de GUI Qt DEV com c?digo carregado

Data: 2026-11-05 (hor?rio local da m?quina)

## Escopo

Registro de uma execu??o diagn?stica isolada no DEV. N?o ? evid?ncia da GUI Stable instalada, n?o ? autoriza??o operacional e n?o habilita exclus?o.

## Processo observado

- Reposit?rio: `C:\Users\Matheus\CodeBridge-MCP-Bridge`
- Branch de origem: `dev-local`
- Python: `C:\Users\Matheus\CodeBridge-Runtime\dev\Scripts\python.exe`
- PID observado pelo kernel: `5588`
- Nascimento do processo (microssegundos): `1793904290745000`
- Interface Qt executada com `QT_QPA_PLATFORM=offscreen`
- Widgets efetivamente instanciados e exibidos: `RagPanel` e `KnowledgeRemovalReviewPanel`
- Transporte: Named Pipe ef?mero `CB.RAGDEL.GUIWITNESS.<PID>.<birth>`

## Resultado do verificador independente

- Estado: `GUI_LOADED_CODE_KERNEL_PINNED_READONLY`
- PID do servidor observado por `GetNamedPipeServerProcessId`: `5588`
- Nascimento do processo conferido: sim
- Desafio aleat?rio vinculado ? resposta: sim
- PID do peer conectado obtido pelo kernel: correspondente ao verificador
- AccessCheck do token do peer: conclu?do e permitido
- Recibos de c?digo carregado: 2, ambos correspondem ao c?digo esperado no DEV

| S?mbolo carregado | SHA-256 do code object |
|---|---|
| `rag_panel.review_authorization` | `2aa623b83e9333233091db3169501f97383e4312a9dccf5b21cf2002436c7c7d` |
| `rag_deletion_review_panel.review_selected` | `530031e30d56a457c162f332e8905f0c1143461248e85261f92c1d78898fadd7` |

Os dois m?dulos foram reportados a partir de:

- `app_rewrite/rag_panel.py`
- `app_rewrite/rag_deletion_review_panel.py`

## Limites expl?citos

Os campos abaixo permaneceram falsos no resultado:

- `installed_gui_operationally_attested`
- `ipc_peer_effective_acl_attested`
- `activation_authorized`
- `operational_use_allowed`

O resultado prova somente que o processo Qt DEV separado, com os dois pain?is instanciados, respondeu ao desafio externo e que o c?digo em mem?ria correspondeu aos s?mbolos esperados no DEV. N?o prova que a GUI Stable est? executando esse c?digo; tampouco prova um canal IPC operacional de autoriza??o por requisi??o.

## Regress?o

O teste `tests/test_rag_del_close_03_gui_witness_dev.py` foi atualizado para instanciar os dois pain?is Qt no processo filho antes de iniciar o testemunho.

- Teste focado: 2 PASS
- RAG-DEL completo ap?s a altera??o: 840 executados, 833 PASS, 7 SKIP, 0 FAIL
- Commit: `e2c8417 test(rag-del): instantiate DEV GUI in witness proof`

## Seguran?a e estado operacional

- Nenhum arquivo, processo ou configura??o Stable foi alterado.
- Nenhum cat?logo, fila, canary ou gera??o p?blica foi modificado.
- Decis?o KEEP de `newworldpvp` preservada.
- Exclus?o permanece desabilitada.
- CLOSE-03 G32 permanece BLOCKED at? prova independente do canal IPC operacional e revis?o final de todos os crit?rios.
