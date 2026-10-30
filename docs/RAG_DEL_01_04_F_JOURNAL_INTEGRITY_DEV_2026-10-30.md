RAG-DEL-01.04-F — Integridade de journal em laboratorio
Data 2026-10-30
O journal PREPARED/ACTIVE/ROLLED_BACK agora inclui SHA-256 canonico e e verificado antes de recuperar, auditar ou permitir uma segunda transacao. Um teste altera project_id mantendo o digest anterior e confirma recusa na auditoria e no rollback. Checksum sem chave detecta inconsistencias acidentais, NAO autentica contra adversario que pode recalcular o hash. Executor operacional continua bloqueado.
