# MCP de produção — Regressão real (2026-10-10)

## Base
Handoff: `CodeBridge_HANDOFF_MELHORIAS_MCP_PRODUCAO_2026-09-30.md`.
Branch: `rag-017-optimized-inference-after-candidate`.
O MCP local em `127.0.0.1:8765/mcp` publica 13 tools, incluindo `codebridge_exec`, `codebridge_wait`, `codebridge_capabilities` e ferramentas RAG. Catálogo exposto por esta conversa ainda inclui ferramentas legadas e requer sincronização externa.

## Validação por testes
- Ambiente correto: `author_mcp/.venv/Scripts/python.exe`.
- 31 testes MCP específicos aprovados.
- 56 testes da suíte `author_mcp` aprovados, com ResourceWarning de arquivos não fechados em testes.

## Execuções reais (não simuladas)
- PowerShell 5.1, execução longa com espera: `exec_161c2684bbaf11a1a51f376923230279`; `FINISHED`; exit `0`; cursor final `778`; RAW recuperado por wait; marcador inicial e final presentes.
- CMD, falha provocada (`cmd /c exit /b 7`): `exec_993a3c0a68168e5483fe770bdfa25100`; `FAILED`; exit `7`; cursor final `146`.
- SSH, saída grande (`seq 1 2200`): `exec_6a72b855380480d2902860d510a11aee`; `FINISHED`; exit `0`; primeiro retorno COMPACT `5771` caracteres, saída RAW recuperada por wait `12093` caracteres, cursor final `12093`.

O coletor de prova descartável `benchmarks/probe_mcp_prod_deep_live.py` é ignorado pelo Git conforme regras existentes; não incluído à força.

## Critérios satisfeitos
- `execution_id` persistente durante exec e wait.
- Cursor monotônico sem repetição de comando.
- Recuperação RAW mesmo após COMPACT.
- Status de falha e exit code nativo distintos de sucesso.
- Três targets exercitados.

## Pendências (não encerrar todos os marcos)
- O runtime retornou `stream_mode=COMBINED` e `streams_separated=false` nos testes anteriores; separação fiel de stdout/stderr ainda não comprovada.
- Falta matriz completa de timeout, cancelamento, retomada, Unicode, stderr grande e falhas de transporte.
- A publicação externa de tools no ChatGPT deve ser reconciliada com o catálogo local.
- Não modificar backup `Documents/CodeBridge_Recovery_20261010_103146`; preservar benchmark JSON preexistente fora do commit.

**Estado: regressão parcial aprovada; fechamento de produção continua pendente.**
