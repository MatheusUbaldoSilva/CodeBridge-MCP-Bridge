# P3 ? Falha entre journal e troca de ponteiro

Data 2026-10-21. Laboratorio isolado, sem mutacao de indice publico.

Teste test_p3_pre_pointer_failure_isolated.py injeta OSError depois do journal PREPARED mas antes de gravar active-generation.json. Confirmacoes: journal remanescente impede leitura fail-closed, ponteiro nao criado, rollback especifico retorna RECOVERED_LEGACY, remove jornal, preserva arquivo legacy e os arquivos da candidata. Ativacao foi simulada somente por fixture e mock do gate, nao concede autorizacao para execucao real.

Complementa testes existentes de falha depois do ponteiro. Publicacao do RAG real continua bloqueada por contrato e exige autorizacao especifica de geracao.

Teste adicional: falha na propria gravacao do journal nao deixa journal nem ponteiro ativo, nao altera bytes do legado. Ambos cenarios PASS em fixture temporaria.
