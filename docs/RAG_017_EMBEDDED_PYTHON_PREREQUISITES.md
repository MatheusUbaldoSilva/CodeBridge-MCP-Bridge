# RAG-017 — Gate de dependências no Python embutido

Auditoria em 2026-10-10 no Python 3.13.15 embutido da instalação existente. A instalação possui `mcp`, `pydantic` e `psutil`, mas **não possui `numpy`, `qdrant_client` nem o pacote `rag`**. Os caminhos `sys.path` não incluem a raiz instalada. O import de `rag.runtime.production_search` passou somente quando a raiz do staging foi adicionada explicitamente ao `sys.path`.

Criado `benchmarks/rag017_embedded_runtime_gate.py`, que consulta os módulos disponíveis e retorna exit code 2 quando falta algum requisito. No runtime instalado o resultado foi `ready_for_rag=false`, `production_approved=false` e `GATE_EXIT=2`. Dois testes unitários validam a recusa e a não promoção mesmo com dependências presentes.

**Próximo passo:** corrigir receita NSIS e bootstrap em ambiente isolado para empacotar `rag/`, configurar import pela raiz instalada e instalar dependências binárias compatíveis com o Python embutido. Executar preflight e testes em cópia limpa antes de atualizar o CodeBridge ativo. O gate não valida versionamento de dependências nem garante rollback. Instalação original e build dual preservadas; RAG-017-J BLOCKED.
