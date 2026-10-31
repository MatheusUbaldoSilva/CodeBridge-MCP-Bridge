# RAG-DEL-01.04-DQ-C-A — Sessao de leitura privada composta (DEV)

Nova API private_read_session_lab (somente laboratorial) coordena os context managers injetados nesta ordem: generation compartilhado -> semantic exclusivo quando requerido -> catalog mutex com timeout limitado. Depois de adquirir os locks valida identidade da entrada, caminho da geracao, hash SQLite e hash do manifesto. Revalida ambos os hashes e o catalogo ao encerrar a leitura, ainda sob os locks.

PrivateLabPin apresenta flags activation_authorized=False e operational_use_allowed=False. O callback semantico sintetico so pode ser chamado enquanto semantic_lock_held=True e a sessao estiver aberta. Nao chama semantic_isolated_project e nao pretende atestar o subprocesso MCP instalado.

A prova usa o Win32 LockFileEx real em raiz TEMP via resolver injetado nos testes. Outra instancia com generation exclusivo nao consegue obter o lock durante a sessao e pode obte-lo depois de sua liberacao. Testes tambem verificam ausencia de vazamento entre projetos, journal pendente, mismatch de manifesto, mudanca durante a leitura e bloqueio de callback apos fechamento.

9 testes DQ-C-A passaram. Regressao: RAG-DEL 334 (330 PASS, 4 SKIP), RAG-AUTO sem MCP 241 (236 PASS, 5 SKIP), zero falhas.

Proximo passo DQ-C-B: provar o contrato com os pontos reais de search/get-context e subprocesso semantic, sem dupla aquisicao de lock. Nao integrar na GUI/MCP instalado, nao alterar Stable nem indices reais e nao habilitar exclusao.