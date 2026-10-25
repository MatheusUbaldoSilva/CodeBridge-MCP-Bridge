# CB-LOCAL.05 — Validacao geral do CodeBridge 2.0

Data: 2026-10-25

## Decisao

**APROVADO para desenvolvimento local. NAO constitui autorizacao de publicacao remota, promocao stable ou homologacao de uma nova copia de recuperacao.**

A validacao da execucao local e da recuperacao bidirecional usa a infraestrutura do CB-LOCAL.01/02/04. A correcao de memoria do RAG na branch local dev-local foi testada e confirmada por MCP real.

## Evidencias reais

| Critério | Resultado |
|---|---|
| Inicializacao direta no Windows pelo launcher | PASS |
| Volta da candidata isolada para desenvolvimento | PASS, modo DEV PID 16420 e candidata encerrada normalmente |
| Handshake CBMCP/1 / API / estado | PASS, READY e API online |
| PowerShell 5.1 | PASS, comando CB05_DEV_PS_OK, exit 0 |
| CMD | PASS, comando CB05_DEV_CMD_OK, exit 0 |
| SSH Linux | PASS, comando CB05_DEV_SSH_OK, exit 0 |
| Fila de execucao | PASS, sem jobs pendentes |
| Indice RAG local | READY, sem reindexacao nesta fase |
| Pesquisa semantica TEXT | PASS, MCP result_count=3 e VECTOR_TEXT_COSINE presente |
| Pesquisa semantica CODE | PASS, MCP result_count=3 e VECTOR_CODE_COSINE presente |
| Jina Code GPU | PASS, 1536 dimensoes, vetor normalizado, fechamento limpo |
| Integridade do snapshot anterior | PASS, manifesto da candidata 14e875a com 983 checksums e selecao por commit correta |
| Testes automatizados direcionados | PASS, 39 testes (29 RAG + 10 launcher) |
| diff --check e pos-commit | PASS |
| Arquivos pendentes anteriores | Preservados, hashes invariaveis |
| GitHub | Intocado, sem push |

## Correcao de memoria RAG

Notebook em uso: 8 GiB RAM e RTX 3050 6 GiB. Erros anteriores dos modelos eram consistentes com pressao de RAM/VRAM e KV cache sem limite.

- Texto: commit `e1fc118`; limite de contexto 8192 e ubatch 512 para consultas.
- Codigo: commit `22e12d2`; contexto 2048, ubatch 128 e um slot paralelo para consultas, inclusive caminho residente.
- Modelo e indice do usuario NAO foram reinstalados, apagados, migrados ou reindexados.
- O teste CODE isolado carregou na GPU e retornou embedding com 1536 dimensoes e norma 1.0.
- O CodeBridge MCP retornou resultados vetoriais verdadeiros para ambas rotas apos os commits.

## Controle Git

- Repositorio: `C:\Users\Matheus\CodeBridge-MCP-Bridge`
- Branch: `dev-local`
- HEAD apos correcao de memoria: `22e12d20f9c77534d5e7bcfa7ca19a7a4604f773`
- Branch remota unica observada: `rag-017-optimized-inference-after-candidate` no commit `44af6e0bd367c6264e6f29c96fcba758908355cd`
- Arquivos preexistentes intocados:
  - `benchmarks/rag017_code_only_extended_smoke.json` (M)
  - `docs/RAG_017_J_VM_ROLLBACK_RUNBOOK_2026-10-10.md` (??)
  - `rag/runtime/incremental_installed_queue_init.py` (??)

## Limites do encerramento

CB-LOCAL.05 fica concluido para o **ambiente DEV local** e testes reais das rotas e terminais.

**CB-LOCAL.03 segue PENDENTE**: a promocao remota para `stable` requer aprovacao especifica do usuario, verificacao do HEAD remoto e estrategia sem force push. Nenhuma alteracao remota esta autorizada apenas por esta validacao.

A copia candidata da CB-LOCAL.04 continua fixada em `14e875a`, portanto **nao inclui** as correcoes posteriores de memoria TEXT e CODE. Ela foi homologada quanto a abertura, handshake MCP e terminais, mas **nao** como distribuicao final dessas novas correcoes. Para uma futura publicacao, preparar e testar um novo candidato do commit local final e obter aprovacao explicita, sem sobrescrever a candidata anterior.

## Resultado

Encerrar o marco CB-LOCAL.05 sem novas funcionalidades. O CodeBridge permanece aberto em DEV e o GitHub permanece inalterado.
