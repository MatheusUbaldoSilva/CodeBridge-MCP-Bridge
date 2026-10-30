# RAG-DEL-01.04-DF — Diagnóstico do scheduler sob lock compartilhado (DEV)

## Implementação

A inspeção read-only de incremental_scheduler_public_pointer.py era executada fora do lock de geração. Agora inspect_public_pointer_for_scheduler detém production_generation_lock(exclusive=False, channel="generation") durante a inspeção de journal e ponteiro. Colisão com lock exclusivo do cutover retorna PUBLIC_POINTER_BUSY, generation None, safe_to_schedule False e read_only True, sem ler ponteiro fora da região protegida.

Outros estados mantidos: PUBLIC_TRANSITION_PENDING, PUBLIC_LEGACY_POINTER, PUBLIC_POINTER_INVALID e PUBLIC_POINTER_OBSERVED. Todos retornam safe_to_schedule False; a inspeção nunca inicia workers, grava índices ou dá permissão operacional.

Os testes existentes de diagnóstico usam guard nulo injetado APENAS por unittest.mock. Testes novos exercitam o LockFileEx real em TemporaryDirectory/CodeBridge/rag, inclusive concorrência real entre processos Windows, integridade do ponteiro e journal pendente.

## Limitações

É uma leitura breve; a detenção de generation shared não garante consistência após retornar. Leitores que manipulam SQLite e Qdrant durante uma sessão precisam manter pin pelo ciclo completo, como production_generation_read.

A auditoria de outras rotas GUI/MCP/legadas e a compatibilidade integral dos locks generation/semantic/queue permanecem pendentes. A exclusão real e ativação de gerações não foram habilitadas, e a Stable não foi alterada.