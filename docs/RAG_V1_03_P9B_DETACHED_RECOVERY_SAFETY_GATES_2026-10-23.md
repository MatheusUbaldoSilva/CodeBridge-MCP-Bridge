# P9-B ? Gates de recupera??o combinada desacoplada

Data: 2026-10-23
Estado: P9-B ABERTO. Nenhuma instalacao NSIS aplicada na maquina ativa.

## Sequencia obrigatoria para producao

1. Supervisor independente recebe manifest e SHA256 de identidade duravel.
2. O coordenador verifica diretamente a identidade dos 4 artefatos, caminho instalado e commit de origem.
3. Primeira observacao de parada valida ausencia de CodeBridge/MCP ativos.
4. Trabalhador externo restaura arquivos com hashes e journal, SEM autorizar NSIS.
5. Segunda observacao de parada antes de modificar HKCU/atalhos.
6. Trabalhador de shell verifica restauracao com snapshot e preimagem.
7. Terceira observacao de parada antes da pos-verificacao independente.
8. Sucesso combinado apenas com comparacao de arquivos, 2 HKCU e 5 atalhos.

Retornos INDEPENDENT_POSTSTOP_REQUIRED, POSTSTOP_LOST_BEFORE_SHELL e
POSTSTOP_LOST_BEFORE_POSTVERIFY sao recusas esperadas enquanto o processo
esta ativo ou reaparece. A existencia de arquivos de backup por si so nunca
autoriza uma atualizacao.

## Evidencias verificadas

- Identidade real gerada em fixture com 4 artefatos: integracao PASS.
- Mudanca de bytes do instalador e divergencia de commit bloqueiam antes do journal.
- Falhas de HKCU com tentativa posterior e crash apos restaurar arquivos: ensaios isolados PASS.
- Preflight real com CodeBridge ativo: recusa INDEPENDENT_POSTSTOP_REQUIRED.
- Regressoes P9-B anteriores: 388 PASS antes das ultimas duas protecoes.

## LIMITES IMPORTANTES

Testes com FakeWinreg e arquivo temporario nao provam recuperacao de producao.
O coordenador so aceita workers externos explicitamente fornecidos; ele nao
implementa ainda controle de privilegios de ponta a ponta ou execucao oficial NSIS.
Nenhum indice RAG/SQLite ou servico instalado foi alterado durante estes testes.
A proxima preparacao de instalador exige reexportacao do HEAD commitado e nova
identidade dos artefatos; candidato ligado a commit anterior nao serve para corte.

Arquivos sujos anteriores do usuario continuam fora dos commits:
- benchmarks/rag017_code_only_extended_smoke.json
- docs/RAG_017_J_VM_ROLLBACK_RUNBOOK_2026-10-10.md
- rag/runtime/incremental_installed_queue_init.py
