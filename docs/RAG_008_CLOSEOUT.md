# RAG-008 — Closeout do Model Manager sob demanda

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-008-model-manager`

## Estado

`RAG-008 ✅ FECHADO`

O critério do handoff foi cumprido

O Model Manager agora classifica consultas deterministicamente coordena TEXT e CODE com exclusão mútua descarrega por inatividade serializa transições concorrentes e converte falhas operacionais em resultado estruturado com fallback lexical

## Base

RAG-008 parte do fechamento do RAG-007

`43228b4 docs(rag-007): close Jina code embedding milestone`

## RAG-008-A — Classificador de consulta

Commit

`93893dd feat(rag-008-a): add deterministic query classifier`

Rotas congeladas

```text
TEXT
CODE
HYBRID
LEXICAL_ONLY
```

Características

- regras determinísticas
- nenhum LLM usado para classificação
- nenhum modelo carregado no import
- formato lexical exato tem prioridade
- source_types explícitos têm prioridade sobre heurística semântica
- default conservador TEXT
- mistura código + documentação retorna HYBRID

## RAG-008-B — Exclusão mútua inicial

Commit

`40fef01 feat(rag-008-b): enforce initial model mutual exclusion`

Invariante

```text
TEXT ativo XOR CODE ativo
```

Nunca os dois ao mesmo tempo

Troca TEXT → CODE

```text
unload TEXT
↓
estado sem modelo
↓
load CODE
```

Troca CODE → TEXT segue a mesma regra

Snapshot inválido com dupla residência é rejeitado

## RAG-008-C — Idle timeout

Commit

`0870f1d feat(rag-008-c): add configurable idle timeout`

Política

- timeout configurável
- None desabilita
- valor deve ser maior que zero
- relógio padrão time.monotonic
- touch renova atividade
- unload_if_idle descarrega no limite
- nenhum worker ou timer em background

Fluxo

```text
atividade
↓
last_activity_at
↓
idle < timeout → manter
idle >= timeout → unload
```

## RAG-008-D — Concorrência

Commit

`e87311d feat(rag-008-d): serialize model manager transitions`

Implementação

`threading.RLock`

Transições serializadas

- activate
- unload_active
- unload_if_idle
- touch
- snapshot
- leituras de estado

Provas

- duas ativações do mesmo modelo não executam load simultaneamente
- CODE espera load de TEXT terminar antes da troca
- unload espera load em andamento terminar
- exclusão mútua continua válida sob concorrência

Nenhuma thread própria é iniciada pelo manager

## RAG-008-E — Falhas

Commit

`063b1b4 feat(rag-008-e): add safe failure policy and lexical fallback`

APIs seguras

`activate_safe()`

`unload_active_safe()`

Resultado estruturado

`ModelManagerOperationResult`

Campos principais

- ok
- operation
- requested_model
- active_model
- value
- error_type
- error_message
- cause_type
- cleanup_errors
- fallback_route

Tipos de erro estáveis

```text
ACTIVATION_FAILED
UNLOAD_FAILED
```

Falha operacional retorna

```text
fallback_route=LEXICAL_ONLY
```

A exceção operacional não precisa atravessar a fronteira MCP

## Cleanup em falha

Em falha segura

```text
tentar unload TEXT
↓
tentar unload CODE
↓
active_model=None
last_activity_at=None
↓
retornar resultado estruturado
```

Erros secundários de cleanup ficam em `cleanup_errors`

`resources_released` informa se todas as limpezas terminaram sem erro

## FTS5 preservado

O Model Manager não abre fecha reconstrói nem altera o índice FTS5

Em falha de modelo a rota estruturada `LEXICAL_ONLY` permite continuar pela busca lexical existente

Assim falha de embedding local não implica indisponibilidade da busca lexical nem derrubada do MCP

## Testes

Antes do fechamento formal

```text
Ran 427 tests
OK
```

Testes específicos adicionados durante RAG-008

- 13 classificador
- 11 exclusão mútua
- 13 idle timeout
- 3 concorrência
- 7 política de falhas

Auditorias

```text
git diff --check
OK
```

```text
git diff --cached --check
OK
```

## Arquitetura consolidada

```text
query
↓
classificador determinístico
├── LEXICAL_ONLY → FTS5
├── TEXT
├── CODE
└── HYBRID
     ↓
Model Manager
     ↓
exclusão mútua
     ↓
load do modelo necessário
     ↓
atividade / idle timeout
     ↓
operação serializada
     ↓
sucesso
ou
falha estruturada → LEXICAL_ONLY
```

HYBRID não significa manter os dois modelos residentes simultaneamente

A execução híbrida real será composta nas fases de busca posteriores respeitando a política de residência

## Fronteiras preservadas

Não pertencem ao RAG-008

### RAG-009

Índice vetorial

- backend de armazenamento vetorial
- coleções separadas
- IDs determinísticos
- namespaces de projeto

### RAG-010

Busca híbrida

- FTS5 + vetor textual
- FTS5 + vetor de código
- fusão de ranking
- deduplicação

### RAG-011 e seguintes

- filtros avançados
- ingestão incremental adicional
- avaliação e benchmark de recuperação
- exposição final pela superfície MCP

## Critério de fechamento

RAG-008 pode ser marcado fechado porque

- classificador TEXT CODE HYBRID LEXICAL_ONLY existe
- nenhum LLM é usado para classificação
- TEXT e CODE têm exclusão mútua
- timeout de idle é configurável
- loads concorrentes são serializados
- unload concorrente é serializado
- falhas operacionais têm resultado estruturado
- cleanup é tentado após falha
- fallback lexical permanece disponível
- Model Manager não toca FTS5
- 427 testes RAG passaram
- diff check passou
- cada subfase A B C D E possui commit próprio
- branch está sincronizada com origin antes do closeout

## Próximo marco

`RAG-009 — Índice vetorial`

O primeiro passo oficial deve seguir o handoff

`RAG-009-A`
