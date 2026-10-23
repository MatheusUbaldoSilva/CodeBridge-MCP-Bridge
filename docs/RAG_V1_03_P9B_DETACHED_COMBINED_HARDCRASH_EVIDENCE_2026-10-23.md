# P9-B ? Recuperacao combinada sob hard crash externo

Data: 2026-10-23
Status: VALIDADO EM LABORATORIO; PRODUCAO NAO AUTORIZADA.

## Novas provas

- Atomic shortcut restore: subprocess separado executou substituicao real de atalho em diretorio temporario, encerrou com os._exit(77); novo processo continuou o journal e verificou o atalho.
- Real shell backend com FakeWinreg: subprocess caiu com os._exit(79) depois da primeira substituicao; outro subprocess executou novamente o backend e validou a captura original.
- Real shell backend com HKCU simulado persistente em JSON: primeira operacao de replace_key foi gravada e processo terminou com os._exit(80); segundo subprocess reabriu e concluiu o estado esperado de ambas as chaves. Nenhuma chave real HKCU foi alterada.
- Recuperacao COMBINADA: primeiro subprocess restaurou arquivos existentes, removeu destinos novos conhecidos, restaurou atalhos e caiu com os._exit(81) depois de modificar uma chave HKCU simulada. Outro subprocess continuou com o journal duravel, revalidou arquivos e atalhos e concluiu ambas as chaves. Ultimo evento: SHELL_DETACHED_COMBINED_VERIFIED.
- Os ensaios exigiram um segundo interpretador/processo independente em vez de uma excecao sintetica.
- Regressao de familia P9-B: 434 testes aprovados.

## Limites e proximas etapas

A simulacao de HKCU e implementada com arquivo JSON no diretorio temporario. Nao equivale a usar o registro Windows real nem prova recuperacao sob perda de energia. Os testes injetam verificacoes de processos parados e gates de rollback, portanto nao autorizam mutacoes na instalacao.

Antes de realizar NSIS oficial:
- supervisor realmente destacado da GUI/MCP deve passar pelos gates e sobreviver a interrupcao real;
- processo instalado devera ser parado e religado com evidencias de listeners e CBMCP/1;
- validar restauracao completa contra escopo controlado do Windows e mecanismo de compensacao;
- validar bootstrap fila RAG/scheduler e politica de rollback;
- auditar Git, diff, snapshot, hashes e explicitacao da janela de corte.

Preservar os tres arquivos locais historicos fora de escopo. P9-B permanece ABERTO.
