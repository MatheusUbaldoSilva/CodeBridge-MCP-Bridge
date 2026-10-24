# CodeBridge — Executor e runtime atuais

## Caminho de execução

O cliente chama `codebridge_exec` ou prepara via `codebridge_prepare`. O servidor MCP autoral encaminha a solicitação ao adapter autenticado, que utiliza o runtime e sua autoridade única de terminal.

O protocolo `CBMCP/1` mantém identificadores de requisição/resposta, handshake `REQUEST_SYN/REQUEST_ACK` e `RESPONSE_SYN/RESPONSE_ACK`, e proteção contra reexecução de um mesmo pedido. O ledger registra identidade, estados e resultados de execução.

## Alvos

| Alvo MCP | Destino | Dependência |
|---|---|---|
| `POWERSHELL5.1` | Terminal PowerShell 5.1 do Windows | Runtime e shell ativos |
| `CMD` | Terminal Prompt de Comando | Runtime e shell ativos |
| `SSH` | Sessão shell remota configurada | SSH online |

A lista de alvos suportados vem de `codebridge_capabilities.targets`; estar configurado não significa estar conectado. O retorno `codebridge_status.terminals` é a confirmação de disponibilidade no momento da consulta.

## Formas de executar

### Execução direta

```json
{"target":"POWERSHELL5.1","command":"Get-Location","wait_timeout_ms":1500,"output_mode":"NORMAL"}
```

Use a ferramenta `codebridge_exec`. Modos de saída aceitos: `NORMAL`, `COMPACT` e `RAW`. O modo compacto reduz volume da resposta, sem substituir a possibilidade de recuperar a saída bruta quando disponível.

### Preparação antes do Enter

1. `codebridge_prepare({"target":"POWERSHELL5.1","command":"Get-Location"})` apresenta/prepara o comando no terminal.
2. `codebridge_execute_prepared({"prepared_request_id":"<id retornado>"})` envia Enter uma vez.
3. Ou `codebridge_discard` para cancelar a preparação sem executar.

A operação de preparação não é uma execução concluída.

### Operação assíncrona, saída e cancelamento

A chamada `codebridge_exec` pode responder `RUNNING` e fornecer `execution_id`. Consulte o mesmo ID em:

```json
{"execution_id":"<id retornado>","cursor":0,"wait_timeout_ms":15000,"output_mode":"NORMAL"}
```

`codebridge_wait` devolve mudanças de estado e delta de saída; use o próximo cursor retornado para continuar sem duplicar conteúdo. Para interromper uma execução específica, chame `codebridge_stop({"execution_id":"<id>"})`.

Campos relevantes: `state`, `runtime_state`, `exit_code`, `stdout`, `stderr`, `complete`, `error_type`, `error_message` e `raw_available`. `FINISHED` representa término do ciclo, mas consulte `exit_code` e erros para determinar sucesso do comando.

## Limites retornados por capabilities na instalação observada

| Parâmetro | Valor |
|---|---:|
| `exec_wait_timeout_max_ms` | 10.000 |
| `wait_timeout_max_ms` | 120.000 |
| `wait_max_chars` | 262.144 |
| `compact_response_max_chars` | 9.000 |
| `read_batch_max_items` | 32 |
| `read_batch_max_workers` | 8 |

Esses valores vêm da instância observada e podem variar conforme a versão instalada.

## Concorrência e consistência

O runtime oferece consultas de lote somente leitura (`codebridge_read_batch`) e espera orientada a eventos (`codebridge_wait`), além de saída incremental e cancelamento direcionado. Não assumir que um comando é seguro ou idempotente por estar encapsulado no MCP. O comportamento de comandos PowerShell, CMD e SSH depende da semântica da linguagem e das permissões da conta efetiva.

## Estado e segurança

- Não executar comandos destrutivos sem revisar o comando e seu escopo.
- O shell real pode ter estado e diretório corrente próprios.
- Segredos de autenticação nunca devem ser exibidos ou registrados em documentação.
- Falhas no transporte, no shell e no próprio comando são classes diferentes; preferir os campos estruturados de erro.
- Não interpretar um timeout curto como falha de execução: recuperar pelo `execution_id`.
