# P9-B ? Candidato NSIS oficial preparado no Windows atual

Fonte limpa obtida de git archive HEAD no commit
f45880511c7f8a920c551bb9c92add75874cfd08.
Compilado o installer/CodeBridge.nsi sem executar o instalador,
sem modificar a instalacao em uso e sem incluir os tres arquivos
locais pendentes. Binarios tunnel-client e cloudflared copiados
apenas para a arvore descartavel de build.

Candidato privado em LOCALAPPDATA/CodeBridge-MCP-Bridge/release_staging/
P9B_HEAD_CANDIDATE_f45880511c/source/installer/dist/CodeBridge-Setup.exe
SHA256 d7b847a850bc6bacda5c7539b14e2f36b5648c4dd2ac93c6fdd18f354ed58664
Payload validado: 258 destinos, mesmo conjunto do backup anterior;
arquivo RAG incremental nao versionado excluido.

Backup proprio: P9B_HEAD_FULL_PREINSTALL_SNAPSHOT.zip
SHA256 c7fdacf996d5081e743caca0a092e6c0518dd4914af331fdc6f320ba81e6299e
236 arquivos existentes, 22 destinos novos;
inspect_installer_snapshot_baseline = INSTALLED_BASELINE_MATCH.

Identidade duravel: P9B_HEAD_TRANSACTION_IDENTITY.json
SHA256 6a2d32f0c4264b8dfe54b0c25e342d8cd1f94d594cdc9d98908380f0133ba9dc
Quatro artefatos vinculados, incluindo snapshots de HKCU/atalhos
e crash preimage anteriores, ainda validos.
Estado shell existente: SHELL_POSTRESTORE_MATCHED, cinco atalhos
e duas chaves, nenhum valor sensivel exibido.

Bloqueio da maquina atual: CURRENT_MACHINE_CUTOVER_REFUSED,
PROCESSES_NOT_EXTERNALLY_STOPPED.
O NSIS oficial usa HKCU, InstallDirRegKey, atalhos e bootstrap;
direcionar /D sozinho nao isola todos os efeitos.
Exigir supervisor Windows externo com parada independente,
rollback completo real e reconexao antes da atualizacao.

Nenhum processo foi parado e NSIS nao foi executado.
P9-B aberta; producao intacta.
