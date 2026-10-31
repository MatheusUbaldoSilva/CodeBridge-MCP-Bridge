# RAG-DEL-01.04-DQ-B — Mutex com prazo máximo (DEV)

Novo modulo knowledge_deletion_bounded_catalog_lab.py: trava auto-canary.lock via msvcrt.LK_NBLCK, tentativas limitadas, validacao de identidade do arquivo sob lock, rejeicao de journal pendente, caminhos TEMP obrigatorios e aprovacao de laboratorio.

O inventario privado DM passa a usar este guard e preserva seu contrato de erro PrivateInventoryLabError em falhas de caminho. O timeout tem tipo LaboratoryCatalogBusy.

Testes DQ-B: 10 executados, 9 PASS, 1 SKIP (criacao de symlink nao permitida no Windows). DM: 7 PASS. RAG-DEL: 325, 321 PASS, 4 SKIP. RAG-AUTO sem MCP: 241, 236 PASS, 5 SKIP. Nenhuma falha.

Escopo exclusivamente TEMP e codigo DEV. O guard nao coordena ainda os locks generation e semantic: esta composicao sera feita e testada em DQ-C. Nenhuma alteracao de indices reais, Stable ou GitHub; nenhuma exclusao habilitada.