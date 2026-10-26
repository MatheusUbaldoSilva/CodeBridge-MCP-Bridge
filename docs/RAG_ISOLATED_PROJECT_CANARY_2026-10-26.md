# RAG multiprojeto — integração isolada e ativação controlada

**Data:** 2026-10-26
**Status:** canário local de leitura ATIVO; migração da geração pública NÃO EXECUTADA
**Projeto:** `codebrige-mcp-rag`
**Código indexado:** snapshot DEV `f3242e53f6bf6b7c67bd58f4017538fe3205dc39`

## Escopo integrado

O MCP e a aba "Meus conhecimentos" podem consultar um projeto explicitamente registrado em arquivo local sem trocar a geração pública do RAG `codebridge`.

- `rag/runtime/isolated_project_index.py`: resolução de projeto por configuração local com paths restritos à pasta `CodeBridge-RAG-Workspace`, fingerprint SHA256 do SQLite e do manifesto, check de revisão, progresso e registro habilitado.
- `rag/runtime/isolated_project_search.py`: busca lexical isolada, subprocesso semântico e recuperação de trechos vinculados ao snapshot original. Nega contexto se a fonte mudou ou não pôde ser comprovada.
- `rag/runtime/isolated_project_worker.py`: roda o Jina via Python autorizado e consulta o SQLite/Qdrant explicitamente selecionado, sem publicar nada.
- `author_mcp/rag_bridge.py`: roteamento por `project_id` sem alterar o caso especial `codebridge` nem seu lock/pointer.
- `author_mcp/mcp_server.py`: exposição de `isolated_project_indexes` na ferramenta `codebridge_rag_status`.
- `app_rewrite/rag_panel.py`: a aba de arquivos consulta o SQLite do projeto selecionado e o total de documentos inclui os projetos isolados.

Não há rota para escrita, publicação ou troca de geração nessas APIs do projeto canário. A inclusão incremental continua sujeita às barreiras existentes. O canário é **somente leitura via aplicativo**, não uma imutabilidade de ACL do filesystem.

## Índice candidato e configuração

Fonte original de indexação (preservada):
`C:\Users\Matheus\CodeBridge-RAG-Workspace\codebrige-mcp-rag\staging\full-dev-f3242e5-work`

Cópia independente para leitura:
`C:\Users\Matheus\CodeBridge-RAG-Workspace\codebrige-mcp-rag\generations\codebrige-mcp-rag-f3242e5`

Os 7 arquivos da cópia foram comparados contra o staging por SHA256. A consulta usa apenas o candidato. SQLite, manifesto e progresso são verificados antes de liberar o projeto.

Registro de canário (fora do Git):
`%LOCALAPPDATA%\CodeBridge\rag\project-indexes.json`

O registro contém `enabled=true` somente para `codebrige-mcp-rag`, com paths e revisão explícitos. A geração pública permaneceu **`v1_delta_1ae1d01ea84f4e`**, em estado READY. O índice antigo `codebridge` não foi substituído.

Contagens do candidato auditado:
- 971 documentos
- 11.385 chunks SQLite + FTS5
- 173 vetores TEXT (1024 dimensões)
- 11.212 vetores CODE (1536 dimensões)
- 100% dos 11.385 vetores cruzados com SQLite na auditoria final

## Testes e evidências

- 40 testes de regressão aprovados em 7 suítes: integração, segurança, status público, pesquisa MCP, contexto MCP, contexto interno e interface Qt.
- MCP público em subprocesso: `codebridge_rag_status` mostrou o canário isolado; `codebridge_search_context` localizou arquivos; `codebridge_get_context` recuperou o conteúdo.
- Busca semântica CODE real com Jina e subsequente `get_context` pelo MCP: PASS, três resultados, com fontes FRESH.
- Aba Qt: 971 arquivos no novo projeto; listagem do `codebridge` antigo continua independente.
- Correção específica de proveniência CRLF: comparação de SHA do arquivo a partir de bytes UTF-8 decodificados, igual à indexação; um `README.md` com CRLF deixou de ser classificado falsamente como STALE. Alterações reais continuam causando STALE e bloqueiam `get_context`.
- Recuperação do canário: DISABLE -> ENABLE testados, mantendo inalterado o pointer `active-generation.json`.
- Verificação de que nenhum modelo Jina permaneceu carregado depois dos testes.

## Reversão imediata do canário

Script local (fora do Git e independente do MCP):
`C:\Users\Matheus\CodeBridge-RAG-Workspace\codebrige-mcp-rag\control_readonly_canary.ps1`

Consultar estado:
```powershell
& 'C:\Users\Matheus\CodeBridge-RAG-Workspace\codebrige-mcp-rag\control_readonly_canary.ps1' -Action Status
```

Desativar somente o novo projeto, mantendo o RAG antigo:
```powershell
& 'C:\Users\Matheus\CodeBridge-RAG-Workspace\codebrige-mcp-rag\control_readonly_canary.ps1' -Action Disable -Confirmation 'CODEBRIDGE_RAG_READONLY_DISABLE:codebrige-mcp-rag'
```

Reativar após nova verificação dos hashes e do ponteiro público:
```powershell
& 'C:\Users\Matheus\CodeBridge-RAG-Workspace\codebrige-mcp-rag\control_readonly_canary.ps1' -Action Enable -Confirmation 'CODEBRIDGE_RAG_READONLY_ENABLE:codebrige-mcp-rag'
```

O script troca somente o registro local, com backup e atualização atômica. Não escreve SQLite, Qdrant, Git nem o ponteiro público.

Backups da configuração inicial estão no mesmo diretório do registro, com nomes `project-indexes.pre-canary-2026-10-26.json` e `project-indexes.atomic-before-canary-2026-10-26.json`; os testes de disable/enable também gravaram backups individuais.

## Limites e futura ativação pública

**Este marco NÃO substituiu o RAG público.** O projeto canário está disponível sob seu próprio identificador `codebrige-mcp-rag`.

A versão `codebridge` pública está em uma geração versionada já ativa. A função antiga `publish_staged_index` recusa sobrescrever dados existentes, e `production_generation_transition.publish_validated_generation` suporta especificamente migração legacy -> candidato, não uma troca arbitrária a partir da geração pública já versionada.

Para uma substituição pública futura, exigir aprovação específica e:
1. Definir política de IDs: coexistência `codebridge` e `codebrige-mcp-rag` versus migração de projeto, sem renomear índices às cegas.
2. Preparar nova transação de geração compatível com o ponteiro atual e preservar cópia verificável de `v1_delta_1ae1d01ea84f4e`.
3. Congelar leitores/processos sob lock, inspecionar versão e hashes de origem, ensaiar recuperação após interrupção e verificar consultas reais nos dois sentidos.
4. Auditar rollback dos dados separadamente do rollback do código e provar que o launcher stable lê sua geração compatível.
5. Confirmar autorização expressa vinculada à geração e revalidar imediatamente antes de qualquer alteração no apontador público.

O snapshot indexado é do commit `f3242e5`. Os commits de integração posteriores não fazem parte desse índice congelado, o que é intencional; atualizar o conhecimento para commits mais novos requer indexação nova com validação.

Mudanças locais deste marco pertencem à branch **DEV local**, sem push para `stable`. Não remover as três pendências preexistentes no working tree.

## Observação operacional

O launcher isolado pode permanecer aberto com código já carregado. Se a aplicação GUI/MCP estiver carregando módulos Python antigos, fechar e reabrir normalmente o CodeBridge DEV para carregar a integração nova. A ativação do registro em disco não garante hot-reload do processo.
