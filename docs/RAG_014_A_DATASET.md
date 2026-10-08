# RAG-014-A — Dataset real do benchmark CodeBridge

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-014-benchmark`

## Objetivo

Criar o dataset inicial exigido pelo handoff para benchmark próprio do CodeBridge

O handoff exige perguntas reais e proíbe tratar um benchmark artificial como prova de produção

## Distribuição congelada

```text
25 código
25 docs/handoffs
20 erros/auditorias
10 Git
10 logs
10 PT-BR → código/termos em inglês
```

Total

`100 consultas`

## Arquivo

`benchmarks/rag014_dataset.jsonl`

Cada linha possui

```text
id
category
query
language
ground_truth_status
```

## Ground truth

RAG-014-A não inventa respostas esperadas

Todos os registros ficam explicitamente com

`ground_truth_status=PENDING_RAG_014_B`

A associação manual das fontes esperadas pertence ao RAG-014-B conforme o handoff

## Natureza das consultas

As perguntas foram construídas a partir de funcionalidades e artefatos realmente presentes no repositório

Exemplos de código

- classificador TEXT CODE HYBRID LEXICAL_ONLY
- Model Manager
- idle timeout
- exclusão mútua
- Qdrant
- namespaces
- IDs determinísticos
- RRF
- deduplicação
- incremental indexing
- MCP tools
- Git metadata

Exemplos de documentação

- closeouts RAG-009 até RAG-013
- decisões de backend
- contratos de collections
- benchmark RAG-010
- regras de staleness
- contratos das tools MCP

Erros e auditorias cobrem falhas reais previstas pelos contratos

Git cobre HEAD branch provenance working tree e staleness

Logs cobrem arquivos de restart transition e regras de indexação de execução

O bucket PT-BR usa perguntas naturais em português que precisam recuperar símbolos ou conceitos implementados em inglês

## IDs

IDs são estáveis e sequenciais

```text
rag014-001
...
rag014-100
```

## Validação automática

Criado

`tests/test_rag_014_dataset.py`

O teste prova

- exatamente 100 consultas
- distribuição exata do handoff
- IDs únicos e sequenciais
- queries únicas
- queries não vazias
- schema uniforme
- bucket PT-BR marcado como pt-BR
- ground truth ainda pendente para RAG-014-B

## Critério de aceitação

RAG-014-A está concluído quando

- existem 100 consultas
- contagem por categoria corresponde ao handoff
- não existem IDs duplicados
- não existem queries duplicadas
- dataset é versionado
- ground truth não é antecipado
- testes passam
- git diff check passa

## Próximo passo

`RAG-014-B — Ground truth`

Registrar manualmente as fontes esperadas para cada consulta
