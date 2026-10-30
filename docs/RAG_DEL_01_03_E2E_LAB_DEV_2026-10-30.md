# RAG-DEL-01.03 — Evidência integrada de laboratório
Data: 2026-10-30
Escopo: apenas dados temporários no DEV.

`tests/test_rag_del_01_03_end_to_end_lab.py` executa a cadeia de laboratório: 2 documentos CODE em SQLite com FTS/manifesto; simula seleção para retirar `a.cpp`; constrói SQLite/FTS/manifesto isolados preservando `b.cpp`; planeja e transfere seu vetor CODE de 1536 dimensões entre clientes Qdrant Local independentes; gera checkpoint durável; executa verificação estrutural final; confirma originais byte a byte e ausência de ativação.

Resultado: 1 teste E2E laboratorial PASS. Nenhuma fonte real, índice público, Stable, `newworldpvp`, catálogo ou geração ativa alterados.

Limites: prévia e resolução da geração são simuladas; o teste não executa troca de catálogo, não prova recuperação após crash real e não substitui homologação com vários lotes e falhas injetadas. 01.03-C permanece parcial até incluir geração imutável com recibos completos.
