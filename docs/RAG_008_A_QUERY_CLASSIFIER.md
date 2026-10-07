# RAG-008-A — Classificador determinístico de consulta

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch rag-008-model-manager

## Objetivo

Decidir entre TEXT CODE HYBRID e LEXICAL_ONLY sem usar LLM

## Regras congeladas

A classificação é determinística e side effect free

Nenhum modelo é carregado

Nenhum índice é aberto

Nenhum comando externo é executado

## Prioridade

1 formato lexical exato
2 escopo explícito de source_types
3 sinais de código e documentação
4 default TEXT

## LEXICAL_ONLY

Usado quando a consulta já possui formato exato forte

Exemplos

hash Git

caminho de arquivo

símbolo CamelCase ou CONSTANT_CASE

símbolo com namespace

expressão inteira entre aspas

Objetivo

evitar carregar modelo quando busca lexical exata é suficiente

## CODE

Usado quando

source_types contém somente CODE

existe snippet de código

existem sinais claros de pergunta sobre implementação

## TEXT

Usado quando

source_types contém somente fontes não CODE

existem sinais de README handoff roadmap docs audit log Git

nenhuma evidência mais específica existe

TEXT é o default conservador

## HYBRID

Usado quando

source_types mistura CODE e fontes textuais

a consulta contém simultaneamente sinais de código e documentação

## Arquivos

Criados

rag/runtime/__init__.py

rag/runtime/query_classifier.py

tests/test_rag_query_classifier.py

## Fronteiras

RAG-008-A não carrega nem descarrega modelos

Não implementa exclusão mútua

Não implementa idle timeout

Não implementa concorrência

Não altera FTS5

Esses pontos pertencem às próximas subfases do RAG-008
