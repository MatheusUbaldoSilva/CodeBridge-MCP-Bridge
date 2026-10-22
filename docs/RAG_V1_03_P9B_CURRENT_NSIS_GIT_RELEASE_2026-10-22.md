# P9-B ? Novo instalador NSIS baseado no HEAD Git

Data: 2026-10-22
Status: VALIDADO OFFLINE, NAO INSTALADO; P9-B ABERTA.
Branch: rag-017-optimized-inference-after-candidate
Fonte Git: c7b0a464c9ad1915a173d480d863a1b2f0734a53

## Pacote isolado

%LOCALAPPDATA%\CodeBridge-MCP-Bridge\release_staging\P9B_CURRENT_c7b0a46\CodeBridge-P9B-CURRENT-GUARDED-Preview.exe

SHA-256: 5e49d77d933744016276f460d3900aee1becadb0df430ba8aa459de5b03992fe
Tamanho: 27271347 bytes.
Auditoria: P9B_NSIS_GIT_PAYLOAD_VERIFIED, sete modulos criticos, 264 entradas
no inventario bruto, zero arquivos Python nao versionados.
A protecao NSIS de processo corresponde ao commit c7b0a46.
Nenhuma alteracao foi aplicada a instalacao ativa.

## Snapshot compat?vel com ESTE instalador

%LOCALAPPDATA%\CodeBridge-MCP-Bridge\release_staging\P9B_CURRENT_c7b0a46\FULL_NSIS_PREINSTALL_SNAPSHOT.zip

SHA-256: 6f6cb339afd19e391233368858334a44fccbb86ad7a19422ec07ee79ae54e78b
Cobertura: 258 destinos NSIS, 236 arquivos existentes.
Verificacao: INSTALLER_ROLLBACK_SNAPSHOT_VERIFIED.
Comparacao instalada: INSTALLED_BASELINE_MATCH, 236 de 236.
Restauracao isolada: ISOLATED_INSTALLER_RESTORE_REHEARSED, 236 arquivos.
Esse ZIP cobre os arquivos que o NSIS pode sobrescrever; nao e backup
integral de configuracoes, registro, conexoes nem dados RAG.

## Gate de atualiza??o real

OFFICIAL_UPDATE_BLOCKED:
- ACTIVE_MCP_MUST_SHUT_DOWN
- ACTIVE_CODEBRIDGE_GUI_MUST_SHUT_DOWN

O canal independente Remote Desktop foi observado online antes dos ensaios.
O MCP principal PID 9300 foi observado fora da arvore atual da GUI PID 1376.
N?O tratar PID como identidade suficiente; validar create_time e origem antes
de qualquer parada e executar nova auditoria do guard no momento do cutover.

Este pacote permanece PREVIEW, nao autorizacao de publicar em main e nao
pode ser usado para contornar o process guard nem para atualizacao automatica.
Nenhum processo, fila, scheduler, indice publico ou instalacao foi alterado.
Preservar os tres arquivos sujos/preexistentes separados do commit.

## Proximo passo

Preparar um supervisor independente, com controle do canal de recuperacao,
prova de desligamento GUI/MCP, revalidacao de hash e snapshot,
atualizacao NSIS oficial e prova real de reconexao do MCP/tunel.
Somente apos instalar a versao aprovada consultar a nova ferramenta oficial
codebridge_rag_queue_bootstrap em execute=false antes de eventual autorizacao
especifica para inicializar fila e ensaiar um job supervisionado.
