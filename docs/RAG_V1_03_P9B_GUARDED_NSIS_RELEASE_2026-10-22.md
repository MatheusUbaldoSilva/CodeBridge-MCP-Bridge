# RAG V1.03 — P9-B: instalador com dupla protecao MCP (22/10/2026)

Status: PREVIA OFFLINE COMPILADA E TESTADA; NÃO IMPLANTADA.
Branch: rag-017-optimized-inference-after-candidate.

## Problema confirmado

O atualizador oficial CodeBridge verificava apenas um PID da interface
antes do download e nao repetia a verificacao antes do subprocess.Popen.
O NSIS instalado nao bloqueava por si mesmo uma atualizacao iniciada
manualmente com o MCP ainda em execucao. Isso era um risco real de
atualizacao incompleta do Python portatil e do servidor MCP.

## Correcao

installer/p9b_update_process_guard.py
- Examina em modo somente leitura a command line dos processos associados
  a instalacao especifica CodeBridge (main.py e mcp_server.py).
- Falha de enumeracao ou falta de psutil = bloqueio, nunca permissoes.
- CLI --install-root retorna 2 com GUI/MCP ativos, 0 somente quando
  confirma ambos ausentes. Nao encerra processos.

installer/updater.py
- Verifica GUI e MCP antes de iniciar o download.
- Repete a verificacao imediatamente antes de abrir o instalador.
- Em caso de bloqueio, mantem o download, nao inicia o .exe.

installer/CodeBridge.nsi
- .onInit: exige ambos encerrados quando uma instalacao anterior existe;
  inclui fallback mesmo sem entrada de registro Windows.
- Section SEC_MAIN: repete a verificacao imediatamente antes de
  sobrescrever arquivos, evitando reabertura da interface durante a UI.
- Embute o guard no $PLUGINSDIR e tambem no diretorio installer.

installer/rag_p9b_clean_release.py + _audit.py
- Exigem script temporario de processo versionado no commit Git;
  comparam seus bytes ao arquivo do commit.
- Nao confundem $PLUGINSDIR com fonte Python solta e continuam
  recusando todo outro Python nao versionado.

## Testes e commits

- 33 regressões de protecao/instalador PASS no primeiro pacote.
- 21 regressões de proveniencia/guard PASS na alteracao adicional.
- 20 regressões de fallback e rechecagem NSIS PASS na terceira.
- NSIS compilado temporariamente e depois diretamente a partir do Git.
- Ferramenta portatil instalada executou guard de verdade:
  UPDATE_PROCESS_BLOCKED, GUI PID 1376 e MCP PID 9300,
  sem alterar os processos.
- fddbf30: protecao GUI + MCP updater e NSIS.
- ebcb07a: proveniencia do script temporario versionado.
- 3feed9b: fallback sem registro e checagem antes da sobrescrita.

## Artefatos de validacao em armazenamento separado

Executavel NAO EXECUTADO:
%LOCALAPPDATA%\CodeBridge-MCP-Bridge\release_staging\P9B_FINAL_GUARDED_3feed9b\CodeBridge-P9B-FINAL-GUARDED-Preview.exe

SHA-256:
77c7c64a0af4065431d1b4769347d3c2e1abd1efbc83cb4a37cc44256b77ad97
Tamanho: 27.277.663 bytes.
Commit de origem:
3feed9b8e93bbdb02cb209478ef03bf0395d2473
263 entradas no pacote; 7 modulos criticos conferidos; zero
Python nao versionado; script $PLUGINSDIR igualmente verificado.

Novo snapshot:
%LOCALAPPDATA%\CodeBridge-MCP-Bridge\release_staging\P9B_FINAL_GUARDED_3feed9b\FULL_NSIS_PREINSTALL_SNAPSHOT.zip
SHA-256:
fd88e67d96cb91deff2881c95398d4be2b911a5194ecbbaecd3c10cc8fe03fd8
257 destinos no instalador, 236 arquivos anteriores preservados.
Snapshot verificado, baseline instalada conferida antes/depois.
Restauracao de todos os 236 arquivos ensaiada em scratch isolado.

## Limites

A protecao do NSIS recusa a atualizacao de executaveis ativos, mas
NAO prova automaticamente que reiniciar o MCP, o tunel, a interface
e as credenciais depois da instalacao sera bem sucedido.
O backup cobre os arquivos listados, nao operacoes do registro,
atalhos e conexoes. O updater atualmente busca releases de main;
estes commits estao na branch de desenvolvimento.
Nenhuma atualizacao real, restart, inicializacao de fila, worker
ou scheduler foi realizada nesta sessao.

Proximo ciclo: validar procedimento oficial de desligamento/reabertura,
caminho de rollback independente, e entao implementar implantacao
supervisionada; confirmar tool live em execute=false antes de bootstrap.
RAG publico permanece v1_delta_1ae1d01ea84f4e, 211 docs/8774 chunks.

P9-B CONTINUA ABERTA.
