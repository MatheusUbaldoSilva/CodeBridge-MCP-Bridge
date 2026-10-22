# P9-B ? Integracao real do backend com registro simulado

Teste tests/test_rag_p9b_combined_real_backend_integration.py
aciona em um unico coordenador:
- rollback de arquivos em diretorio descartavel via ZIP;
- restore_shell real com escrita atomica de atalhos;
- ScopedHKCU com FakeWinreg (nenhuma alteracao ao HKCU real);
- preimagem real e duas validacoes independentes de shell;
- journal fsync compartilhado entre coordenador e backend.

Resultado: COMBINED_LAB_RECOVERY_VERIFIED, seis eventos
persistidos no journal (quatro do coordenador e dois do
backend), um arquivo antigo, um destino novo removido,
cinco atalhos e duas chaves fake HKCU validadas.

Cenario negativo: destino novo desconhecido bloqueia
antes do backend de shell; atalho original de estado
interrompido permanece intacto. Dois testes integrados PASS.

Nao executou instalador NSIS e nao tocou no HKCU real.
O bloqueio de producao continua aberto: executor elevado
externo + interrupcao verdadeira NSIS + rollback e reinicio
da stack com handshake publico do MCP.
