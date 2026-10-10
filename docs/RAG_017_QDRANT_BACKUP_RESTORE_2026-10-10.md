RAG-017 — Backup e restauração isolados do Qdrant (2026-10-10)

Com o venv Python temporário 3.13.15 e qdrant-client 1.19.1, executado `benchmarks/rag017_qdrant_backup_restore.py` exclusivamente no diretório `%TEMP%\CodeBridge-RAG017-BackupProbe-20261010`. Criada coleção canário `canary`, registro 47; cliente Qdrant fechado antes da cópia. Após copiar a pasta de banco, houve comparação SHA-256 de **3 arquivos**, todos idênticos; a pasta restaurada foi aberta por outro cliente e o payload foi recuperado. Evidência: `backup_files=3`, `hash_identical=true`, `restore_read_ok=true`, exit code 0.

Prova negativa: `benchmarks/rag017_qdrant_backup_negative.py` gerou arquivo de prova **em cópia separada** acrescentando conteúdo, detectou divergência SHA-256 (`corruption_detected=true`) e confirmou que o arquivo do backup original não mudou (`original_backup_untouched=true`), exit code 0.

Limitações: teste de cópia após cliente fechado; não valida snapshot online, transação interrompida no meio de gravação, corrupção real de banco, recuperação após falha de disco, restore de índice de produção nem rollback de instalação NSIS. RAG-017-J continua BLOCKED; CodeBridge principal preservado.
