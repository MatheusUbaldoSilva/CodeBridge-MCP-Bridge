# RAG V1.03-D — Fence de geração durável (laboratório)

Data: 2026-10-21. Base: `cb54cf1`.

`incremental_supervisor_fence.py` implementa contador monotônico SQLite em banco temporário dedicado `supervisor_fence.sqlite3`, versão 1, transações `BEGIN IMMEDIATE` e consulta read-only que rejeita identificadores antigos. A emissão exige indicação de lock externo, mas esta primeira versão **não comprova criptograficamente nem vincula essa indicação a um handle de lock**; portanto ainda não deve ser usada como fencing de produção. O próximo gate precisa acoplar diretamente a posse do lock à emissão.

Quatro testes locais cobrem ausência de habilitação, aumento após reabertura, recusa de banco estrangeiro e rejeição de token inválido. Sem worker, scheduler, arquivos públicos ou publicação de geração.
