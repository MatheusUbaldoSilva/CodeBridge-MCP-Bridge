# RAG-DEL-01.04-DK — Handoff para integracao segura da GUI (DEV)

## Auditoria somente leitura

No diff local preexistente de app_rewrite/rag_panel.py (30 adicoes e 3 remocoes), a interface de adicao de conhecimento ganhou o botao Adicionar ao conhecimento e ocultou controles internos de preview. A operacao documents em linhas proximas de 84-103 nao esta alterada no diff, mas faz leitura direta do banco publico com resolve_rag_sqlite_path().

O novo backend read_pinned_public_document_inventory() de DJ resolve a geracao publicada com production_generation_read(), seleciona apenas codebridge e retorna um dicionario com documents, generation, read_only e activation_authorized=False.

## Integracao planejada (NAO executada)

1. Revalidar e preservar os cinco arquivos sujos preexistentes; o patch da GUI deve ser criado em cima do seu estado atual, nao via checkout/reset.
2. No ramo is_public da operacao documents, chamar read_pinned_public_document_inventory(project_id="codebridge") e retornar exclusivamente o vetor documents. Manter o formato atual usado em RagPanel._complete: list[dict] com path/count/type, sem alterar callbacks, o botao de adicao ou a selecao.
3. No ramo privado, nao usar o helper publico. A integridade e a concorrencia do catalogo isolado precisam de mecanismo proprio antes de exclusao real.
4. Acrescentar testes: SQL no versionado publico, projeto privado nao vaza, busy generation devolve erro controlado sem deixar GUI bloqueada, falha de leitura nao limpa a lista indevidamente, nenhum index/worker ativado.
5. Fazer smoke em DEV instalado e verificar que o processo carregou a nova implementacao; manter Stable intocada ate autorizacao expressa.
6. Auditar git diff por arquivo e fazer commit seletivo sem incluir as modificacoes anteriores do usuario.

## Limites

Esta etapa foi apenas auditoria e documentacao. Nenhuma linha em app_rewrite/rag_panel.py ou app_rewrite/main.py foi mudada nesta retomada. A nova API nao autoriza delecao, publicacao ou promocao de geracao. O MCP publico ja usa production_generation_read nas rotas principais de search/get-context; o processo MCP instalado ainda nao foi atestado nesta sessao.