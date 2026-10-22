# P9-B — Handoff: cobertura integral dos arquivos do instalador (2026-10-22)

Status: P9-B ABERTA; instalação MCP ativa NÃO alterada.

## Evidência

O NSIS atualizado a partir do Git contém 256 destinos. O pacote inicial
de rollback cobria apenas sete módulos MCP e era insuficiente para uma
atualização NSIS completa. O novo snapshot offline preserva 236 arquivos
existentes e identifica 20 destinos ainda ausentes.

Artefato NSIS limpo:
%LOCALAPPDATA%\CodeBridge-MCP-Bridge\release_staging\P9B_GIT_f42b727\CodeBridge-P9B-CLEAN-Preview.exe
SHA256: 3e6b220d8571abad42a8f9cc148468fc69d535a6271d51b7c4078fc0e09a4667

Snapshot de 236 arquivos:
%LOCALAPPDATA%\CodeBridge-MCP-Bridge\release_staging\P9B_GIT_f42b727\FULL_NSIS_PREINSTALL_SNAPSHOT.zip
SHA256: 30d85e86480ca32d809d0f28bc579f8bd708441b061f145f6fb22d5e51feb176
Dados anteriores: 67.214.038 bytes; ZIP: 31.957.517 bytes.

Provas reais: INSTALLER_ROLLBACK_SNAPSHOT_VERIFIED,
INSTALLED_BASELINE_MATCH antes e depois,
ISOLATED_INSTALLER_RESTORE_REHEARSED para 236 arquivos.
Nenhum arquivo instalado modificado, nenhuma restauração em produção.

## Implementação

- installer/rag_p9b_installer_rollback_scope.py: inventário NSIS,
  allowlist, snapshot com hashes, verificação da base e restauração
  em diretório temporário isolado, sem tocar na instalação.
- installer/rag_p9b_official_update_preflight.py: negativa de
  manutenção com MCP/GUI ativos, ponteiro alterado, journal,
  snapshot divergente ou recuperação não comprovada.
- Testes de regressão relativos ao pacote: 31 PASS.
- Commits: 7a0ac61 e 25c2808.

## Bloqueios reais

OFFICIAL_UPDATE_BLOCKED:
- ACTIVE_MCP_MUST_SHUT_DOWN (PID 9300)
- ACTIVE_CODEBRIDGE_GUI_MUST_SHUT_DOWN (PID 1376)

O snapshot cobre arquivos sobrescritos, NÃO equivale a rollback
completo do registro, atalhos, serviços e conexões. Não executar
o instalador automaticamente nem contornar bloqueios.

Público preservado: v1_delta_1ae1d01ea84f4e, READY,
211 documentos, 8774 chunks. Fila, worker e scheduler inativos.

## Próximo passo

Comprovar ciclo oficial de desligamento, instalação e recuperação MCP;
validar integridade e reconexão; descobrir a ferramenta
codebridge_rag_queue_bootstrap; primeiro preview execute=false;
somente depois bootstrap autorizado e job único supervisionado.
A política de fechamento exige Git, auditoria pós-commit e patch notes.
