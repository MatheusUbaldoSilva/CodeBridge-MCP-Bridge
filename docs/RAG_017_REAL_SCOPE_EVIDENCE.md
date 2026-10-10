# RAG-017 — Filtros combinados no índice persistente real

Execução opt-in da variante Code-only com modelo Jina Code residente e Qdrant local reutilizado, usando `search_persistent_semantic` com `experimental_cross_route=True`, `experimental_resident_models=True`. Nenhum serviço instalado foi modificado ou ativado.

**Sete cenários passaram:** projeto `codebridge` (10 resultados), branch inexistente (0), caminho inexistente (0), fonte `CODE` (10), `CODE` com caminho `rag/` (10), combinação com branch inexistente (0) e projeto inexistente válido (0). Os metadados de cada resultado foram confrontados com o escopo da consulta. Tempos observados: 4521,56 ms primeira consulta; demais entre 62,01 e 155,83 ms. Não equivalem ao p95 estatístico de produção.

O teste inicial utilizou um identificador de projeto inválido para o contrato e foi corrigido antes da execução final; a validação final retornou `passed=true` em 7/7 cenários. Limitações: não exercita todos os projetos/branches reais, falsificação de payload, credenciais de acesso ou o serviço instalado. Gate BLOCKED; holdout independente pendente; build dual candidata preservada.
