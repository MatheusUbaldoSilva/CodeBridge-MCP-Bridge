# RAG V1.03-D — Callback com geração do supervisor

Data: 2026-10-21. Complemento sintético do contrato `da0ee3f`.

`transition` passou a exigir `expected_generation` nas confirmações `started`, `stopped` e `failed`. Sinais sem geração válida ou provenientes de tentativas antigas são recusados sem alterar o snapshot. Testes verificam callback antigo após reinício e ausência de token. Esse identificador lógico ainda não é uma trava interprocessos nem um fencing token persistente; os dois continuam pendentes.

Não inicia processo nem serviço e não toca no índice público.
