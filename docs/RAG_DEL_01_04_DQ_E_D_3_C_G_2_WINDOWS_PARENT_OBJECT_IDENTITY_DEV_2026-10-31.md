# RAG-DEL-01.04-DQ-E-D-3C-G-2 — Identidade do objeto Win32 pai (DEV)

## Escopo implementado
O modulo knowledge_deletion_parent_identity_lab.py vincula o IPC simulado a PID declarado, FILETIME exato de criacao observado pelo kernel Windows, estado ativo e um HANDLE do MESMO processo aberto por toda a chamada. A verificacao rejeita FILETIME incorreto, PID inexistente, nao-decimal ou do proprio worker, e fecha o handle em saidas normais ou por erro. O parent de laboratorio informa a criacao de seu processo junto com o PID ao iniciar o entrypoint real isolated_project_worker em modo --pinned-scratch-supervised. A funcao de liveness observa o handle persistente sem reabrir por PID, evitando associar a sessao a outro processo se o numero PID for reciclado.

## Descoberta relevante / limite deliberado
No runtime de CodeBridge, Python usa um redirecionador do ambiente virtual. Na auditoria, o Python chamador de subprocess.run apresentou PID 5812, enquanto o Python filho reportou PPID 15868 (o redirecionador). Exigir que os dois IDs fossem iguais recusou filhos legitimos. Essa hipoteses de parentesco direto foi removida, NAO relaxada silenciosamente: agora apenas se afirma identidade consistente do objeto de processo indicado com PID + nascimento Win32. Nenhum desses dados, mesmo quando conferidos, autentica o originador do pipe ou substitui um canal autenticado. O modo continua restrito a raiz TemporaryDirectory e nao recebe capacidade operacional de exclusao.

## Testes
3 testes novos no pacote supervisionado, alem dos 15 anteriores: roundtrip de identidade e hora de nascimento entre Python pai e filho, recusa de datas/IDs adulterados, entrada real do worker recusando birth FILETIME incorreto. Suite dirigida 18 PASS.
Regressoes: RAG-DEL 435 (429 PASS, 6 SKIP); RAG-AUTO non-MCP 241 (236 PASS, 5 SKIP). Total 676, 665 PASS, 11 SKIP, zero falhas.
Observacao: diagnostico de PPID do redirecionador e exploratorio, nao constitui prova de criacao trusted nem validacao de autenticação.

## Bloqueios persistentes
Nenhuma integracao com modelos reais ou Qdrant transacional, nenhuma mudanca em MCP/GUI instalado, Stable, indices, journal, fila real, GitHub ou habilitacao de delecao. A etapa seguinte deve avaliar um mecanismo de canal autenticado por handle herdado ou canais IPC com protecao adequada, em DEV e sob aprovacao, antes de chamar o supervisor operacional de seguro. Os gates READY_FOR_REVIEW, reconciliation de journals e generation_probe instalado permanecem pendentes.