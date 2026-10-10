# RAG-017 — Preflight de compilação NSIS (2026-10-10)

Na máquina MatheusPC, não foi encontrado `makensis.exe` nos locais padrão nem no PATH. O executável existente `installer/dist/CodeBridge-Setup.exe` possui data de modificação **2026-09-30 08:33:13**, anterior à atualização da receita RAG. Não é evidência de compilação atual.

Criado `benchmarks/rag017_nsis_build_gate.py`, ferramenta somente leitura que verifica compilador, presença das entradas do instalador e se o binário é posterior a essas entradas. O diagnóstico local verificou 86 arquivos de entrada, sem faltantes, mas informou `compiler_found=false`, `installer_newer_than_inputs=false`, `compile_preflight_passed=false`; terminou com exit code 2. Dois testes de regressão checam recusa por compilador ausente e binário desatualizado; 810 testes RAG passaram.

**O gate não valida sintaxe NSIS nem inspeciona o conteúdo do EXE** e não constitui prova de compilação, instalação ou rollback, que seguem explicitamente falsos. O compilador e o empacotamento ainda precisam ser preparados em ambiente isolado, seguidos de build e auditoria de payload/rollback. Nenhum instalador foi executado, nenhuma dependência foi instalada e o CodeBridge ativo na porta 8765 foi preservado. RAG-017-J BLOCKED, build dual preservada.
