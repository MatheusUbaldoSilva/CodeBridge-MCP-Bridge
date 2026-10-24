<p align="center">
  <img src="assets/codebridge_brand_header.png" alt="CodeBridge 2.0 — MCP Bridge" width="800">
</p>

# CodeBridge 2.0 — MCP Bridge

**Atualizado em 24/10/2026.** Projeto Windows de integração entre ChatGPT e computadores autorizados por um **servidor MCP autoral**, com executor de terminais, telemetria, ferramentas de leitura e RAG local com Jina Embeddings, SQLite e Qdrant.

> **Situação atual:** o executor MCP e a consulta ao índice RAG existente funcionam. A entrada de fontes possui inventário e prévia, mas a **publicação incremental no índice ativo ainda está bloqueada**. A fase de atualização/rollback NSIS P9-B está congelada para priorizar leitura, escrita e gerenciamento do RAG. Não interpretar testes isolados como autorização de instalação em produção.

## Documentação técnica oficial

O conjunto de referências **do sistema que existe nesta branch** está em [docs/INDEX.md](docs/INDEX.md). Inclui arquitetura, executor e ledger, 16 ferramentas MCP principais e 2 ferramentas de checkpoint de desenvolvimento, segurança (DPAPI, Named Pipes), RAG interno e ranking, interface Windows, implantação NSIS e recuperação, sempre distinguindo código implementado de disponibilidade operacional.

## Arquitetura e responsabilidades

```text
ChatGPT — ferramentas MCP
          │ streamable HTTP / Secure Tunnel (canal main)
          ▼
CodeBridge MCP autoral — 127.0.0.1:8765/mcp
          │ CBMCP/1 / idempotência / validação
          ▼
Adapter local — 127.0.0.1:8766
          │ API local autenticada
          ▼
CodeBridge Runtime + autoridade única de terminal
          ├── PowerShell 5.1
          ├── CMD
          ├── SSH Linux (quando configurado e online)
          ├── ledger de execuções e saída persistente
          └── RAG local: inventário → SQLite FTS5 + Qdrant → Jina
                       │
                       └── citações com arquivo, linhas, SHA e Git
```

A interface desktop utiliza Python/PySide6, terminais reais, telemetria e o painel **Meus conhecimentos**. A versão 2.0 não depende da extensão Chrome, do DOM do ChatGPT nem de interpretar blocos `@CODEBRIDGE` como protocolo. O Browser Bridge 1.x é separado.

### Ciclo de uma execução

1. O ChatGPT chama `codebridge_exec` com `target` e `command`; ou faz `codebridge_prepare` para inserir o comando sem pressionar Enter.
2. O MCP encaminha o pedido pelo protocolo **CBMCP/1**, com pares `REQUEST_SYN/REQUEST_ACK` e `RESPONSE_SYN/RESPONSE_ACK`, identificadores e proteção contra repetição.
3. O adapter autenticado conversa com o runtime. O terminal correspondente recebe o comando; a execução ganha um `execution_id`.
4. O ledger persiste estados e resultados; `codebridge_wait` acompanha saída por cursor sem reenviar Enter. Saídas grandes podem ser consultadas em modo `RAW`.
5. `codebridge_stop` interrompe a execução indicada. Uma execução preparada também pode ser descartada com `codebridge_discard`.

PowerShell 5.1 e CMD estavam online nas últimas verificações; SSH é opcional e pode estar offline. O runtime normalmente inicia e supervisiona os seus próprios processos locais MCP/adapter e os encerra no fechamento normal. A disponibilidade real deve ser verificada com `codebridge_status`.

## Catálogo MCP — chamadas atuais

Os nomes abaixo são os nomes declarados em `author_mcp/mcp_server.py` na branch atual. A exposição efetiva depende da versão MCP carregada e da conexão; uma ferramenta presente no código pode não estar disponível na sessão.

| Ferramenta | Finalidade | Efeito |
|---|---|---|
| `codebridge_status()` | Handshake, disponibilidade, terminais, fila e executor | Leitura |
| `codebridge_capabilities()` | Recursos, limites, alvos e migração dos comandos legados | Leitura |
| `codebridge_read_batch(...)` | Lote de operações **estritamente somente leitura** (ex.: status Git, versão e informações de arquivos, dentro da lista permitida) | Leitura |
| `codebridge_prepare(target, command)` | Prepara comando no terminal real, sem Enter | Modifica buffer |
| `codebridge_execute_prepared(prepared_request_id)` | Executa uma única vez um comando preparado | Execução |
| `codebridge_discard(request_id=None)` | Descarta comando preparado sem executar | Controle |
| `codebridge_exec(target, command, wait_timeout_ms=1500, output_mode="NORMAL")` | Execução V2 direta; modos `NORMAL`, `COMPACT`, `RAW` | Execução |
| `codebridge_wait(execution_id, cursor=0, wait_timeout_ms=15000, output_mode="NORMAL")` | Estado, saída incremental e recuperação por cursor | Leitura |
| `codebridge_stop(execution_id=None)` | Cancelamento direcionado; sem ID, interrompe ativo ou descarta preparado | Controle |
| `codebridge_rag_status()` | Estado do índice, projetos, modelos e backend | Leitura |
| `codebridge_rag_index(project_id, project_root, scope="BOTH", paths=None, execute=False)` | Planeja fontes elegíveis; `execute=False` é o padrão seguro | Prévia; execução bloqueada no índice ativo |
| `codebridge_search_context(query, project, top_k=10, source_types=None, path_filter=None, branch=None)` | Busca lexical e semântica com procedência | Leitura |
| `codebridge_get_context(...)` | Recupera chunks autorizados por identificadores dentro de um projeto | Leitura |
| `codebridge_rag_generation_probe()` | Diagnóstico da geração RAG | Diagnóstico; disponibilidade varia |
| `codebridge_rag_integrity()` | Diagnóstico de integridade RAG | Diagnóstico; disponibilidade varia |
| `codebridge_rag_queue_bootstrap(...)` | Rotina de preparação da fila incremental RAG | Experimental/restrita; não equivale a publicar |

Para parâmetros adicionais, campos de resultado e versões específicas, consulte `codebridge_capabilities`, a descrição exposta pelo MCP e `author_mcp/mcp_server.py`. Os três últimos métodos RAG de diagnóstico/fila estão declarados no código, mas não foram disponibilizados na conexão ChatGPT utilizada nesta atualização.

### Exemplos de chamadas

Exemplos ilustrativos da chamada de ferramentas MCP (o JSON representa **argumentos**, não um comando de terminal).

**Estado e recursos**
```json
{}
```
Ferramenta: `codebridge_status` ou `codebridge_capabilities`.

**PowerShell — comando simples**
```json
{"target":"POWERSHELL5.1","command":"Get-Date","wait_timeout_ms":1500,"output_mode":"NORMAL"}
```
Ferramenta: `codebridge_exec`. Um retorno `RUNNING` contém `execution_id`; use esse ID em `codebridge_wait`, sem iniciar uma segunda execução.

**CMD**
```json
{"target":"CMD","command":"ver","wait_timeout_ms":1500}
```
Ferramenta: `codebridge_exec`.

**SSH Linux**, somente se conectado
```json
{"target":"SSH","command":"uname -a"}
```
Ferramenta: `codebridge_exec`. Consulte os alvos efetivamente aceitos com `codebridge_capabilities`.

**Preparar / executar**
```json
{"target":"POWERSHELL5.1","command":"Get-Location"}
```
Ferramenta: `codebridge_prepare`. Com o `prepared_request_id` recebido:
```json
{"prepared_request_id":"<ID retornado pelo prepare>"}
```
Ferramenta: `codebridge_execute_prepared`. Para desistir, use `codebridge_discard`.

**Consultar saída ou interromper**
```json
{"execution_id":"<ID retornado pelo exec>","wait_timeout_ms":15000,"output_mode":"RAW"}
```
Ferramenta: `codebridge_wait`. Para cancelar, chame `codebridge_stop` com o mesmo `execution_id`.

**Buscar conhecimento**
```json
{"project":"codebridge","query":"Onde está implementada a recuperação do supervisor?","top_k":5}
```
Ferramenta: `codebridge_search_context`.

**Planejar inclusão de arquivo, sem publicar**
```json
{"project_id":"codebridge","project_root":"C:\\Users\\Matheus\\CodeBridge-MCP-Bridge","scope":"TEXT","paths":["docs/CURRENT_SYSTEM.md"],"execute":false}
```
Ferramenta: `codebridge_rag_index`.

### Ferramentas antigas (não priorizar)

Os nomes `codebridge_ping`, `codebridge_terminal`, `codebridge_start`, `codebridge_execution_status` e a família `codebridge_v2_start/status/result/output/stop` aparecem no catálogo de migração/compatibilidade. Para novas integrações, priorize `codebridge_status`, `codebridge_capabilities`, `codebridge_exec`, `codebridge_wait` e `codebridge_stop`.

## RAG local — recursos e limites

**Pilha:** modelos `jinaai/jina-embeddings-v5-text-small` (documentos) e `jinaai/jina-code-embeddings-1.5b` (código); índice lexical SQLite FTS5/BM25 e vetores Qdrant local. O sistema combina recuperação lexical/vetorial e apresenta trechos com arquivo, linhas, commit, hashes e informação de atualização quando disponível.

**Último estado observado (24/10/2026):** geração `v1_delta_1ae1d01ea84f4e`, 211 documentos, 8.774 chunks; última indexação em **09/10/2026**. Esses números são um retrato, não valores fixos do produto. Modelos podem estar instalados, mas descarregados até uma consulta; há política de fallback CPU conforme o ambiente.

**Interface de conhecimentos:** Meus arquivos, Pesquisar e Adicionar. O código da branch contém seleção de pasta e de arquivos individuais/múltiplos, prévia e revisão simulada. A seleção individual foi copiada para a instalação Windows, mas precisa de reinício da interface para ser vista na sessão já aberta.

**Escrita:** o planejamento reconhece novos arquivos, mas o botão de publicar permanece desabilitado. Não existe garantia certificada de inclusão, edição e remoção incremental no índice público. Estão em desenvolvimento: admissão segura de fontes (identidade/origem/aprovação), writer incremental, validação SQLite/Qdrant/manifest, troca atômica de geração, leitores MCP consistentes, rollback e integração explícita de arquivos anexados ao chat. Um upload no ChatGPT **não é transferido automaticamente** ao computador Windows.

**Precisão:** consultas reais funcionam, porém não anunciar uma taxa de acerto sem benchmark reproduzível. Para informações alteradas após a última indexação, confira os arquivos atuais no repositório.

## Segurança operacional

- Use `codebridge_rag_index(..., execute=False)` para prévia. A autorização de novas fontes é individual; não contornar os bloqueios de publicação.
- O terminal tem acesso às permissões do usuário conectado: revise comandos que apagam, instalam, alteram sistema ou usam segredos.
- Não exponha API keys, tokens, configurações de túnel nem credenciais em commits, logs ou anexos.
- Antes de editar ou publicar, confira Git, hashes e evidências de teste; commits e auditoria pós-commit são exigidos no fluxo de desenvolvimento.
- A fase P9-B/NSIS possui ensaios de rollback isolados, **não** liberação de atualização da instalação ativa.

## Instalação e atualização Windows

Há instalador e atualizador em `installer/`; consulte [documentação de implantação](docs/DESKTOP_DEPLOYMENT_CURRENT.md) e [installer/build_installer.ps1](installer/build_installer.ps1). As rotinas incluem instalação de runtime isolado, componentes do túnel e configuração da conexão. A documentação/artefatos de instalador não substituem os gates de release ainda pendentes.

```powershell
.\installer\build_installer.ps1 -InstallNSIS
```

**Atenção:** esse é o comando documentado do build histórico; confirme os parâmetros suportados pela revisão atual do script e o resultado das validações antes de distribuir o instalador. Não executar cutover P9-B até certificação e aprovação.

## Repositório e documentação

A documentação técnica **do sistema atual** está centralizada em [docs/INDEX.md](docs/INDEX.md). Ela inclui os contratos do MCP, executor, RAG, segurança, interface, implantação e recuperação.

- [Visão do sistema](docs/CURRENT_SYSTEM.md)
- [Executor MCP](docs/EXECUTION_RUNTIME_CURRENT.md)
- [Ferramentas MCP](docs/MCP_TOOLS_CURRENT.md)
- [Segurança e persistência](docs/SECURITY_AND_PERSISTENCE_CURRENT.md)
- [RAG e funcionalidades](docs/RAG_CURRENT.md)
- [RAG interno](docs/RAG_INTERNALS_CURRENT.md)
- [Interface desktop](docs/DESKTOP_FEATURES_CURRENT.md)
- [Instalação Windows](docs/DESKTOP_DEPLOYMENT_CURRENT.md)
- [Operação e recuperação](docs/OPERATIONS_AND_RECOVERY_CURRENT.md)
