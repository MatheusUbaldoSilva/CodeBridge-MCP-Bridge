# RAG-DEL-01.03-C — Recibo de evidência da geração candidata
Data: 2026-10-30
Estado: Implementado em laboratório; NÃO é autorização de ativação.

`rag/runtime/knowledge_deletion_evidence.py` vincula o identificador da seleção e da geração-base aos hashes SHA-256 do SQLite e manifesto do estágio, além das contagens previamente verificadas. Cria recibo exclusivo via escrita sincronizada/atômica e oferece inspeção que detecta adulteração de recibo e arquivos.

`tests/test_rag_del_01_03_c_evidence.py` cobre emissão, leitura, negativa de aprovação, recibo duplicado, adulteração e deriva de contagens. 7 executados, 6 aprovados, 1 dispensado pela indisponibilidade de symlink no Windows.

IMPORTANTE: este recibo **não** cria um índice completo homologado, não atesta o Qdrant independentemente, não substitui verificação de origem nem autoriza trocar catálogo. A futura transição precisa validar recepção imutável, caminhos seguros, política de geração, reabertura, snapshots e rollback sob lock. Stable e dados de usuário não foram tocados.
