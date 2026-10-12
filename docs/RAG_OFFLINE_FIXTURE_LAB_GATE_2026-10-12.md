# RAG   Laboratório de snapshot offline e recuperação isolada

Data: 2026-10-12
Estado: SOMENTE LABORATÓRIO   PRODUÇÃO NÃO AUTORIZADA

## Contrato de segurança

Este incremento NÃO executa backup de produção e NÃO liga publicação ou troca de geração.
Os comandos autônomos aceitam exclusivamente raiz com basename `codebridge-rag-generation-test`.
A flag `--lab-only` é obrigatória e não oferece nenhuma opção que a substitua.
Não usar esses comandos em caminhos reais de produção.

## Entrada autônoma (processos distintos do MCP)

- `python rag_offline_fixture_cli.py --fixture-root CAMINHO_TESTE --backup-name nome --lab-only`
- `python rag_offline_fixture_restore_cli.py --fixture-root CAMINHO_TESTE --backup-name nome --restore-name novo --lab-only`
- `python rag_offline_quiescence_cli.py`   relatório somente leitura, sai com código 2 por projeto.

## Provas executadas

- SQLite e Qdrant sintetizados com manifesto coerente
- SHA-256 de origem e destino e validação cruzada do bundle copiado
- Verificador de snapshot em segundo processo Python
- Restauração para destino novo sem ativar ponteiro
- Bloqueio de sobrescrita, symlinks, junctions, hardlinks e sidecars SQLite
- Bloqueio por lock entre processos e tentativa real de handle aberto para escrita
- Captura interrompida e adulteração bloqueadas
- Arquivos temporários de restauração removidos sem apagar o backup original

## Limitações bloqueantes

O lock cooperativo só coordena processos que respeitam o mesmo protocolo.
Um inventário de processos pelo `tasklist` não demonstra ausência de handles, mapeamentos de memória ou transações em andamento.
A verificação de compartilhamento do Windows é outra barreira, mas também não prova parada completa do aplicativo.
Resultados `UNPROVEN_QUIESCENCE` nunca significam autorização.
A ferramenta autônoma de diagnóstico devolve código 2 mesmo se não identificar processos suspeitos.
Não existe caminho de produção nesse capturador.

## Próximo marco

Desenvolver e verificar um procedimento externo de encerramento completo da GUI/MCP/adapters/indexadores com comprovação de handles e dados estáticos durante toda a janela de manutenção, depois capturar somente com consentimento explícito e destino aprovado. Exigir teste independente de restauração antes de propor publicação real.

## Preservação

O benchmark modificado e o runbook preexistente fora do Git deste ciclo não são parte deste incremento e não devem ser removidos ou adicionados incidentalmente.
