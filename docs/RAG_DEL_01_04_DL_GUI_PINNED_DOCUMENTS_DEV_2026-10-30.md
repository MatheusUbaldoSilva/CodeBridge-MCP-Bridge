# RAG-DEL-01.04-DL - GUI Documents com pin de geração (DEV)

## Integração seletiva

O ramo documents de app_rewrite/rag_panel.py para o projeto público codebridge agora delega a listagem para rag.runtime.knowledge_deletion_public_inventory_read.read_pinned_public_document_inventory(), criado na fase DJ. Ele retorna somente a lista documents (list[dict] com path/count/type), exatamente como a tela _complete("documents", ...) já consome.

O helper mantém production_generation_read() durante a consulta SQLite mode=ro e PRAGMA query_only=ON, usando geração versionada estável e rejeitando journal de cutover pendente. Em um lock exclusivo concorrente, a operação falha fechada; não volta silenciosamente ao SQLite legado. A listagem de projeto privado segue o caminho anterior e não lê o índice público.

## Proteção de alterações preexistentes do usuário

No início da fase, app_rewrite/rag_panel.py já tinha alterações não commitadas no assistente de adição de conhecimento (botão simplificado e controles ocultos). Essas alterações foram preservadas integralmente no arquivo de trabalho, sem reset/checkout.

O commit parcial para rag_panel.py foi preparado diretamente a partir do blob HEAD anterior com SOMENTE 8 linhas novas na operação documents. A diferença preexistente no restante do arquivo ficou intencionalmente unstaged e não será incluída no commit. Nenhum outro arquivo preexistente sujo foi preparado.

## Testes

Testes em test_rag_del_01_04_dl_gui_pinned_documents.py cobrem:
- retorno público no formato esperado, sem resolver o SQLite legado;
- bloqueio por ProductionGenerationBusy sem fallback;
- projeto privado isolado e projeto privado ausente sem vazamento;
- tela Qt conserva o formato e botão de revisão/exclusão pública desabilitado;
- prova ponta a ponta com o helper real, SQLite versionado sintético, projeto privado sentinela e lock Win32 temporário.

O test_rag_panel_smoke.py esperava incorretamente três páginas. A base de código HEAD anterior a DL já possuía quatro páginas (a quarta é Indexação automática). Corrigido apenas o teste, sem modificar a quantidade de páginas ou os nomes da GUI.

## Limitações

Somente o código DEV local foi alterado, não a instalação Stable. O novo ramo não implementa exclusão de conhecimento e nunca aprova ativação. O lado privado ainda precisa de uma revisão de locking/catálogo própria; testes MCP carregados no processo instalado permanecem pendentes. Não houve escrita ou exclusão no índice de produção nem push ao GitHub.