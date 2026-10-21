# CodeBridge RAG V1.03-D-C — Patch notes e fechamento técnico

Data: 2026-10-21

## Alterações
- `installer/runtime_postupdate_verify.py`: compara alterações apenas do manifesto, SQLite e árvore Qdrant do índice público; exige baseline histórica versionada.
- `tests/test_installer_runtime_postupdate_verify.py`: teste de relatório sem diferenças espúrias.
- `installer/dist/CodeBridge-Setup.exe`: instalador NSIS recompilado e utilizado na manutenção supervisionada.
- `installer/dist/CodeBridge-Setup.sha256`: SHA-256 correspondente ao instalador.

## Evidências da manutenção
- Operador autorizou manutenção; Remote Desktop independente conectado, CodeBridge encerrado normalmente antes da atualização.
- Backup integral da instalação (8.197 arquivos) conferido por SHA-256; restauração em pasta isolada também conferida integralmente.
- Bootstrap do instalador oficial concluído; Python embarcado importa `rag`, `qdrant_client` e dependências sem injeção de caminhos.
- Jina Code real: worker de staging sintético aprovado sem publicação; Jina Text real: vetor de 1.024 dimensões aprovado.
- MCP CodeBridge voltou a READY, índice `legacy` READY com 210 documentos e 8.761 chunks; worker automático desativado.
- Manifesto, SQLite e Qdrant permaneceram iguais à baseline histórica.
- Regressões: 64 testes do instalador e 284 testes incrementais RAG aprovados.

## Política de fechamento
- Os dois arquivos históricos pendentes (benchmark e runbook de rollback) NÃO fazem parte deste patch.
- Este registro documenta o fechamento técnico D-C; encerramento Git exige diff staged limpo, commit, push e auditoria pós-commit.
- Não foram ativados worker automático, scheduler, publicação ou troca da geração pública.

Relatório local: `%LOCALAPPDATA%\CodeBridge-Maintenance-Backups\V103DC_PreUpdate_20261020\MAINTENANCE_RESULT_20261020.txt`.
