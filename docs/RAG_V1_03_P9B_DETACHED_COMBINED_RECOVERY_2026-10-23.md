# P9-B ? Recuperacao combinada desacoplada ? 2026-10-23

Estado: EM DESENVOLVIMENTO, NAO APROVADO PARA INSTALACAO.

## Continuidade

Base: commit d870279.
Os arquivos pendentes anteriores nao foram incluidos em nenhum commit.

## Incrementos desta janela

- 6ab96d6: coordenador que ordena arquivos ? registro/atalhos ? verificacao cruzada.
- 500a348: journal admite transacao combinada e impede replay apos sucesso.
- f80f7fb: teste de replay apos interrupcao do shell usando journal duravel.
- bef2632: teste dos backends reais de arquivos e atalhos num diretorio temporario, com HKCU simulado.
- 6fa7684: correcao do journal: FILE_RESTORED e parcial no contexto combinado, nao representa sucesso final.

## Validacao observada

- 375 testes da familia P9-B aprovados na regressao.
- A restauracao combinada em fixture recupera arquivo antigo, remove candidato novo conhecido e restaura atalhos.
- Conteudo desconhecido de destino novo impede prosseguir.
- A interrupcao entre arquivo e shell admite replay desde que o journal permaneca incompleto.
- Nenhum NSIS foi executado.
- Nenhuma instalacao real, HKCU real, indice RAG real ou GUI ativa foram alterados.

## Limites

O coordenador continua dependente de trabalhadores injetados; nao exp?e CLI de atualizacao.
O teste com HKCU usa FakeWinreg e diretorios temporarios.
Nao ha prova de desligamento real completo nem de handles do CodeBridge instalado.
A validacao end-to-end em laboratorio NAO equivale a recuperacao de producao.

## Proximo alvo

1. Integrar o gate do supervisor real aos dois trabalhadores com identidade criptografica vinculado ao candidato NSIS atual.
2. Revisar idempotencia, revalidacao de processos apos crash e registro de transicao duravel.
3. Provar retomada combinada sob falha parcial de HKCU/atalhos com verificacao independente.
4. Somente depois revalidar NSIS do HEAD atual, executar cutover autorizado fora do MCP e demonstrar CBMCP/1 e RAG queue.
