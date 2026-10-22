# P9-B ? Novos alvos criados pelo NSIS

O backup do preview 2d99ed4 possui 258 destinos:
236 arquivos existentes preservados e 22 ausentes
antes da instalacao. Os novos destinos incluem modulos
da fila incremental e do supervisor do RAG.

installer/rag_p9b_rollback_new_targets.py lista somente
os alvos que nao existiam e valida ausencia de caminhos
simbolicos e tipos inesperados antes de qualquer
plano de remocao. Inspecao atual:
NEW_TARGETS_OBSERVED_ONLY; count=22;
exists_now=0; delete_authorized=false.

Nao foi executado NSIS, nenhuma remocao ou alteracao
na instalacao existente. O rollback futuro devera
verificar os hashes dos alvos apos a instalacao e
excluir somente arquivos comprovadamente criados
pelo instalador, sem remover dados nao pertencentes
ao CodeBridge. Tres testes isolados PASS.
