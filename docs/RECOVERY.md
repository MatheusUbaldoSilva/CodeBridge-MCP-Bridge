# Recuperação e integridade operacional

## Princípio

Recuperar significa **verificar estado, preservar dados e executar uma ação reversível**. Falha de comunicação com MCP não significa que a execução no shell falhou; não repetir automaticamente comandos com efeitos colaterais.

## Executor

Se `codebridge_exec` devolver `RUNNING` ou perder a resposta:

1. Guardar o `execution_id` informado.
2. Usar `codebridge_wait` e `cursor` para recuperar estado e saída sem novo Enter.
3. Inspecionar `exit_code`, campos de erro e eventos finais.
4. Usar `codebridge_stop(execution_id)` para cancelamento direcionado quando pertinente.

`ExecutionLedger.interrupt_incomplete_from_other_runtime` lida com execuções incompletas de outro runtime. `TerminalManager.recover_orphaned`, `recycle` e `cancel_active` oferecem caminhos controlados de recuperação, não reexecução implícita.

## Processos locais e túnel

Confirmar `AuthorMCPManager.status()` e `SecureTunnelManager.status()` antes de iniciar ou encerrar subprocessos. Evitar encerramento amplo de processos Python, que pode afetar serviços não pertencentes ao CodeBridge.

## Armazenamento RAG

Confirmar a geração com `codebridge_rag_status`. Os mecanismos de `rag/runtime/` incluem resolução de ponteiro, locks, leases de leitura, journal de transição, backup verificado e restauração controlada. Antes de qualquer reparo, preservar manifesto, SQLite, Qdrant e ponteiro ativo como conjunto coerente.

Não editar `active-generation.json`, não apagar dados vetoriais e não substituir bases diretamente para forçar atualização. O caminho de escrita incremental precisa cumprir gates de origem, integridade e publicação.

## Instalador e rollback

Os componentes de `installer/` incluem verificações de runtime, fingerprints, snapshots e testes de restauração. A existência dessas rotinas não autoriza executar atualização/rollback real da instalação ativa sem validação completa e decisão do operador.

## Checklist de integridade

- Conferir commit do repositório e estado Git antes de atualizar código.
- Preservar arquivos locais pendentes e informações de configuração.
- Confirmar hashes e identidade de dados/restauração.
- Executar testes de fonte com a raiz do checkout primeiro no `sys.path`, evitando importar inadvertidamente módulos da instalação.
- Validar funcionamento após qualquer correção antes de declarar sucesso.

Veja [EXECUTOR.md](EXECUTOR.md), [STORAGE.md](STORAGE.md) e [SECURITY.md](SECURITY.md).