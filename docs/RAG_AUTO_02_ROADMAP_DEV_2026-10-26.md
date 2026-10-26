# RAG-AUTO-02 — Worker de indexação automática (DEV)

Data: 2026-10-26
Base: RAG-AUTO-01 encerrado no commit a1ec581e732ea8b098e389e8695a243081d072d8
Estado inicial: EM DESENVOLVIMENTO, sem execução autônoma liberada
Branch: dev-local. Nenhum push GitHub antes de pacote comprovadamente funcional.

## Invariantes herdados

1. O job deve estar QUEUED com autorização de fonte registrada e hash revalidado.
2. No máximo um worker Jina no notebook (RTX 3050, VRAM 6GiB, RAM 8GiB).
3. A geração pública ativa NÃO é alvo de escrita (nem ponteiro, nem SQLite/Qdrant).
4. Staging novo por job, fora da pasta fonte e do diretório de geração pública.
5. Contadores de embeddings apurados do Qdrant persistido, jamais do contador Python.
6. CODE GPU CUDA0 ubatch32, lote inicial no máximo 256; TEXT em CPU.
7. Garantir ausência de modelo concorrente, checar RAM antes de lote e descarregar sempre.
8. Lease/fencing requer verificação antes e após cada checkpoint, heartbeat enquanto ocupa modelo.
9. Pausa/cancelamento só se confirma na fronteira segura entre lotes, sem apagar vetores.
10. Não há publicação pública no RAG-AUTO-02 (isso é o marco 03).

## Subfases

- RAG-AUTO-02.1: contrato de execução e gates de segurança
- RAG-AUTO-02.2: preparação de geração isolada (SQLite + FTS5 + manifesto + Qdrant)
- RAG-AUTO-02.3: processador por lotes CODE/TEXT, sem recalcular chunks já presentes
- RAG-AUTO-02.4: checkpoint/retomada, confirmação de pausa/cancelamento e fencing
- RAG-AUTO-02.5: limites RAM/VRAM e ligação à telemetria da fila
- RAG-AUTO-02.6: testes sintéticos e Jina real em projeto pequeno; auditoria diff/commit

## Fases de adoção

Começar com staging e testes de simulação, sem modelos carregados.
Executar embeddings reais apenas em teste pequeno, com autorização operacional e
controle de memória. Um job real de projeto grande requer aprovação do projeto
e execução deliberada; sem agendamento invisível.
Não reindexar automaticamente o CodeBridge real já validado de 11.385 vetores.

## Estado Git

Durante subfases, não commitar. Só fechar o marco com revisão diff, git check,
testes, commit local, auditoria pós-commit. Nenhum push para GitHub.
As três pendências existentes no DEV continuam intocadas.
