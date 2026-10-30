# RAG-DEL-01.04-A — Planejamento de substituição de catálogo privado
Data: 2026-10-30
Estado: IMPLEMENTADO APENAS O PLANEJADOR SOMENTE LEITURA.

`rag/runtime/knowledge_deletion_catalog_plan.py` compara o catálogo privado atual com uma entrada candidata: recusa namespace público, revisão desatualizada, mesma geração ou ID incompatível, preserva outras entradas e calcula hashes SHA-256 do catálogo anterior, proposto e ponteiro público.

`tests/test_rag_del_01_04_a_catalog_plan.py` cobre cenário positivo sem escrita e quatro recusas. 5 testes em arquivos temporários.

**Importante:** o candidato proposto NÃO é validado, o novo catálogo NÃO é gravado, não existem backup ou journal desta operação, não há autorização de ativação. O executor da transição precisa primeiro obter um recibo íntegro da geração RAG-DEL, verificar lock/fencing e executar troca atômica com rollback sem interferir nos journals RAG-AUTO preexistentes. Somente depois de completar testes de falhas e recuperação essa fase poderá ser fechada.
