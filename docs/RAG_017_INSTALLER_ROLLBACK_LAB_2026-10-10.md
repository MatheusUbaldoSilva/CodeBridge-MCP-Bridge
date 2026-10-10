RAG-017 — Ensaio de rollback em laboratório temporário (2026-10-10)

Auditoria do instalador NSIS confirma alterações em `HKCU\Software\CodeBridge`, chaves de desinstalação, atalhos no desktop/menu iniciar, scripts de bootstrap de dependências e chamadas de início do CodeBridge. A receita atual não é segura para teste de reversão sobre a instalação ativa.

Criado `benchmarks/rag017_installer_rollback_lab.py` com restrição de caminho a diretório novo diretamente sob `%TEMP%` e prefixo `CodeBridge-RAG017-RollbackLab-`. Foram preparados seis arquivos fictícios representando aplicativo, MCP, `_pth`, configuração, registro exportado e atalho. Após backup, foram simuladas seis alterações, incluindo novo módulo RAG. A restauração recuperou hashes idênticos dos seis arquivos e removeu o novo módulo: `restored_identical=true`, `new_files_removed=true`, exit code 0. Nenhum registro real nem atalho real foi alterado.

**Limite essencial:** trata-se de simulação de arquivos; NÃO é rollback completo do NSIS, e não reproduz efeitos de pip, serviços, subprocessos, locks ou recuperação após atualização real. `actual_nsis_rollback_verified=false`. O próximo marco exige snapshot completo em VM descartável ou instalador com transação/rollback testado, antes de atualização real. Produção RAG-017-J permanece BLOCKED.
