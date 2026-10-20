# PATCH NOTES — CodeBridge RAG V1.03-D-C Offline Worker

Data: 2026-10-20
Estado: IMPLEMENTADO / TESTADO EM AMBIENTE DE DESENVOLVIMENTO
Produção: NÃO LIBERADA
Commit de referência: 1e55841

## Mudanças técnicas

- Fila SQLite dedicada migrou de esquema V1 para V2 com estados persistentes e recibo validado
- Heartbeat transacional com token de lease e verificação de expiração após validação demorada
- Worker único por execução com opt-in explícito para fila e worker
- Builds em staging isolado usando Jina e Qdrant Local
- Validação cruzada de documentos hashes chunks vetores manifesto e modelo
- Confirmação terminal STAGED_OFFLINE_VALIDATED sem publicar geração
- Recuperação de leases expirados e retomada em processo Python independente
- Progresso sanitizado sem expor tokens nem caminhos internos
- Preflight para dependência qdrant-client antes de reservar job
- Bloqueio de fonte não aprovada ou alterada antes da conclusão

## Evidência

- Jina Text embedding e busca vetorial reais passaram no laboratório isolado
- Jina Code 1.5B gerou embedding real com load/unload
- Worker percorreu fila Git staging Jina Qdrant validação e recibo
- Segundo processo leu recibo persistido sem reexecutar geração
- Regressão integrada: 284 testes OK  exit_code 0
- Git em 1e55841 sincronizado com origin após testes
- Índice público legacy mantido sem atualização
- Dois arquivos Git preexistentes não relacionados preservados

## Pendente antes da entrega instalada

O Python embarcado em Programs/CodeBridge/runtime/python não encontra o pacote rag no sys.path e não possui qdrant-client instalado
Não foi alterado nem reparado automaticamente o runtime público
É necessário ajustar empacotamento dependências e teste da edição instalada em etapa controlada

## Política de segurança

Nunca iniciar watcher serviço ou worker automaticamente
Nunca modificar ponteiro de geração ou índice público sem autorização separada
Nunca usar os testes sintéticos como certificado de produção
