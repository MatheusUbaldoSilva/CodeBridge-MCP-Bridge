# RAG V1.03 — P9-B: instalador de prévia criado só com objetos Git

Data: 2026-10-22
Branch: rag-017-optimized-inference-after-candidate
Status: INSTALADOR OFFLINE VALIDADO; NÃO EXECUTADO / NÃO IMPLANTADO.

## Causa real e correção

A primeira compilação NSIS feita a partir do checkout Windows incluiu
um script Python não versionado:
rag/runtime/incremental_installed_queue_init.py.

O script é rascunho preexistente do operador e NÃO faz parte do contrato
aprovado. O instalador original de prévia portanto foi invalidado
e removido, sem alterar o rascunho.

Foi criado o pipeline installer/rag_p9b_clean_release.py:
- Usa git archive de um hash HEAD resolvido e comprovado.
- Exporta para diretório temporário independente, sem ler alterações
  não commitadas na pasta de desenvolvimento.
- Copia somente dois executáveis previamente selecionados,
  tunnel-client.exe e cloudflared.exe, do payload local aprovado.
- Compila NSIS exclusivamente sobre essa árvore limpa.
- Recusa inserir arquivos Python que não apareçam no ls-tree do commit.
- Confere a presença dos sete módulos críticos do bootstrap.
- Gera binário em diretório de release separado da instalação.
- Nunca executa o instalador, não reinicia MCP, não cria jobs nem altera RAG.

Em complemento, installer/rag_p9b_clean_release_audit.py:
- Abre o pacote NSIS com 7-Zip em modo offline.
- Rejeita arquivos Python não rastreados, inclusive o rascunho citado.
- Extrai somente os sete módulos e confere com git show do commit.
- Aceita apenas normalização de CRLF -> LF para equivalência do Git.
- Registra SHA-256 do executável e o hash exato do commit.

## Evidências reais

Git de origem usado no instalador:
f42b72750e06765fe061147b03826ca77e9ac324

Artefato construído, não instalado:
%LOCALAPPDATA%\CodeBridge-MCP-Bridge\release_staging\P9B_GIT_f42b727\CodeBridge-P9B-CLEAN-Preview.exe

SHA-256:
3e6b220d8571abad42a8f9cc148468fc69d535a6271d51b7c4078fc0e09a4667

Tamanho: 27.264.953 bytes.
NSIS compila: PASS.
Auditoria do pacote:
P9B_NSIS_GIT_PAYLOAD_VERIFIED.
Entradas: 261.
Módulos do bootstrap comparados ao Git: 7/7.
Arquivos Python não versionados no pacote: zero.
Rascunho incremental_installed_queue_init.py presente: NÃO.
Testes unitários do exportador + auditor: 6 PASS.
Outros testes do instalador/NSIS anteriores: 4 PASS.

O pacote reversível de sete arquivos criado anteriormente permanece:
%LOCALAPPDATA%\CodeBridge-MCP-Bridge\release_staging\P9B_16fecab\MCP_P9B_REVERTIBLE.zip
SHA-256:
417a7282746c0e3f5055f37c1f6eef0bdbe7287705c87631fd28f7877531b9b7

## Regras para execução futura

1. Não executar esta prévia como atualização automática ainda: é um
   artefato de VALIDAÇÃO OFFLINE, não uma versão publicada em main.
2. Demonstrar antes um caminho oficial de reinício e recuperação da
   sessão MCP ativa (a inspeção do gerenciamento foi bloqueada antes).
3. Confirmar que a instalação não mudou e revalidar backup/manifesto.
4. Se autorizado, executar atualização por rotina oficial, com restauração
   byte-exata e recuperação da conexão como pré-condição.
5. Exigir nova ferramenta codebridge_rag_queue_bootstrap no MCP conectado,
   primeiro em execute=false. Não iniciar automaticamente fila, worker
   ou publicação.
6. Só então ensaiar uma inicialização real da fila autorizada, com
   lock, fence, lease e revisão de cada job.

## Integridade do ambiente

Índice público esperado v1_delta_1ae1d01ea84f4e:
211 documentos, 8774 chunks, READY; não foi modificado.
Servidor MCP existente permanece ativo. Sem journal e sem queue real.
Continuam intocados:
benchmarks/rag017_code_only_extended_smoke.json (modified),
docs/RAG_017_J_VM_ROLLBACK_RUNBOOK_2026-10-10.md (untracked),
rag/runtime/incremental_installed_queue_init.py (untracked).

## Commits desta janela

f42b727: exportação Git para prévia NSIS limpa.
d9d69ac: auditoria reproduzível de conteúdo do executável.
Registro documental no commit seguinte.

P9-B permanece EM ANDAMENTO. Nenhuma alegação de produção ativa.
