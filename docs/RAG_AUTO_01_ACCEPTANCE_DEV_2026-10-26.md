# RAG-AUTO-01 — Aceitação técnica do controlador multiprojeto (DEV)

Data: 2026-10-26
Projeto: CodeBridge MCP Bridge / codebrige-mcp-rag
Branch: dev-local
Base antes da fase: be9ef504a175eb3ec5ee14978152c6aa3570e184
Escopo: RAG-AUTO-01.1 a 01.9 — contrato, persistência, prévia/aprovação, controles, card Qt e MCP.

## Definição de funcionalidade

O controlador RAG-AUTO-01 está funcional para preparar, autorizar, registrar,
listar, pausar, retomar e cancelar **trabalhos na fila**, inclusive pela GUI
e pelo MCP. O operador aprova exatamente um conjunto de fontes e hashes antes
de criar um job QUEUED. Consulta nenhuma cria DB/worker automaticamente.
O executor que efetivamente gera embeddings será implementado em RAG-AUTO-02,
não é parte deste fechamento.

Não confundir "fila QUEUED" com "indexação em execução". Sem worker RAG-AUTO-02,
nenhum botão anuncia falsamente que os modelos estão indexando.

## Entregas validadas por subfase

- 01.1 — Contrato e roadmap da automação e distinção entre índice canário e público
- 01.2 — SQLite transacional isolado com schema versionado, idempotência, WAL e eventos
- 01.3 — Inventário, política de exclusão, sha256 de cada fonte, aprovação explícita
- 01.4 — Reservation/lease único, heartbeat, fencing token e geração monotônica
- 01.5 — Pausar, retomar e cancelar com registro durável e proteção de checkpoint futuro
- 01.6 — Telemetria read-only; zero chunks retorna `--%` em vez de progresso inventado
- 01.7 — Card QT no layout do mockup preto com barra verde, botões de controle e rótulos reais
- 01.8 — Quarta aba na Central RAG, seleção de pasta e autorização, ferramentas MCP de prévia/status/aprovação/controle
- 01.9 — Contratos e GUI testados, aceitação de permissões, segurança, regressão, integração com MainWindow em QT offscreen

## Cenários de aceitação

1. Ler o status de uma fila inexistente NÃO cria arquivo no disco.
2. Planejar/aprovar um conjunto não publica índice, nem inicia modelos.
3. A aprovação exige clique afirmativo na GUI ou `execute`, `operator_approved` e token específico no MCP.
4. Alteração do arquivo depois da prévia invalida a autorização.
5. Duplicar a mesma autorização não cria trabalhos extras.
6. Concorrência na criação de jobs preserva atomicidade e idempotência.
7. Fonte sensível/fora do escopo não entra no conjunto aprovado.
8. Pausa e cancelamento invalidam reservas não iniciadas; alterações exigem nova revisão antes da retomada.
9. Heartbeat com token antigo é recusado.
10. Interface mostra estados reais sem progresso inventado; botões interagem com estado persistente em DB temporário.
11. MCP registra os quatro nomes das ferramentas no catálogo e nega mutações implícitas.
12. MainWindow carrega `RagPanel` com quatro abas, incluindo `Indexação automática`; serviços externos simulados no teste.
13. Nenhum indexador Jina ou banco de produção foi iniciado por importação, GUI de teste ou MCP de teste.
14. A geração pública RAG não foi trocada. No fim conferir `v1_delta_1ae1d01ea84f4e`.

## Testes

Os testes de controlador DEV passam via:
```powershell
$env:PYTHONPATH='C:\Users\Matheus\CodeBridge-MCP-Bridge;C:\Users\Matheus\CodeBridge-MCP-Bridge\app_rewrite'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:QT_QPA_PLATFORM='offscreen'
& 'C:\Users\Matheus\CodeBridge-Runtime\dev\Scripts\python.exe' -m unittest discover -s tests -p 'test_rag_auto_01_*.py' -q
```

O teste do MCP requer ambiente Python dedicado:
```powershell
& 'C:\Users\Matheus\CodeBridge-MCP-Bridge\author_mcp\.venv\Scripts\python.exe' -m unittest discover -s tests -p test_rag_auto_mcp_tools.py -q
```

Além dos novos testes foram rodadas regressões de busca MCP, status,
contexto, canário multiprojeto e prévia Qt.

Observação: teste de criação de symlink pode ser SKIP em contas Windows sem privilégio.
Não presumir sucesso do smoke de janela real até o usuário abrir a aplicação DEV e conferir a aparência.

## Artefatos operacionais fora do repositório

Prévia do QT:
C:\Users\Matheus\CodeBridge-RAG-Workspace\codebrige-mcp-rag\preview_RAG_AUTO_01_DEV.png

Handoff pré-parada (histórico):
C:\Users\Matheus\CodeBridge-RAG-Workspace\codebrige-mcp-rag\HANDOFF_RAG_AUTO_01_PRE_PARADA_GRACIOSA_2026-10-26.md

A indexação canário anterior permanece armazenada e não alterada.
O controlador novo NÃO utiliza o mesmo SQLite das filas instaladas do RAG V1.
Se o DB de produção do RAG-AUTO ainda não existe, isso é esperado: ele será
criado somente quando o usuário autorizar um primeiro trabalho real.

## Segurança e limites da publicação

- Atualizar o Git somente após revisão de todos os arquivos novos, diff --check e testes.
- Criar commit local de fechamento da fase no `dev-local`; não enviar ao GitHub até a automação completa e autorização.
- Nunca incluir os três arquivos preexistentes fora do escopo.
- Não ativar executor ainda, não substituir índice antigo.
- A ativação de canário de leitura do projeto de testes é independente do novo controlador.
- Futuro RAG-AUTO-02 deve consumir apenas jobs QUEUED e aprovações revalidadas,
  usar CODE ubatch 32, TEXT CPU, monitorar RAM livre e pausar nas bordas de lote,
  gravar progresso de fonte de verdade e validar vetores antes de marcar READY.
- A promoção de uma geração pública e rollback completo são responsabilidade do RAG-AUTO-03.

## Progresso estimado

RAG-AUTO-01 (controlador/GUI/MCP): 100% após aceitação dos testes e auditoria Git.
RAG-AUTO-COMPLETE (01 a 05, peso igual): 20%, pois 02-05 não estão concluídos.

Os percentuais expressam marcos planejados, não significam que a indexação
automática completa e atualização incremental já estejam disponíveis.
