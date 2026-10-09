# HANDOFF — Próxima fase do RAG — Qualidade, Knowledge Management e Interface

Data: 2026-10-08
Projeto: CodeBridge 2.0 — MCP Bridge
Branch de planejamento: rag-017-knowledge-management-plan
Base preservada: 4dcf739 — docs(rag-016-g): hand off qualified RAG architecture
Status: PLANEJAMENTO
Implementação nova executada por este handoff: NÃO

---

# 1. Objetivo

Este handoff abre a próxima etapa do RAG depois do fechamento operacional do RAG-016.

A nova etapa tem dois objetivos:

1. resolver tudo que ainda impede o go-live do RAG;
2. transformar o RAG em um subsistema administrável pelo usuário dentro da interface do CodeBridge.

Visão de produto:

    CodeBridge
    ├── executor MCP
    ├── terminais
    ├── telemetria
    └── RAG
        ├── projetos
        ├── repositórios
        ├── fontes de conhecimento
        ├── arquivos importados
        ├── notas manuais
        ├── auditorias
        ├── índices
        ├── modelos
        ├── pesquisa/teste
        └── auditoria de gerenciamento

O RAG deixa de ser apenas infraestrutura interna e passa a ter uma Central RAG administrável.

# 2. Estado herdado

RAG-001 até RAG-016 foram implementados e qualificados operacionalmente.

Último commit do marco anterior:

    4dcf739 docs(rag-016-g): hand off qualified RAG architecture

Última suíte completa:

    Ran 688 tests
    OK

RAG-016 provou:

- soak;
- restart real;
- CPU-only;
- GPU;
- unload;
- independência do executor MCP;
- falha deliberada dos modelos sem derrubar o executor;
- auditoria Git;
- handoff final.

Porém:

    PRODUCTION READINESS = BLOCKED

Métricas atuais:

    Recall@5  = 0.46
    Recall@10 = 0.48
    MRR       = 0.3257777778

Thresholds congelados:

    Recall@5  >= 0.80
    Recall@10 >= 0.90
    MRR       >= 0.60

Além disso:

    production index != READY

Nenhuma etapa futura pode reduzir os thresholds apenas para produzir PASS.

# 3. Superfície MCP atual do RAG

Ferramentas já existentes:

    codebridge_rag_status
    codebridge_rag_index
    codebridge_search_context
    codebridge_get_context

A superfície já consegue:

- consultar estado;
- planejar indexação;
- solicitar indexação;
- pesquisar contexto;
- recuperar chunks autorizados.

Limitação importante confirmada em author_mcp/rag_bridge.py:

    _RAG_INDEX_EXECUTOR = None
    _RAG_SEARCH_EXECUTOR = None

Os executores são callbacks opcionais.

Enquanto o executor semântico real não estiver registrado, a busca pode cair para fallback lexical.

Enquanto o executor de indexação de produção não estiver registrado e o índice persistente não for construído:

    production index != READY

Isto precisa ser resolvido antes de go-live.

# 4. Formatos atualmente reconhecidos

Documentação atual:

    .md
    .markdown
    .rst
    .adoc
    .txt

TXT possui regras de classificação e não é aceito indiscriminadamente em qualquer lugar.

Código/config atual inclui:

    .c .cc .cpp .h .hpp
    .py .ps1 .bat .cmd .sh
    .js .ts .html .css
    .json .yaml .yml .toml
    .nsi .nsh
    requirements.txt

PDF NÃO possui pipeline RAG próprio implementado atualmente.

Portanto:

    PDF = PENDENTE

Não declarar suporte antes da implementação e dos testes.

# 5. Visão da interface solicitada

Adicionar na interface principal do CodeBridge um botão:

    RAG

Posição desejada:

    abaixo do relógio

A auditoria do frontend confirmou que o relógio atual é self.chatgpt_timer_box em app_rewrite/ui.py.

A região atual contém:

    chatgpt_timer_box
    chatgpt_timer_label
    chatgpt_timer_status

Composição proposta:

    header
    ├── info/status
    └── timer_column
        ├── chatgpt_timer_box
        └── botão RAG

O botão deve ficar visualmente abaixo do relógio sem alterar a estética/dimensões já validadas do timer.

# 6. Central RAG

Ao clicar no botão RAG, abrir uma área dedicada de gerenciamento.

Nome provisório:

    Central RAG

ou:

    RAG Manager

Ela não será apenas uma tela de status.

Ela deverá permitir enxergar, adicionar, alterar, desativar, reindexar e remover aquilo que serve de conhecimento para o RAG.

# 7. Projetos RAG

Cada projeto terá identidade própria.

Exemplos:

    codebridge
    new-world-pvp
    drones

Cada projeto poderá possuir:

- repositório principal;
- zero ou mais diretórios extras de conhecimento;
- arquivos externos referenciados;
- arquivos importados para biblioteca gerenciada;
- notas manuais;
- auditorias;
- handoffs;
- roadmaps;
- patch notes;
- PDFs;
- outros documentos aprovados;
- namespace próprio;
- configuração própria de fontes.

Project isolation continua obrigatório.

Projeto A nunca pode recuperar conteúdo do Projeto B sem ação explícita e autorizada.

# 8. Project Registry

Criar registro persistente de projetos.

Contrato mínimo proposto:

    project_id
    display_name
    repository_root
    enabled
    created_at
    updated_at
    last_indexed_at
    index_state
    notes

repository_root poderá ser alterado pela interface.

Alterar repository_root NÃO significa:

- mover arquivos;
- apagar repositório anterior;
- copiar Git;
- reescrever histórico.

Fluxo de alteração:

1. validar novo caminho;
2. validar boundary;
3. validar existência;
4. registrar alteração;
5. marcar fontes derivadas STALE quando necessário;
6. permitir reindexação explícita;
7. registrar auditoria.

# 9. Knowledge Source Registry

Cada fonte precisa possuir identidade estável.

Contrato mínimo proposto:

    source_id
    project_id
    source_kind
    display_name
    original_path
    managed_path
    content_type
    category
    enabled
    status
    size_bytes
    sha256
    extractor
    created_at
    updated_at
    last_indexed_at
    chunk_count
    page_count
    last_error

Não usar somente path como identidade.

# 10. Tipos de fonte

## REPOSITORY

Repositório principal do projeto.

## DIRECTORY_REFERENCE

Pasta externa autorizada como fonte de conhecimento.

Não copiar a pasta inteira automaticamente.

## FILE_REFERENCE

Arquivo externo utilizado no local original.

Remover do RAG nunca pode apagar este arquivo.

## MANAGED_FILE

Arquivo importado para biblioteca gerenciada pelo CodeBridge.

Exemplos:

- PDF;
- TXT;
- Markdown;
- documento de auditoria.

Somente MANAGED_FILE poderá oferecer uma ação separada para excluir também a cópia gerenciada.

## MANUAL_NOTE

Informação digitada diretamente pelo usuário.

A nota precisa possuir:

- source_id;
- project_id;
- data;
- hash;
- categoria;
- provenance;
- histórico mínimo;
- chunks.

Não criar memória invisível.

## AUDIT_RESULT

Resultado de auditoria ou relatório explicitamente escolhido como conhecimento.

# 11. Categorias de conhecimento

Categorias iniciais propostas:

    DOCUMENTATION
    HANDOFF
    ROADMAP
    PATCH_NOTE
    AUDIT
    REFERENCE
    MANUAL_NOTE
    CODE
    CONFIG
    LOG_SUMMARY
    OTHER_DOCUMENT

A categoria organiza a interface e não substitui SourceType nem as políticas existentes.

# 12. Estados de uma fonte

Estados propostos:

    PENDING
    INDEXING
    READY
    STALE
    DISABLED
    BLOCKED
    ERROR
    REMOVED

PENDING: cadastrada e ainda não indexada.
INDEXING: processamento em andamento.
READY: índice coerente.
STALE: fonte alterada depois da indexação.
DISABLED: cadastrada mas fora das consultas.
BLOCKED: política de segurança impediu indexação.
ERROR: falha técnica.
REMOVED: removida logicamente.

# 13. Estrutura da Central RAG

Estrutura inicial:

    Visão geral
    Projetos
    Conhecimento
    Adicionar
    Índice
    Pesquisa / Teste
    Modelos
    Auditoria

Os nomes podem mudar em mockup, mas as funções não devem desaparecer.

# 14. Visão geral

Mostrar:

    Projeto ativo
    Estado do índice
    Fontes ativas
    Fontes bloqueadas
    Chunks
    Última indexação
    Modelo Text
    Modelo Code
    CPU/GPU
    Recall do último benchmark
    Gate de produção

Deixar explícita a diferença entre:

    QUALIFIED OPERATIONALLY

e:

    PRODUCTION READY

# 15. Aba Projetos

Funções:

- listar projetos;
- adicionar projeto;
- editar display name;
- ativar/desativar;
- alterar repository_root;
- visualizar namespace;
- visualizar última indexação;
- solicitar reindexação;
- excluir índice do projeto;
- remover projeto do registry.

Remover projeto do registry não pode apagar repositório do disco.

# 16. Aba Conhecimento

Mostrar todas as fontes do projeto.

Colunas sugeridas:

    Nome
    Tipo
    Categoria
    Origem
    Status
    Tamanho
    Chunks
    Atualizado
    Última indexação

Filtros:

    status
    tipo
    categoria
    text/code
    stale
    blocked

Ações:

    Abrir detalhes
    Preview
    Reindexar
    Desativar
    Ativar
    Remover do índice
    Remover cadastro
    Excluir cópia gerenciada

A última opção só existe para MANAGED_FILE.

# 17. Aba Adicionar conhecimento

Fluxo:

    escolher projeto
    ↓
    escolher origem
    ↓
    arquivo / pasta / nota manual
    ↓
    categoria
    ↓
    extrair/preview
    ↓
    secret scan
    ↓
    policy validation
    ↓
    mostrar o que será indexado
    ↓
    confirmar
    ↓
    indexar

Selecionar um arquivo não deve iniciar automaticamente trabalho pesado.

# 18. TXT e Markdown

Primeira classe de importação documental:

    .txt
    .md
    .markdown
    .rst
    .adoc

Casos:

- handoffs;
- resultados de auditoria;
- patch notes;
- roadmaps;
- documentação técnica;
- logs resumidos;
- relatórios.

Preservar:

- origem;
- hash;
- data;
- categoria;
- linhas;
- source_id.

# 19. PDF

PDF passa a ser requisito explícito.

Não indexar PDF binário diretamente.

Pipeline esperado:

    PDF original
    ↓
    validação
    ↓
    extractor
    ↓
    texto por página
    ↓
    normalização
    ↓
    chunks
    ↓
    provenance por página
    ↓
    embedding/index

A pesquisa deve poder mostrar algo como:

    manual.pdf — página 18

e não apenas um chunk sem referência humana.

# 20. PDF com texto e PDF escaneado

Primeira implementação proposta:

    PDF com text layer = SUPORTADO
    PDF somente imagem = NEEDS_OCR / BLOCKED

OCR não deve entrar automaticamente na primeira versão.

Motivos:

- custo;
- erros;
- idioma;
- dependências;
- risco de ingestão incorreta;
- provenance mais difícil.

OCR fica como decisão separada.

# 21. Outros formatos

Candidatos posteriores:

    .docx
    .html
    .csv

Não declarar suporte ainda.

A arquitetura deve usar registry de extractors para permitir expansão futura.

# 22. Informação manual

Adicionar ação:

    Nova informação

Campos:

    Projeto
    Título
    Categoria
    Conteúdo
    Tags opcionais

Ao salvar:

1. criar source_id;
2. registrar data;
3. gerar hash;
4. executar secret scan;
5. criar provenance;
6. indexar somente após confirmação.

Editar nota:

- cria nova versão/hash;
- invalida chunks antigos;
- reindexa deterministicamente;
- registra auditoria.

# 23. Auditorias e resultados técnicos

Permitir adicionar como conhecimento arquivos como:

    Auditar execução finalizada.txt
    relatórios RAG
    patch notes
    handoffs
    logs resumidos
    relatórios de validação

Regra preservada:

    RAW do execution ledger continua no ledger

Somente documentos explicitamente escolhidos entram no RAG.

# 24. Três níveis de remoção

## Desativar da pesquisa

Mantém cadastro e arquivo.

Fonte deixa de aparecer em novas consultas.

## Remover do índice

Remove derived data:

- chunks;
- FTS;
- vetores;
- manifest state.

Mantém cadastro e arquivo.

## Remover fonte

Remove cadastro e derived data.

Se FILE_REFERENCE ou DIRECTORY_REFERENCE:

    NUNCA apagar arquivo original

Se MANAGED_FILE:

oferecer ação separada:

    Excluir também a cópia gerenciada

com confirmação explícita.

# 25. Alterar repositório de conhecimento

O usuário pediu explicitamente poder alterar o repositório de sabedoria/informações de cada projeto.

Existirão duas dimensões:

## Repository root

Raiz principal do projeto.

## Knowledge roots

Diretórios extras autorizados.

Cada knowledge root pertence a um project_id.

Não implementar compartilhamento cross-project implícito.

# 26. Managed Knowledge Library

Arquivos importados poderão precisar de biblioteca interna.

Estrutura conceitual:

    CodeBridge local data
    └── rag
        └── knowledge
            └── project_id
                └── source_id
                    ├── original.ext
                    └── metadata

O path físico final ainda precisa ser definido depois de auditar os paths persistentes existentes.

Requisitos:

- ID estável;
- sem overwrite silencioso;
- hash;
- operação segura;
- backup/migração;
- atualização do CodeBridge não pode apagar conhecimento.

# 27. Preview antes de indexar

TXT/Markdown:

- primeiras linhas;
- categoria;
- tamanho;
- hash;
- secret scan.

PDF:

- páginas;
- quantidade de texto;
- amostra;
- páginas sem texto;
- NEEDS_OCR quando aplicável.

Nota manual:

- conteúdo integral antes de confirmar.

# 28. Segurança da ingestão

Toda fonte deve passar por:

    project scope
    path boundary
    denylist
    file type validation
    size validation
    secret scan
    extractor validation
    provenance validation

A UI nunca pode bypassar política existente.

# 29. Secret detection

RAG-015-A permanece obrigatório.

Se detectar conteúdo sensível:

    BLOCKED

A UI pode mostrar:

- tipo da regra;
- linha/página;
- fingerprint seguro.

Nunca revelar raw secret descoberto.

# 30. Limite de arquivo

Ainda precisa ser confirmado.

Requisitos:

- size cap configurável;
- não carregar arquivo gigante na UI thread;
- extractor streaming quando fizer sentido;
- erro claro.

Valor padrão não congelado.

Proposta para benchmark futuro:

    50–100 MiB por documento comum

Não implementar valor sem teste.

# 31. Indexação em background

Extração e indexação não podem congelar a UI.

Estados de job:

    PENDING
    SCANNING
    EXTRACTING
    CHUNKING
    EMBEDDING
    WRITING_INDEX
    READY
    ERROR
    CANCELLED

Cancelamento deve terminar em estado consistente.

# 32. Progress reporting

Cada operação longa deve expor:

    source
    stage
    current
    total
    percent
    elapsed
    last_message

Progresso é telemetria, não authority de consistência.

# 33. Pesquisa / Teste

Tela obrigatória para diagnosticar qualidade.

Entrada:

    Projeto
    Query
    Top K
    Source types
    Path filter opcional
    Debug ON/OFF

Saída:

    rank
    source
    path
    linha/página
    source_type
    route
    lexical rank
    vector rank
    fused rank/score
    stale
    chunk preview

Também mostrar:

    requested_route
    effective_route
    fallback_reason

# 34. Debug de retrieval

Pode mostrar:

- classificação TEXT/CODE/HYBRID;
- query normalizada;
- candidatos;
- scores;
- RRF;
- dedup;
- eligibility.

Nunca mostrar:

- secrets;
- credenciais;
- conteúdo proibido;
- path fora do scope.

# 35. Aba Índice

Mostrar:

    state
    documents
    chunks
    text vectors
    code vectors
    SQLite size
    Qdrant size
    manifest
    last indexed
    stale sources
    blocked sources
    errors

Ações:

    Planejar indexação
    Indexar alterações
    Reindexar projeto
    Rebuild completo
    Remover índice

Rebuild completo exige confirmação.

# 36. Aba Modelos

Mostrar:

    Text model
    Code model
    artifact
    hash
    installed
    backend
    CPU/GPU
    device
    loaded/unloaded
    VRAM/RAM

Ações inicialmente permitidas:

    Carregar
    Descarregar
    Executar canary

Não permitir download silencioso.

Trocar modelo exige novo pin, hash, benchmark, gate e revisão de licença.

# 37. Aba Auditoria

Registrar:

    timestamp
    operation
    project_id
    source_id
    old_state
    new_state
    result
    error_type

Operações relevantes:

- project added;
- repository changed;
- source added;
- source disabled;
- source enabled;
- source reindexed;
- source removed from index;
- managed file deleted;
- full rebuild;
- model canary;
- index failure.

Nunca registrar raw secrets.

# 38. Arquitetura recomendada da UI

Frontend atual:

    PySide6
    app_rewrite/ui.py

Não concentrar todo o RAG Manager dentro de ui.py.

Estrutura conceitual:

    app_rewrite/rag_ui/
        manager_window.py
        overview_page.py
        projects_page.py
        knowledge_page.py
        add_source_page.py
        index_page.py
        search_test_page.py
        models_page.py
        audit_page.py

ou equivalente aprovado.

# 39. Janela separada ou painel

Recomendação inicial:

    botão RAG abaixo do relógio
    ↓
    janela RAG Manager modeless

Motivos:

- terminais continuam utilizáveis;
- espaço para tabelas;
- preview grande;
- jobs longos;
- gerenciamento pode ficar aberto.

Ainda precisa de validação visual por mockup.

# 40. Consistência visual

Reusar:

- dark theme;
- tipografia;
- bordas;
- espaçamento;
- comportamento de botões;
- identidade visual do CodeBridge.

Não criar segundo design system.

# 41. Management Service

A UI não deve manipular SQLite/Qdrant diretamente.

Arquitetura:

    UI
    ↓
    RAG Management Service
    ↓
    registry / extractors / indexer / search

O MCP deve poder utilizar o mesmo service.

# 42. MCP/API parity futura

Ferramentas provisórias:

    codebridge_rag_projects
    codebridge_rag_sources
    codebridge_rag_source_add
    codebridge_rag_source_update
    codebridge_rag_source_disable
    codebridge_rag_source_remove
    codebridge_rag_reindex
    codebridge_rag_preview
    codebridge_rag_audit

Nomes finais somente depois de revisar contratos existentes.

Evitar ferramenta ambígua chamada apenas delete.

Preferir operações explícitas:

    remove_from_index
    unregister_source
    delete_managed_copy
    delete_project_index

# 43. Qualidade continua prioridade

Antes do go-live, RAG-017 precisa analisar as 100 queries congeladas.

Para cada miss registrar:

    query
    route
    expected sources
    lexical top 10
    text-vector top 10
    code-vector top 10
    RRF top 10
    motivo da falha

Categorias propostas:

    QUERY_NORMALIZATION
    LEXICAL_MATCH
    WRONG_ROUTE
    TEXT_EMBEDDING
    CODE_EMBEDDING
    CHUNKING
    GROUND_TRUTH_SPREAD
    RRF_WEIGHTING
    DEDUP
    TOP_K_CUTOFF
    SOURCE_NOT_INDEXED
    STALE_SOURCE
    OTHER

# 44. Anti-overfit

Proibido corrigir query específica do benchmark por ID/texto.

Toda melhoria precisa ser geral.

Depois de tuning:

- rerun das 100 queries;
- regressão;
- novos casos;
- segurança.

# 45. Production index READY

Depois de qualidade suficiente:

1. registrar executor de indexação real;
2. registrar semantic search executor real;
3. construir índice persistente;
4. reiniciar CodeBridge;
5. recuperar índice;
6. status precisa retornar READY;
7. busca MCP precisa usar rota semântica real;
8. não depender do harness de benchmark.

# 46. Licença comercial

Ainda pendente.

Policies atuais registram:

    CC-BY-NC-4.0
    commercial_license_review_required = true

Antes de distribuição comercial:

- revisar licença;
- obter permissão compatível; ou
- substituir modelo.

Mudança de modelo exige novo pin, SHA-256, benchmark, canary e gate.

# 47. Instalador e atualização

Validar:

- RAG Manager;
- extractors;
- SQLite;
- Qdrant;
- llama.cpp sidecar;
- modelos conforme política;
- knowledge library.

Atualizar CodeBridge não pode apagar:

    project registry
    source registry
    knowledge library
    indexes
    audit trail

Migração precisa ser versionada.

# 48. Máquina fisicamente sem GPU

RAG-016-C provou CPU-only com offload desativado.

O host físico possui NVIDIA.

Ainda falta:

    canary em máquina realmente sem GPU dedicada

Obrigatório para distribuição geral se CPU-only fizer parte da promessa de compatibilidade.

# 49. Watch automático

Ainda não congelado.

Recomendação da primeira versão:

    scan/status + reindexação explícita

Watcher pode ser avaliado depois.

# 50. Backup/export

Ainda pendente.

Recomendação futura:

exportar:

- project registry;
- source registry;
- manual notes;
- managed files;
- audit metadata.

Índices podem ser reconstruídos e não precisam obrigatoriamente entrar no backup.

# 51. Decisões já congeladas

1. haverá botão RAG abaixo do relógio;
2. haverá Central RAG;
3. conhecimento será separado por projeto;
4. repository_root poderá ser alterado;
5. será possível adicionar arquivos;
6. TXT e Markdown são prioridade;
7. PDF entra no roadmap;
8. será possível adicionar informação manual;
9. auditorias/handoffs/patch notes poderão virar conhecimento;
10. será possível desativar conhecimento;
11. será possível remover do índice;
12. remover do índice não apaga original;
13. managed copy terá exclusão física separada;
14. project isolation continua obrigatório;
15. secret scan continua obrigatório;
16. provenance continua obrigatório;
17. UI não manipula SQLite/Qdrant diretamente;
18. modelos continuam opcionais para o executor MCP;
19. thresholds não serão reduzidos;
20. go-live continua bloqueado até o gate passar.

# 52. Decisões ainda pendentes

UX:

- nome final Central RAG ou RAG Manager;
- janela modeless ou painel;
- tamanho inicial;
- ícone;
- layout final.

Storage:

- path físico da knowledge library;
- registry em SQLite único ou banco separado;
- backup/export.

Importação:

- tamanho máximo;
- DOCX na primeira versão ou depois;
- HTML;
- CSV;
- OCR;
- drag-and-drop múltiplo;
- importação de pasta completa.

Atualização:

- reindex manual;
- watcher;
- frequência de stale scan.

Notas:

- histórico completo de versões;
- tags;
- autoria local.

Exclusão:

- confirmações para delete managed copy;
- lixeira interna ou remoção imediata.

Distribuição:

- licença dos modelos;
- llama.cpp no installer;
- distribuição dos GGUFs.

# 53. Roadmap normativo

## RAG-017 — Recuperar qualidade e fechar blockers

Dependência: RAG-016 concluído.

RAG-017-A — Diagnóstico das 100 queries
- gerar failure matrix;
- não mudar algoritmo ainda.

RAG-017-B — Query normalization e lexical recall
- melhorias gerais;
- medir delta.

RAG-017-C — Rotas TEXT/CODE/HYBRID
- auditar classificador;
- corrigir erros gerais.

RAG-017-D — Vector retrieval e chunking
- investigar expected source fora de top-k;
- revisar representação/chunking se necessário.

RAG-017-E — Fusion/ranking/dedup
- revisar RRF e top-k intermediário.

RAG-017-F — Anti-overfit/regressão
- dataset completo;
- testes adicionais.

RAG-017-G — Production executors
- registrar index executor;
- registrar semantic search executor.

RAG-017-H — Índice persistente READY
- build real;
- restart;
- recovery;
- status READY.

RAG-017-I — Gate
- Recall@5;
- Recall@10;
- MRR;
- cold;
- warm;
- RAM;
- VRAM;
- index size;
- thresholds inalterados.

RAG-017-J — Fechamento
- testes;
- auditoria;
- commit;
- push;
- handoff/patch note.

## RAG-018 — Project Registry e Knowledge Repository

RAG-018-A — Contrato de projeto
RAG-018-B — Contrato de source
RAG-018-C — Persistence
RAG-018-D — Repository root management
RAG-018-E — Knowledge roots
RAG-018-F — Managed knowledge storage
RAG-018-G — Source lifecycle
RAG-018-H — Restart/recovery
RAG-018-I — Auditoria Git e fechamento

## RAG-019 — Ingestão de documentos e informações

RAG-019-A — Extractor contract
RAG-019-B — TXT/Markdown/RST/AsciiDoc
RAG-019-C — PDF text layer
RAG-019-D — PDF provenance por página
RAG-019-E — PDF sem texto / NEEDS_OCR
RAG-019-F — Manual notes
RAG-019-G — Auditorias e handoffs
RAG-019-H — Preview
RAG-019-I — Segurança de ingestão
RAG-019-J — Fechamento

## RAG-020 — Knowledge Management Service

RAG-020-A — List/get project sources
RAG-020-B — Add/register source
RAG-020-C — Update metadata
RAG-020-D — Enable/disable
RAG-020-E — Reindex source
RAG-020-F — Remove from index
RAG-020-G — Unregister source
RAG-020-H — Delete managed copy
RAG-020-I — Rebuild project index
RAG-020-J — Progress/jobs
RAG-020-K — Audit trail
RAG-020-L — MCP/API parity
RAG-020-M — Fechamento

## RAG-021 — Interface RAG do CodeBridge

RAG-021-A — Mockup e posição do botão
RAG-021-B — Shell da Central RAG
RAG-021-C — Visão geral
RAG-021-D — Projetos
RAG-021-E — Conhecimento
RAG-021-F — Adicionar informação
RAG-021-G — Preview e confirmação
RAG-021-H — Índice
RAG-021-I — Pesquisa/Teste
RAG-021-J — Modelos
RAG-021-K — Auditoria
RAG-021-L — Jobs/progress/cancel
RAG-021-M — UX/error handling
RAG-021-N — Fechamento

## RAG-022 — Segurança da Central RAG

RAG-022-A — Cross-project negative tests
RAG-022-B — Traversal/UI import
RAG-022-C — Secrets em upload
RAG-022-D — PDF malformado
RAG-022-E — File size/type bypass
RAG-022-F — Delete semantics
RAG-022-G — Managed deletion
RAG-022-H — Audit integrity
RAG-022-I — Full negative suite
RAG-022-J — Fechamento

## RAG-023 — Instalador, persistência e migração

RAG-023-A — Fresh install
RAG-023-B — Update existente
RAG-023-C — Restart
RAG-023-D — Sidecar llama.cpp
RAG-023-E — Model artifacts
RAG-023-F — CPU machine canary
RAG-023-G — Rollback
RAG-023-H — Fechamento

## RAG-024 — Gate final e decisão de go-live

RAG-024-A — Benchmark 100 queries
RAG-024-B — Production index READY
RAG-024-C — Security rerun
RAG-024-D — UI end-to-end
RAG-024-E — Performance/resources
RAG-024-F — License review
RAG-024-G — Git audit
RAG-024-H — Handoff final

Resultado permitido:

    GO-LIVE APPROVED

ou:

    GO-LIVE BLOCKED

# 54. Política de fechamento

Nenhuma fase é concluída somente porque funcionou uma vez.

Antes de marcar qualquer etapa concluída:

1. auditar Git;
2. revisar diff;
3. testes focados;
4. suíte RAG relevante;
5. git diff --check;
6. documentar;
7. commit;
8. push;
9. auditoria pós-commit;
10. working tree limpo;
11. branch sincronizada.

Alteração de código exige patch note conforme política do projeto.

# 55. Dividir para conquistar

Se uma subfase ficar grande, dividir antes de codar.

Exemplo:

    RAG-019-C-A
    RAG-019-C-B
    RAG-019-C-C

Não empurrar uma implementação enorme em um único patch.

# 56. Testes manuais

A UI exigirá checkpoints humanos.

Exemplos:

- validar posição do botão;
- conferir mockup;
- selecionar arquivo real;
- conferir preview PDF;
- drag-and-drop;
- remoção;
- restart;
- installer em outra máquina.

Quando precisar ação manual, usar o mecanismo visual de aviso do CodeBridge já adotado no projeto.

# 57. Casos de aceitação finais

Caso 1 — alterar repository_root
- validar novo root;
- não apagar root anterior;
- marcar stale;
- reindexar;
- recuperar READY.

Caso 2 — adicionar TXT
- preview;
- secret scan;
- confirmar;
- indexar;
- recuperar por pesquisa.

Caso 3 — Markdown de auditoria
- categoria AUDIT;
- provenance preservada.

Caso 4 — PDF
- extrair páginas;
- preview;
- indexar;
- resultado aponta página.

Caso 5 — PDF escaneado
- não inventar texto;
- marcar NEEDS_OCR/BLOCKED.

Caso 6 — nota manual
- criar;
- indexar;
- editar;
- hash muda;
- chunks antigos deixam de ser usados.

Caso 7 — desativar
- para de aparecer;
- arquivo permanece.

Caso 8 — remover do índice
- derived data removido;
- fonte/arquivo permanecem.

Caso 9 — managed copy
- remover do índice não apaga cópia;
- somente ação separada pode apagar cópia.

Caso 10 — arquivo externo
- nenhuma ação RAG apaga original.

Caso 11 — projetos A/B
- nunca misturar resultados.

Caso 12 — restart
- projetos/fontes/configuração persistem.

# 58. Itens proibidos automaticamente

- apagar repositório;
- apagar arquivo original;
- mover Git repository;
- baixar modelo sem consentimento;
- trocar modelo sem benchmark;
- OCR automático;
- indexar formato desconhecido;
- indexar secret;
- compartilhar conhecimento entre projetos;
- reduzir threshold;
- colocar modelo no bootstrap obrigatório do executor;
- ativar watcher agressivo sem decisão explícita.

# 59. Ordem recomendada

    RAG-017 qualidade/gate
    ↓
    RAG-018 registry/repository
    ↓
    RAG-019 ingestão
    ↓
    RAG-020 management service
    ↓
    RAG-021 UI
    ↓
    RAG-022 segurança
    ↓
    RAG-023 installer/persistência
    ↓
    RAG-024 gate final

A interface deve sentar sobre contratos estáveis.

Não colocar lógica de negócio diretamente nos widgets.

# 60. Estado ao finalizar este handoff

Nenhuma feature foi implementada por este documento.

Nenhum botão RAG foi criado.

Nenhum extractor PDF foi instalado.

Nenhum repository root foi alterado.

Nenhum índice foi reconstruído.

Nenhum threshold foi alterado.

Este documento apenas congela:

- visão;
- riscos;
- pendências;
- arquitetura alvo;
- roadmap;
- critérios de aceitação.

# 61. Primeiro passo quando execução for autorizada

Começar por:

    RAG-017-A — Diagnóstico das 100 queries

Antes de alterar retrieval.

A Central RAG começa estruturalmente em:

    RAG-018

e visualmente em:

    RAG-021

# 62. Checkpoint de continuidade

Base técnica:

    4dcf739

Branch de planejamento:

    rag-017-knowledge-management-plan

Documento:

    docs/HANDOFF_RAG_017_024_KNOWLEDGE_MANAGEMENT_UI_2026-10-08.md

Próxima instrução esperada depois da revisão:

    Iniciar RAG-017-A

ou solicitar ajuste do handoff antes de codar.
