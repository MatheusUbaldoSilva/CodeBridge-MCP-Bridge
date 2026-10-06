# HANDOFF — CodeBridge 2.0 — RAG Local com Jina v5 Text Small + Jina Code 1.5B

Data: 2026-10-06
Projeto: CodeBridge 2.0 — MCP Bridge
Estado inicial: PLANEJADO
Dependência: MCP-PROD-006 concluído
Estratégia: dividir para conquistar

---

## 1. Objetivo

Adicionar ao CodeBridge 2.0 uma camada RAG local capaz de recuperar contexto técnico de projetos antes da execução de comandos.

A camada RAG deverá funcionar como mecanismo de descoberta e contextualização. Ela não substitui:

- o executor MCP;
- o ledger de execuções;
- os arquivos reais;
- o Git;
- a validação final feita pelo ChatGPT/IA.

Princípio obrigatório:

~~~text
RAG encontra
    ↓
CodeBridge verifica a fonte real
    ↓
Git/arquivo prova o estado atual
    ↓
IA decide e executa
~~~

---

## 2. Modelos definidos para o CodeBridge 2.0

### 2.1 Contexto geral

Modelo principal:

~~~text
Jina v5 Text Small
~~~

Escopo:

- documentação;
- handoffs;
- roadmaps;
- patch notes;
- auditorias;
- logs resumidos;
- mensagens de erro;
- metadados Git;
- documentação técnica;
- português e inglês.

### 2.2 Código-fonte

Modelo especializado:

~~~text
Jina Code 1.5B
~~~

Escopo:

- C/C++;
- Python;
- PowerShell;
- Bash;
- CMD;
- JavaScript/TypeScript;
- arquivos de configuração com estrutura de código;
- recuperação natural-language → code;
- code → code.

### 2.3 Regra de carregamento

Os dois modelos serão usados **sob demanda**.

Não manter ambos residentes permanentemente em RAM/VRAM.

Fluxo esperado:

~~~text
consulta chega
    ↓
classificação da consulta
    ↓
modelo necessário já está carregado?
    ├── sim → usar
    └── não → carregar
             ↓
          gerar embedding
             ↓
       reutilizar enquanto ativo
             ↓
      descarregar após idle
~~~

O tempo de idle deverá ser configurável.

O carregamento sob demanda não pode bloquear nem alterar o executor de terminal.

---

## 3. Compatibilidade de hardware do CodeBridge 2.0

O CodeBridge 2.0 continuará sendo a edição de ampla compatibilidade.

A arquitetura RAG deverá considerar:

~~~text
GPU compatível disponível
        ↓
usar aceleração disponível

GPU indisponível/incompatível
        ↓
fallback CPU
~~~

A GPU deverá melhorar desempenho, nunca ser requisito para o funcionamento básico do RAG.

O backend definitivo de inferência só será congelado após benchmark real no RAG-006 e RAG-007.

---

## 4. Contexto futuro — CodeBridge 3.0

O CodeBridge 3.0 fica registrado somente como contexto para o próximo grande upgrade.

Direção prevista:

- perfil high-end;
- foco em GPU dedicada forte;
- RTX 3050 6 GB como referência mínima inicial a ser validada;
- modelos maiores;
- possibilidade de manter modelos residentes;
- reranking mais pesado;
- contexto local mais agressivo;
- maior throughput de indexação e busca.

### Fora do escopo deste handoff

Não implementar recursos específicos do CodeBridge 3.0 durante esta frente.

Este handoff trata **somente do CodeBridge 2.0**.

---

# 5. Arquitetura alvo

~~~text
                    ChatGPT
                       │
                       ▼
                 CodeBridge MCP
                       │
      ┌────────────────┼─────────────────┐
      │                │                 │
      ▼                ▼                 ▼
 exec/wait/stop   read_batch        RAG tools
                                         │
                                         ▼
                                   RAG Orchestrator
                                         │
                      ┌──────────────────┼──────────────────┐
                      │                  │                  │
                      ▼                  ▼                  ▼
                Text Retriever      Code Retriever      Lexical Search
                Jina v5 Small      Jina Code 1.5B       SQLite FTS5
                      │                  │                  │
                      └──────────────────┼──────────────────┘
                                         ▼
                                  Hybrid Rank/Fusion
                                         │
                                         ▼
                                    top contexts
                                         │
                                         ▼
                              verificação da fonte real
                                         │
                                         ▼
                                     ChatGPT
~~~

---

# 6. Fonte da verdade

O índice RAG nunca será fonte oficial do estado do sistema.

Fontes oficiais permanecem:

1. arquivo atual;
2. Git;
3. ledger do CodeBridge;
4. runtime real;
5. banco/configuração oficial quando aplicável.

O resultado do RAG deverá sempre carregar referência suficiente para permitir verificação.

Exemplo:

~~~text
project
source_type
path
symbol
line_start
line_end
git_branch
git_commit
sha256
indexed_at
chunk_id
score
~~~

---

# 7. Roadmap — dividir para conquistar

## RAG-001 — Contrato e isolamento da nova camada

### RAG-001-A — Congelar responsabilidade do RAG

Definir formalmente:

- o que o RAG pode fazer;
- o que o RAG não pode fazer;
- separação RAG × executor;
- separação índice × fonte da verdade;
- regra de verificação antes de alteração.

**Saída:** contrato arquitetural versionado.

### RAG-001-B — Definir módulos internos

Estrutura inicial sugerida:

~~~text
rag/
├── config.py
├── models/
├── index/
├── chunking/
├── retrieval/
├── ranking/
├── sources/
└── runtime/
~~~

**Saída:** layout aprovado, sem inferência ainda.

### RAG-001-C — Definir contratos de dados

Definir schemas:

- Document;
- Chunk;
- SourceMetadata;
- SearchQuery;
- SearchResult;
- ModelState;
- IndexState.

**Saída:** schemas testáveis.

### RAG-001-D — Testar isolamento

Provar que falha total do RAG não quebra:

- codebridge_exec;
- codebridge_wait;
- codebridge_stop;
- codebridge_read_batch;
- prepare/execute/discard.

**RAG-001 ✅** somente após Git + testes + commit.

---

## RAG-002 — Inventário de fontes

### RAG-002-A — Fontes documentais

Mapear:

- README;
- docs;
- handoffs;
- roadmaps;
- patch notes;
- auditorias.

### RAG-002-B — Fontes de código

Mapear extensões permitidas:

- .c;
- .cc;
- .cpp;
- .h;
- .hpp;
- .py;
- .ps1;
- .bat;
- .cmd;
- .sh;
- .js;
- .ts;
- .json;
- .yaml/.yml;
- .toml;
- outras aprovadas.

### RAG-002-C — Git

Mapear:

- branch;
- HEAD;
- commit;
- mensagem;
- arquivo;
- diff;
- histórico relevante.

### RAG-002-D — Execuções/auditorias

Definir o que pode ser indexado do ledger:

- execution_id;
- target;
- command_hash;
- status;
- erro estruturado;
- resumo;
- referência ao RAW.

Não indexar automaticamente o RAW inteiro.

### RAG-002-E — Exclusões

Criar denylist inicial:

- .git/objects;
- .venv;
- node_modules;
- build;
- dist;
- caches;
- binários;
- backups;
- temporários;
- credenciais;
- .env;
- chaves privadas;
- tokens.

**RAG-002 ✅** com inventário documentado e testes de exclusão.

---

## RAG-003 — Chunking de texto

### RAG-003-A — Markdown

Separar preferencialmente por:

- heading;
- subsection;
- bloco lógico.

### RAG-003-B — TXT/logs

Separar por:

- seção;
- execução;
- erro;
- evento;
- limite controlado.

### RAG-003-C — Overlap controlado

Definir overlap somente quando necessário.

Evitar duplicação excessiva de contexto.

### RAG-003-D — Proveniência

Cada chunk deve manter:

- path;
- linhas;
- SHA-256;
- data;
- source_type;
- project_id.

**RAG-003 ✅** com corpus de teste determinístico.

---

## RAG-004 — Chunking de código

### RAG-004-A — Parser por linguagem

Começar com linguagens prioritárias do CodeBridge.

### RAG-004-B — Função/método como unidade

Evitar corte cego por quantidade de tokens.

Preferir:

~~~text
classe
função
método
bloco lógico
~~~

### RAG-004-C — Símbolos

Extrair quando possível:

- class;
- function;
- method;
- constant;
- module;
- namespace.

### RAG-004-D — Fallback seguro

Se parser estrutural falhar:

- chunking textual controlado;
- marcar parser_mode=fallback;
- nunca perder arquivo silenciosamente.

### RAG-004-E — Linhas exatas

Manter line_start e line_end.

**RAG-004 ✅** após testes com Python, PowerShell e C/C++.

---

## RAG-005 — SQLite + FTS5

### RAG-005-A — Schema do índice textual

Criar SQLite dedicado ao RAG.

### RAG-005-B — FTS5

Indexar:

- conteúdo;
- path;
- símbolo;
- mensagem Git;
- títulos/headings.

### RAG-005-C — Busca lexical

Provar buscas exatas como:

~~~text
GetMoveSpeedProvenance
codebridge_wait
EXECUTION_V2_WAIT
~~~

### RAG-005-D — Ranking lexical

Congelar score/rank mínimo utilizável.

**RAG-005 ✅** sem embeddings ainda.

---

## RAG-006 — Jina v5 Text Small

### RAG-006-A — Backend de inferência

Avaliar backend compatível com:

- GPU quando disponível;
- CPU fallback;
- Windows;
- distribuição com CodeBridge.

### RAG-006-B — Download/instalação controlada

Modelo não deve ser baixado silenciosamente.

Definir:

- origem;
- versão;
- hash;
- diretório;
- tamanho;
- aceite do usuário quando necessário.

### RAG-006-C — Carregamento sob demanda

Implementar:

~~~text
UNLOADED
↓
LOADING
↓
READY
↓
IDLE
↓
UNLOADING
↓
UNLOADED
~~~

### RAG-006-D — Embedding textual

Gerar embeddings para corpus documental.

### RAG-006-E — Cache

Evitar recalcular embedding de chunk cujo SHA-256 não mudou.

### RAG-006-F — CPU fallback

Provar funcionamento sem GPU.

### RAG-006-G — Medir custo

Registrar:

- RAM;
- VRAM;
- cold start;
- warm query;
- embeddings/s;
- tempo de unload.

**RAG-006 ✅** somente com benchmark registrado.

---

## RAG-007 — Jina Code 1.5B

### RAG-007-A — Backend

Validar compatibilidade real do modelo com backend escolhido.

### RAG-007-B — Carregamento sob demanda

Mesmo state machine do modelo textual.

### RAG-007-C — Embedding de código

Indexar corpus de código separado logicamente.

### RAG-007-D — Consultas NL → code

Exemplos:

- "onde valida ownership do item?";
- "onde controla cancelamento?";
- "onde o runtime acorda o wait?".

### RAG-007-E — Code → code

Provar busca por trecho/código semelhante.

### RAG-007-F — CPU fallback

Medir viabilidade e latência.

### RAG-007-G — Memória

Provar que descarregar o modelo realmente libera memória suficiente.

**RAG-007 ✅** após benchmark.

---

## RAG-008 — Model Manager sob demanda

### RAG-008-A — Classificador de consulta

Decidir entre:

~~~text
TEXT
CODE
HYBRID
LEXICAL_ONLY
~~~

Começar com regras determinísticas simples.

Não usar LLM para classificação nesta fase.

### RAG-008-B — Exclusão mútua inicial

No CodeBridge 2.0, por padrão:

- não manter os dois modelos pesados residentes ao mesmo tempo;
- carregar somente o necessário;
- permitir exceção futura somente após benchmark.

### RAG-008-C — Idle timeout

Timeout configurável.

### RAG-008-D — Concorrência

Evitar duas cargas simultâneas do mesmo modelo.

### RAG-008-E — Falhas

Se modelo falhar:

- liberar recursos;
- retornar erro estruturado;
- manter FTS5 disponível;
- não derrubar MCP.

**RAG-008 ✅** com testes de lifecycle e falhas.

---

## RAG-009 — Índice vetorial

### RAG-009-A — Escolha do armazenamento

Comparar antes de congelar:

- Qdrant local;
- alternativa embutida/local aprovada.

Critérios:

- estabilidade;
- tamanho;
- performance;
- instalação;
- backup;
- portabilidade.

### RAG-009-B — Coleções separadas

Separar no mínimo:

~~~text
text
code
~~~

### RAG-009-C — Namespaces de projeto

Exemplo:

~~~text
codebridge
new-world-pvp
drones
outros
~~~

### RAG-009-D — IDs determinísticos

Mesmo chunk não pode criar duplicatas a cada indexação.

**RAG-009 ✅** após teste de reindexação idempotente.

---

## RAG-010 — Busca híbrida

### RAG-010-A — FTS5 + vetor textual

Combinar resultados.

### RAG-010-B — FTS5 + vetor de código

Combinar resultados.

### RAG-010-C — Consulta HYBRID

Quando necessário, pesquisar nos dois espaços.

### RAG-010-D — Fusão

Começar com método determinístico, preferencialmente Reciprocal Rank Fusion.

### RAG-010-E — Deduplicação

Evitar que chunks praticamente iguais dominem o top-k.

**RAG-010 ✅** com benchmark de retrieval.

---

## RAG-011 — Metadados Git

### RAG-011-A — HEAD/branch

Anexar estado Git ao chunk.

### RAG-011-B — Commit de proveniência

Quando possível, associar último commit relevante ao arquivo/trecho.

### RAG-011-C — Arquivos modificados

Não confundir índice antigo com working tree atual.

### RAG-011-D — Staleness

Marcar resultado como potencialmente stale quando SHA do índice divergir do arquivo atual.

**RAG-011 ✅** com teste de arquivo alterado após indexação.

---

## RAG-012 — Indexação incremental

### RAG-012-A — Manifest

Persistir:

- path;
- size;
- mtime;
- SHA-256;
- chunk ids;
- versão do modelo.

### RAG-012-B — Arquivo inalterado

SHA igual → não reprocessar.

### RAG-012-C — Arquivo alterado

Rechunk + reembedding somente daquele arquivo.

### RAG-012-D — Arquivo removido

Remover chunks órfãos.

### RAG-012-E — Mudança de modelo

Nova versão de embedding deve invalidar somente o índice correspondente.

**RAG-012 ✅** com indexação idempotente.

---

## RAG-013 — Tools MCP

Superfície inicial proposta:

~~~text
codebridge_rag_status
codebridge_rag_index
codebridge_search_context
codebridge_get_context
~~~

### RAG-013-A — rag_status

Expor:

- índice;
- projetos;
- modelos;
- loaded/unloaded;
- backend;
- CPU/GPU;
- última indexação.

### RAG-013-B — rag_index

Operação explícita de indexação.

Não iniciar indexação pesada silenciosamente.

### RAG-013-C — search_context

Entradas:

- query;
- project;
- source_types;
- top_k;
- path_filter;
- branch.

### RAG-013-D — get_context

Recuperar conteúdo completo/autorizado de resultados selecionados.

### RAG-013-E — Contratos de erro

Erros estruturados para:

- model load;
- index unavailable;
- source missing;
- stale result;
- invalid scope.

**RAG-013 ✅** após integração real MCP.

---

## RAG-014 — Benchmark próprio do CodeBridge

### RAG-014-A — Dataset

Criar perguntas reais, não benchmark artificial.

Mínimo inicial:

~~~text
25 código
25 docs/handoffs
20 erros/auditorias
10 Git
10 logs
10 PT-BR → código/termos em inglês
~~~

Total inicial: 100 consultas.

### RAG-014-B — Ground truth

Registrar manualmente fontes esperadas.

### RAG-014-C — Métricas

Medir:

- Recall@5;
- Recall@10;
- MRR;
- latência cold;
- latência warm;
- RAM;
- VRAM;
- tamanho do índice.

### RAG-014-D — Critério mínimo

Não colocar RAG em produção somente porque "parece funcionar".

Definir threshold antes do go-live.

**RAG-014 ✅** com relatório versionado.

---

## RAG-015 — Segurança

### RAG-015-A — Secrets

Denylist e detecção de arquivos sensíveis.

### RAG-015-B — Escopo

Projeto A não deve vazar resultados do projeto B quando scope explícito estiver ativo.

### RAG-015-C — Path traversal

Bloquear caminhos fora das raízes autorizadas.

### RAG-015-D — Conteúdo indexado

Registrar origem de todo chunk.

### RAG-015-E — Exclusão

Permitir remover projeto/índice sem tocar nos arquivos originais.

**RAG-015 ✅** após testes negativos.

---

## RAG-016 — Produção CodeBridge 2.0

### RAG-016-A — Soak

Rodar consultas/indexações repetidas.

### RAG-016-B — Restart

Provar recuperação após fechar/reabrir CodeBridge.

### RAG-016-C — CPU-only

Canary de instalação sem GPU dedicada.

### RAG-016-D — GPU

Canary com GPU compatível.

### RAG-016-E — Falha do modelo

Executor MCP deve continuar operacional.

### RAG-016-F — Auditoria Git

Executar política normal de fechamento:

~~~text
git status
git diff
revisão
testes
git diff --check
commit
push
auditoria pós-commit
working tree limpo
~~~

### RAG-016-G — Handoff pós-RAG

Gerar handoff final com:

- arquitetura congelada;
- modelos;
- hashes;
- backends;
- benchmarks;
- limitações;
- rollback;
- commits preservados.

**RAG-016 ✅ → RAG CodeBridge 2.0 PRODUÇÃO**

---

# 8. Sequência resumida

~~~text
RAG-001-A → B → C → D ✅
        ↓
RAG-002-A → B → C → D → E ✅
        ↓
RAG-003-A → B → C → D ✅
        ↓
RAG-004-A → B → C → D → E ✅
        ↓
RAG-005-A → B → C → D ✅
        ↓
RAG-006-A → B → C → D → E → F → G ✅
        ↓
RAG-007-A → B → C → D → E → F → G ✅
        ↓
RAG-008-A → B → C → D → E ✅
        ↓
RAG-009-A → B → C → D ✅
        ↓
RAG-010-A → B → C → D → E ✅
        ↓
RAG-011-A → B → C → D ✅
        ↓
RAG-012-A → B → C → D → E ✅
        ↓
RAG-013-A → B → C → D → E ✅
        ↓
RAG-014-A → B → C → D ✅
        ↓
RAG-015-A → B → C → D → E ✅
        ↓
RAG-016-A → B → C → D → E → F → G ✅
~~~

---

# 9. Regras permanentes desta frente

1. Nenhum modelo pode ser requisito para o executor MCP funcionar.
2. Nenhuma busca RAG autoriza alteração diretamente.
3. Antes de editar, reler/verificar a fonte real.
4. Git continua sendo prova de versão.
5. RAW continua sendo recuperável pelo ledger, não duplicado no RAG.
6. Não indexar secrets.
7. Não baixar modelos sem fluxo explícito/aprovado.
8. Não reindexar arquivo cujo conteúdo não mudou.
9. Não manter ambos os modelos residentes sem benchmark que justifique.
10. Cada fase fecha somente após auditoria Git + testes + commit + pós-commit limpo.

---

# 10. Resultado esperado do CodeBridge 2.0

Ao final, o CodeBridge 2.0 deverá conseguir receber algo como:

> "Continue aquela validação de equipamento que fizemos semana passada."

e recuperar de forma local e auditável:

- fase/handoff relacionado;
- código relevante;
- símbolos;
- arquivos;
- linhas;
- commit;
- auditorias;
- erros anteriores;

antes de usar o executor para verificar o estado atual.

Objetivo final:

~~~text
CodeBridge 2.0 atual
= ponte de execução rápida e auditável

CodeBridge 2.0 + RAG
= ponte de execução rápida, auditável e contextual
~~~

---

# 11. Estado após criação deste handoff

~~~text
MCP-PROD-001 → MCP-PROD-006 ✅
MCP-PERF-001 → MCP-PERF-006 ✅

RAG-001 PLANEJADO
RAG-002 PLANEJADO
RAG-003 PLANEJADO
RAG-004 PLANEJADO
RAG-005 PLANEJADO
RAG-006 PLANEJADO
RAG-007 PLANEJADO
RAG-008 PLANEJADO
RAG-009 PLANEJADO
RAG-010 PLANEJADO
RAG-011 PLANEJADO
RAG-012 PLANEJADO
RAG-013 PLANEJADO
RAG-014 PLANEJADO
RAG-015 PLANEJADO
RAG-016 PLANEJADO

Próxima ação oficial:
RAG-001-A — congelar responsabilidade do RAG.
~~~
