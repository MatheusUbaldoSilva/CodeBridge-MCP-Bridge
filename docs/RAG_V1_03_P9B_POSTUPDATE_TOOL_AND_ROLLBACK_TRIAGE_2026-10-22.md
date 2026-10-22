# CodeBridge RAG V1.03 — P9-B pós-atualização e rollback triado

Data: 2026-10-22
Branch: rag-017-optimized-inference-after-candidate
Estado: P9-B EM ANDAMENTO; binário gerado e testado OFFLINE.
Nenhuma atualização ou restauração ocorreu no CodeBridge em uso.

## Objetivo alcançado nesta janela

Diferenciar o código compilado da ferramenta realmente implantada e
permitir a inspeção do estado de rollback antes de qualquer recuperação.

### Verificador pós-atualização MCP

Arquivo: installer/rag_p9b_postupdate_mcp_tool_probe.py

- Executa um Python filho com -B em cwd temporário, sem ativar MCP.
- Exige codebridge_rag_queue_bootstrap registrada exatamente uma vez.
- Exige execute=false como padrão e os parâmetros de confirmação.
- Usa bootstrap_installed_queue(execute=False): exige apenas diagnóstico
  de leitura BOOTSTRAP_PLAN_ONLY para a geração pública esperada.
- NUNCA chama execute=true, cria jobs ou publica índices.
- Retorno positivo: POSTUPDATE_MCP_TOOL_READONLY_VERIFIED.
- Na instalação atualmente ativa, observou o bloqueio esperado
  MCP_TOOL_SOURCE_NOT_INSTALLED / exit 2.
- O script de pós-atualização será instalado pelo NSIS atualizado.

### Prévia NSIS construída somente do Git

Commit de origem:
6a117afe34a2bb63b11476ece9530002d7244bf8

Caminho:
%LOCALAPPDATA%\CodeBridge-MCP-Bridge\release_staging\P9B_POSTUPDATE_6a117af\CodeBridge-P9B-POSTUPDATE-GUARDED-Preview.exe

SHA-256:
e492b2b9287201a4cdd9b306143868d1ab976a8f1b1ec427875dc3216b891af9

Artefato: 27.282.683 bytes, 264 entradas.
Auditoria do NSIS P9B_NSIS_GIT_PAYLOAD_VERIFIED:
- 7/7 módulos principais iguais aos arquivos do commit.
- Guard temporário NSIS igual ao Git.
- Zero arquivos Python não versionados, rascunho antigo excluído.
- O instalador NÃO foi executado nem disponibilizado em main.

### Snapshot de recuperação correspondente

Caminho:
%LOCALAPPDATA%\CodeBridge-MCP-Bridge\release_staging\P9B_POSTUPDATE_6a117af\FULL_NSIS_PREINSTALL_SNAPSHOT.zip

SHA-256:
daab08743893cd06914e5ea7c2de7cec35a5119342e479476b9d69fb3f77c93c

- 258 destinos no NSIS, 236 arquivos existentes preservados.
- Snapshot verificado contra a identidade SHA do instalador.
- INSTALLED_BASELINE_MATCH, antes e depois.
- ISOLATED_INSTALLER_RESTORE_REHEARSED dos 236 arquivos.
- Escopo de recuperação é baseado em arquivos; não equivale a
  recuperação já comprovada de processos, túnel, registro e atalhos.

### Classificação de rollback somente leitura

Arquivo: installer/rag_p9b_nsis_rollback_classifier.py

- Inspeciona o snapshot, os arquivos do instalador NSIS extraídos em
  pasta temporária e os arquivos da instalação atual.
- Cada destino deve corresponder ao SHA dos bytes originais do snapshot,
  ao SHA aprovado no instalador ou estar ausente quando era novo.
- Mudanças desconhecidas e links simbólicos bloqueiam o candidato.
- Identifica quantos arquivos antigos seriam restaurados e quantos
  arquivos novos seriam removidos; não executa nenhuma ação.
- Retorna rollback_execution_authorized=false e
  real_restore_rehearsed=false em todos os casos.
- Resultado real, com a instalação ainda antiga:
  ROLLBACK_BASELINE_ALREADY_MATCHES, 258 unchanged,
  restore_candidates=0, remove_candidates=0,
  unrecognized_count=0, changes_applied=false.
- CLI:
  python -m installer.rag_p9b_nsis_rollback_classifier
  --snapshot [CAMINHO ZIP]
  --installer [CAMINHO EXE]
  --install-root [INSTALAÇÃO CODEBRIDGE]
  --seven-zip [CAMINHO 7Z]
  (parâmetros acima ilustram o comando; não executá-lo para restaurar,
  pois é apenas inspeção.)

## Testes e commits

- 6 testes iniciais do verificador MCP PASS.
- 20 testes combinados das proteções e do verificador PASS.
- 8 testes iniciais do rollback PASS.
- 28 testes de rollback, pós-atualização e backup PASS.
- 9 testes finais de CLI e classificação PASS.
- 6a117af: registrar verificador de ferramenta MCP pós-instalação.
- a693adc: classificar rollback sem alterar arquivos.
- 4ceea95: disponibilizar CLI de triagem, somente leitura.
- Esta documentação registra a continuidade sem fechar a fase.

## Integridade e próximo passo

- GitHub e branch de desenvolvimento mantidos em sincronia.
- Arquivos preexistentes fora do escopo preservados: benchmark JSON
  modificado, documento antigo de rollback não versionado e
  incremental_installed_queue_init.py não versionado.
- Público: READY, v1_delta_1ae1d01ea84f4e, 211 docs / 8774 chunks.
- Sem journal, fila instalada, worker ou scheduler ligado.

O próximo passo operacional requer desligamento gracioso oficial
da GUI e do MCP, atualização supervisionada independente desta
conexão, validação dos processos e recuperação, reconexão efetiva
do MCP e nova ferramenta em modo somente leitura.

Somente depois deve ser considerado o bootstrap autorizado da fila
e ensaio real de um único job sob lock, fence e lease. Nunca
ativar automaticamente o scheduler ou contornar restrições
anteriores da ferramenta.
