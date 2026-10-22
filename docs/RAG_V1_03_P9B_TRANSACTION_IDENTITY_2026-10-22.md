# P9-B ? Identidade persistente da transacao NSIS

Modulo installer/rag_p9b_transaction_identity.py gera manifesto
exclusivo e sincronizado com fsync antes da alteracao, contendo
identidade por SHA256 do instalador NSIS, snapshot de arquivos,
snapshot HKCU/atalhos e preimagem persistente de recuperacao.
A verificacao independente recalcula todos os hashes.
Nao copia dados privados do registro para o reposit?rio.

Manifesto real criado apenas em release_staging:
P9B_TRANSACTION_IDENTITY_20261022.json.
SHA256: b358a28a0329bb563187a7c36f86331600ca11b1518a601484f9569fef7527f1.
TRANSACTION_IDENTITY_VERIFIED, quatro artefatos, origem 2d99ed4.
Cinco testes unitarios passaram: integridade, adulteracao,
hash invalido, reutilizacao do arquivo e conjunto incompleto.

Proximo requisito: orquestracao externa duravel que consume
esse manifesto e revalide os hashes imediatamente antes da
execucao real NSIS, com rollback integral e teste publico MCP.
Esta etapa nao executou instalador nem altera HKCU ou RAG.
P9-B permanece aberta.
