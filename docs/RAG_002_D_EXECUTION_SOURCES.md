# RAG-002-D — Inventário de execuções e auditorias do ledger

Data: 2026-10-06  
Projeto: CodeBridge 2.0 — MCP Bridge  
Branch: `rag-002-source-inventory`

## Objetivo

Definir exatamente quais dados de uma execução podem virar contexto RAG sem duplicar o RAW do ledger

O handoff exige permitir

```text
execution_id
target
command_hash
status
erro estruturado
resumo
referência ao RAW
```

e proíbe indexar automaticamente o RAW inteiro

## Fonte da verdade

O ledger oficial do CodeBridge continua sendo a fonte da execução

O RAG recebe somente uma projeção de metadados

```text
RAG encontra execução
        ↓
execution_id aponta para ledger
        ↓
ledger recupera estado e RAW reais quando necessário
        ↓
IA verifica antes de agir
```

## Campos aprovados do ledger

A allowlist base é

```text
execution_id
target
command_hash
state
exit_code
error_type
error_message
started_at
finished_at
```

No registro RAG o campo `state` é exposto semanticamente como `status`

## Erro estruturado

O erro permitido é representado como

```text
structured_error
├── error_type
├── error_message
└── exit_code
```

Para execução concluída com sucesso e sem erro

```text
structured_error = null
```

O conteúdo de `error_message` ainda deverá passar pelas regras de secrets e exclusão do RAG-002-E antes de qualquer indexação real

## Resumo permitido

O resumo desta fase é estrutural e não textual

Pode conter

```text
started_at
finished_at
duration_ms
output_mode
compaction_applied
stdout_lines
stderr_lines
stdout_chars
stderr_chars
returned_stdout_chars
```

Isso permite responder questões como duração tamanho e modo de saída sem copiar o conteúdo bruto

## Referência ao RAW

Formato congelado

```text
raw_reference
├── execution_id
└── raw_available
```

Exemplo

```json
{
  "execution_id": "exec_001",
  "raw_available": true
}
```

O RAW continua no ledger e é recuperado sob demanda pelo execution_id

## Conteúdo proibido no índice por padrão

Não copiar automaticamente

```text
output
stdout
stderr
text
stdout_delta
stderr_delta
failed_command
important_sections
execution_output_chunks
raw
raw_output
```

### Motivo de failed_command

O ledger atual preserva `failed_command` em falhas e cancelamentos para diagnóstico

Esse texto pode conter argumentos tokens paths ou outros dados sensíveis

Por isso o RAG-002-D não o aprova para indexação automática

A identidade do comando no RAG permanece

```text
command_hash
```

## Compatibilidade com o contrato atual do CodeBridge

O MCP atual já expõe

```text
execution_id
target
state
exit_code
duration_ms
error_type
error_message
raw_available
output_mode
compaction_applied
stdout_lines
stderr_lines
stdout_chars
stderr_chars
returned_stdout_chars
```

O modo COMPACT atual também informa explicitamente que o RAW permanece disponível pelo execution_id

O RAG aproveita essa propriedade mas não copia o texto COMPACT automaticamente porque ele ainda contém trechos derivados do RAW

## Implementação do inventário

Criado

`rag/sources/execution_inventory.py`

Função principal

`build_execution_index_record`

A função recebe uma linha de ledger e produz somente a projeção aprovada

Ela não

- abre SQLite
- lê chunks RAW
- executa terminal
- carrega modelo
- cria índice
- altera ledger

## Exemplo de projeção

Entrada do ledger pode conter

```text
execution_id
request_id
target
command_hash
failed_command
state
runtime_instance
output
exit_code
error_type
error_message
...
```

Saída permitida

```text
execution_id
target
command_hash
status
structured_error
summary
raw_reference
```

## Auditorias

Auditorias derivadas de execução podem referenciar o mesmo `execution_id`

Elas não devem copiar automaticamente o RAW inteiro

Uma auditoria indexável deverá preferir

- identificador da auditoria
- execution_id relacionado
- resultado ou classificação
- timestamp
- referência à fonte real

O formato completo de auditorias externas continuará sujeito às roots autorizadas e à denylist

## Invariantes

- ledger continua fonte oficial
- execution_id é a âncora para recuperar RAW
- command_hash identifica o comando sem copiar comando bruto
- status vem do state real do ledger
- erro permanece estruturado
- resumo padrão é metadata-only
- output bruto não entra automaticamente
- failed_command não entra automaticamente
- important_sections não entra automaticamente
- nenhuma indexação foi iniciada
- executor não foi alterado

## Fora do escopo deste subpasso

Ainda não foram implementados

- leitura automática do ledger pelo RAG
- resumo semântico com modelo
- redaction de secrets
- indexação de auditorias externas
- indexação de RAW
- embeddings
- busca por execução
- tools MCP RAG

## Critério de aceitação do RAG-002-D

RAG-002-D está concluído quando

- todos os campos exigidos pelo handoff possuem representação
- RAW permanece somente referenciado
- failed_command e output bruto ficam excluídos
- resumo aceita apenas metadados estruturais
- testes negativos impedem conteúdo RAW no resumo
- o contrato continua independente do executor
