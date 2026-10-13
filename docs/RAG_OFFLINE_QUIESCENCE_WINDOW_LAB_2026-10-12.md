# RAG   Janela de quiescência sintética (gate não autorizativo)
Data: 2026-10-12
Estado: LABORATÓRIO; NÃO PROVA PARADA DE PRODUÇÃO.

## Escopo
Amostragem de fingerprints de SQLite, manifesto e todos os arquivos Qdrant
com proteção de handles compartilhados somente para leitura, lock cooperativo
e inventário de processos por tasklist em cada amostra.

CLI externo de diagnóstico:
`python rag_offline_quiescence_window_cli.py --fixture-root CAMINHO_SINTETICO --lab-only`

A ferramenta sempre devolve código 2 e `copy_authorized=false`.
`LAB_STABLE_BUT_UNPROVEN` só indica estabilidade observada em um intervalo
do laboratório, nunca a ausência total de writers, mmap ou handles externos.
Na máquina de desenvolvimento é esperado bloqueio por python.exe/pythonw.exe.

## Falhas verificadas
Processos suspeitos ou inventário impossível, lock concorrente, mutação detectada,
erro de handle (incluindo tentativa de escrita negada), raiz inválida e
parâmetros inválidos bloqueiam. Nenhum arquivo de produção é lido por este utilitário.

## Pendência obrigatória
A prova de parada total da GUI, MCP, indexadores, adaptadores, acesso Qdrant,
handles e eventual cache mmap deve ser construída em procedimento EXTERNO
à aplicação e exercitada sob manutenção autorizada. Nada aqui liga backup real.
