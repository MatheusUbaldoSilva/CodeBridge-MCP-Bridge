# Contrato RAG — CodeBridge 2.0

## Estado

Marco: RAG-001-A  
Status: CONGELADO para a responsabilidade arquitetural inicial  
Escopo: CodeBridge 2.0 MCP Bridge

## Objetivo

A camada RAG existe para descobrir e contextualizar informação técnica antes da execução

Ela ajuda a localizar documentação código símbolos histórico Git auditorias erros e referências relevantes

Ela não substitui o executor MCP nem decide sozinha o estado real do sistema

## Regra central

O fluxo obrigatório é

```text
RAG encontra contexto
    ↓
CodeBridge verifica a fonte real
    ↓
arquivo Git ledger runtime ou configuração oficial provam o estado atual
    ↓
IA decide
    ↓
executor MCP executa quando necessário
```

Nenhum resultado do índice RAG autoriza alteração por si só

## O que o RAG pode fazer

- indexar somente fontes autorizadas
- localizar contexto documental e técnico
- localizar código e símbolos
- recuperar referências de Git
- recuperar referências resumidas de execuções e auditorias quando permitido
- combinar busca lexical e vetorial quando implementadas
- classificar e ordenar resultados
- devolver proveniência suficiente para verificação da fonte real
- indicar possível staleness quando o índice divergir da fonte atual

## O que o RAG não pode fazer

- executar PowerShell CMD SSH ou qualquer shell
- chamar diretamente o executor para alterar estado
- decidir SUCCESS FAILED CANCELLED ou exit code
- substituir o ledger de execuções
- substituir o conteúdo real dos arquivos
- substituir Git como prova de versão
- tratar embedding índice ou score como fonte oficial
- reexecutar comando para recuperar output
- armazenar uma segunda cópia RAW integral do ledger como mecanismo padrão
- indexar secrets credenciais tokens chaves privadas ou arquivos explicitamente negados
- baixar modelos silenciosamente
- iniciar indexação pesada silenciosamente
- tornar GPU ou modelo de embedding requisito para o executor MCP funcionar

## Fontes oficiais

Quando houver conflito o índice perde para a fonte real

A ordem de verificação deve considerar conforme o tipo de dado

1. arquivo atual autorizado
2. Git atual
3. ledger oficial do CodeBridge
4. runtime real
5. banco ou configuração oficial quando aplicável

O RAG é uma camada de descoberta e nunca a autoridade final

## Gate obrigatório antes de alteração

Antes de qualquer edição mutação ou execução baseada em contexto recuperado

1. recuperar a referência RAG
2. identificar projeto path símbolo linhas commit ou outra proveniência disponível
3. reler a fonte real atual
4. verificar Git e estado do working tree quando a operação envolver arquivos versionados
5. detectar se o resultado RAG está stale
6. somente depois permitir decisão da IA
7. somente depois usar o executor MCP quando necessário

Se a fonte real não puder ser verificada a alteração deve ser bloqueada

## Isolamento do executor

Falha total da camada RAG não pode quebrar nem degradar semanticamente

- codebridge_exec
- codebridge_wait
- codebridge_stop
- codebridge_read_batch
- codebridge_prepare
- codebridge_execute_prepared
- codebridge_discard

O executor MCP deve continuar operacional mesmo com

- índice indisponível
- modelo não instalado
- modelo descarregado
- backend de embedding falhando
- banco RAG corrompido ou ausente
- GPU indisponível
- serviço vetorial indisponível

A degradação aceitável é perder busca contextual e manter execução normal

## Limite entre RAG e ledger

O ledger continua sendo a fonte das execuções

O RAG pode indexar metadados aprovados como

- execution_id
- target
- command_hash
- status
- erro estruturado
- resumo determinístico
- referência ao RAW

O RAW integral permanece recuperável pelo ledger e não deve ser duplicado automaticamente no índice RAG

## Segurança de escopo

Cada busca deve respeitar raízes e projetos autorizados

Um projeto não deve vazar contexto de outro quando o escopo explícito estiver ativo

Path traversal para fora das raízes autorizadas deve ser rejeitado

Arquivos negados continuam negados mesmo que sejam tecnicamente legíveis pelo processo local

## Falha segura

Se o RAG falhar

- retornar erro estruturado da camada RAG
- não inferir que a fonte não existe
- não executar automaticamente uma alternativa mutável
- manter busca lexical disponível quando possível
- manter o executor MCP independente
- preservar a possibilidade de verificação manual da fonte real

## Invariantes congelados em RAG-001-A

1. RAG descobre contexto mas não é autoridade
2. nenhuma busca RAG autoriza mudança diretamente
3. fonte real deve ser verificada antes de alteração
4. Git continua sendo prova de versão para conteúdo versionado
5. ledger continua sendo fonte oficial de execução
6. RAW continua recuperável pelo ledger sem reexecução
7. secrets não entram no índice
8. modelos não são requisito do executor
9. downloads e indexações pesadas exigem fluxo explícito
10. falha do RAG não derruba o MCP de execução

## Fora do escopo de RAG-001-A

Ainda não são congelados neste subpasso

- layout definitivo de módulos
- schemas de Document Chunk SearchQuery SearchResult e estados
- chunking
- SQLite FTS5
- backend Jina
- armazenamento vetorial
- ranking híbrido
- tools MCP do RAG
- benchmarks
- política final de lifecycle de modelos

Esses pontos pertencem aos próximos subpassos e marcos do handoff

## Critério de aceitação de RAG-001-A

RAG-001-A está pronto quando

- este contrato está versionado
- a separação RAG versus executor está explícita
- índice versus fonte da verdade está explícito
- o gate de verificação antes de alteração está explícito
- falha do RAG não implica falha do executor
- nenhum item de RAG-001-B ou posterior foi implementado antecipadamente
