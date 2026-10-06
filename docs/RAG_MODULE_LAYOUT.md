# Layout de módulos RAG — CodeBridge 2.0

## Estado

Marco: RAG-001-B  
Status: LAYOUT CONGELADO  
Dependência: RAG-001-A  
Escopo: definição estrutural somente

Este marco define os módulos internos da nova camada RAG

Nenhuma inferência embedding indexação banco vetorial tool MCP ou integração com executor é implementada aqui

## Layout aprovado

```text
rag/
├── config.py
├── models/
├── index/
├── chunking/
├── retrieval/
├── ranking/
├── sources/
└── runtime/
```

## Responsabilidade de cada módulo

### rag/config.py

Responsável somente por configuração própria da camada RAG

Deverá concentrar no futuro parâmetros como

- raízes autorizadas
- projetos habilitados
- exclusões
- limites de busca
- timeout de idle de modelos
- seleção de backend
- caminhos de índices
- flags de recursos RAG

Não deve conter

- credenciais
- execução de shell
- decisão de status de execução
- carregamento automático de modelo durante import
- inicialização silenciosa de indexação

### rag/models/

Responsável pelo lifecycle e adaptação dos modelos usados pelo RAG

Escopo futuro

- Jina v5 Text Small
- Jina Code 1.5B
- backend CPU
- backend GPU quando disponível
- load unload idle
- identificação de versão e hash

Não deve

- possuir autoridade sobre executor
- decidir SUCCESS FAILED ou exit code
- baixar modelo silenciosamente
- manter ambos os modelos pesados residentes por padrão no CodeBridge 2.0

### rag/index/

Responsável pelo armazenamento e estado dos índices

Escopo futuro

- SQLite dedicado
- FTS5
- índice vetorial
- manifest incremental
- IDs determinísticos
- metadados de proveniência
- staleness
- namespaces de projeto

Não é fonte da verdade

Qualquer dado indexado deve continuar verificável na fonte real

### rag/chunking/

Responsável por transformar fontes autorizadas em chunks rastreáveis

Escopo futuro

- Markdown
- TXT e logs
- código por linguagem
- fallback textual controlado
- overlap
- linhas exatas
- símbolos
- proveniência

Não deve acessar shell nem alterar arquivos de origem

### rag/retrieval/

Responsável por executar recuperação sobre índices já disponíveis

Escopo futuro

- busca lexical
- busca vetorial textual
- busca vetorial de código
- consulta híbrida
- filtros de projeto path branch e source type
- top k

Deve devolver referências suficientes para verificação da fonte real

### rag/ranking/

Responsável por ordenar e fundir candidatos recuperados

Escopo futuro

- ranking lexical
- fusão determinística
- Reciprocal Rank Fusion
- deduplicação
- score final de retrieval

Ranking não transforma resultado em verdade oficial

### rag/sources/

Responsável por descobrir e ler somente fontes autorizadas

Escopo futuro

- documentação
- código
- Git
- auditorias
- patch notes
- handoffs
- roadmaps
- metadados aprovados do ledger

Também é responsável por aplicar

- allowlist de raízes
- denylist
- proteção contra path traversal
- exclusão de secrets e credenciais
- identificação da proveniência da fonte

Não executa comandos para modificar fontes

### rag/runtime/

Responsável pela orquestração interna da camada RAG

Escopo futuro

- classificar consulta como TEXT CODE HYBRID ou LEXICAL_ONLY
- coordenar source retrieval chunking index e ranking
- coordenar model lifecycle
- tratar falhas da camada RAG
- manter FTS5 disponível quando modelos falharem quando tecnicamente possível

Não deve assumir nem controlar o lifecycle do executor MCP

## Direção de dependência

A direção arquitetural pretendida é

```text
MCP RAG tools
    ↓
rag/runtime
    ├── rag/config
    ├── rag/sources
    ├── rag/retrieval
    │      ├── rag/index
    │      └── rag/models
    ├── rag/ranking
    └── rag/chunking
```

As dependências finais de implementação ainda serão confirmadas durante os próximos marcos

Este diagrama congela responsabilidade e separação mas não obriga imports específicos antes da auditoria do código real

## Fronteira com o MCP autoral

A camada RAG ficará abaixo das futuras tools RAG do MCP

As tools de execução atuais continuam independentes

```text
author_mcp
├── tools de execução existentes
│   └── executor atual
└── futuras tools RAG
    └── rag/runtime
```

Não criar dependência inversa do executor para rag/

O executor não pode precisar importar o RAG para iniciar ou executar comandos

## Fronteira com app_rewrite

app_rewrite continua responsável pelo runtime local terminal execução ledger e demais funções atuais

rag/ não deve ser colocado dentro do caminho crítico de inicialização do terminal

Integrações futuras devem usar fronteiras explícitas e falha segura

## Fronteira com dados

O layout separa responsabilidades para evitar um módulo monolítico

```text
sources
  descobre e lê

chunking
  transforma em unidades rastreáveis

models
  gera representações quando solicitado

index
  persiste índices

retrieval
  recupera candidatos

ranking
  ordena e funde

runtime
  orquestra
```

## Regras de importação e efeitos colaterais

Quando os módulos forem criados em código

- import de rag não deve carregar modelo
- import de rag não deve abrir GPU
- import de rag não deve baixar arquivo
- import de rag não deve iniciar indexação
- import de rag não deve abrir servidor
- import de rag não deve alterar banco
- import de rag não deve executar shell
- efeitos pesados devem ocorrer somente por chamadas explícitas do runtime RAG

## Decisões propositalmente adiadas

RAG-001-B não congela

- classes e dataclasses
- schemas de dados
- assinaturas de funções
- backend de inferência
- biblioteca de embeddings
- formato SQLite
- escolha do vetor store
- algoritmo definitivo de chunking
- thresholds
- top k padrão
- política de cache
- tools MCP públicas

Esses itens pertencem ao RAG-001-C e marcos posteriores

## Critério de aceitação

RAG-001-B está concluído quando

- o layout de módulos está documentado
- cada módulo possui uma responsabilidade única clara
- a fronteira RAG versus executor permanece preservada
- nenhum modelo ou backend foi implementado
- nenhum índice foi criado
- nenhuma tool MCP RAG foi criada
- nenhum caminho crítico atual do CodeBridge foi alterado
