# CodeBridge DEV — Correção de encerramento automático do turno
Data: 2026-10-30

## Diagnóstico
O servidor local continuava em RUNNING/WRAP_UP_NOW após finalizar a resposta do ChatGPT. WRAP_UP_NOW é instrução, não transição de estado. O endpoint /v1/chatgpt/timer/finish funciona quando chamado com request_id.
Durante a auditoria: /v1/extension/status retornou connected=false. Sem a extensão ativa, o aplicativo não observa o fim do streaming da página.

## Patch
- background.js: consulta /v1/chatgpt/timer para obter o request_id atual; finalização/cancelamento só com identificador explícito.
- content.js: sincroniza o identificador observado, encaminha finish/cancel para aquele turno e tenta novamente quando há falha no evento; nunca envia finalização para outro ID.
- Mantém detecção visual do botão Parar; não utiliza temporizador que conclui artificialmente um turno ainda gerando texto.
- O servidor HTTP e Stable não foram alterados.

## Testes e limite operacional
- node --check background.js e content.js: PASS
- tests/test_chatgpt_companion.py: 15 PASS
- Extensão não conectada durante auditoria. Necessário recarregar a extensão no navegador e comprovar heartbeat + transição RUNNING -> FINISHED com uma resposta real.
- Não houve mudança em produção, nem instalação automática da extensão.
