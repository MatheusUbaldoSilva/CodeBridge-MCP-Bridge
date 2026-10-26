# RAG-AUTO-03 — Aceitação técnica de geração verificada, canário e rollback

Data: 2026-10-26
Base: DEV local commit 6db33d5c9a878591e665391570a1ed168092aa18
Estado: aceitação validada; auditoria final Git para fechamento
Branch: dev-local
GitHub: NÃO PUBLICAR ATÉ RAG-AUTO-COMPLETE FUNCIONAL E AUTORIZADO.

## Contrato final

- 03.1 Auditoria: módulos test-only de geração não são usados para alterar a geração pública ativa. A migração legacy anterior não suporta este índice multiprojeto arbitrário.
- 03.2 Validação: job READY_FOR_REVIEW, fontes e recibos SHA256, SQLite integrity, FTS5, manifesto/IDs, Qdrant/payload e contagem cruzada.
- 03.3 Versão: índice isolado e snapshot dos arquivos autorizados copiados e comparados por hash antes de ficarem disponíveis; sem alterar o catálogo/ponteiro.
- 03.4 Catálogo isolado: registro `RAG_AUTO_03` compatível com o resolvedor multiprojeto preexistente; mantém formato legado de `source_revision` SHA Git de 40 caracteres para índices anteriores, enquanto os automáticos usam SHA256 de 64 caracteres.
- 03.5 Journal e reversão: backup exato do catálogo, mutação atômica, restauração do catálogo byte a byte, reativação após rollback e testes de interrupção antes/depois da gravação. Nunca excluir gerações.
- 03.6 GUI: três botões reais no painel de Indexação Automática com confirmação específica: Preparar versão, Habilitar leitura, Reverter habilitação. MCP: status e três mutações com gates `execute`, `operator_approved` e `confirmation`.

## Arquitetura

O canário é uma **geração de leitura isolada por projeto**, NÃO um novo active-generation global. Usa o mesmo mecanismo de busca/contexto do multiprojeto de CodeBridge-MCP-Bridge.

Diretórios de trabalho:
`<workspace>/auto/projects/<project_id>/generations/auto_<job_id>`
`<workspace>/auto/projects/<project_id>/snapshots/source_<job_id>`

Operações do módulo:
- `validate_reviewed_auto_generation`: somente leitura e validação.
- `prepare_verified_auto_generation`: cria geração imutável e snapshot aprovado.
- `verify_prepared_auto_generation`: confere SHA dos artefatos e fontes.
- `activate_auto_canary`: journal, backup e habilitação no catálogo multiprojeto.
- `rollback_auto_canary`: restaurar catalogo anterior; bloqueia mudanças externas concorrentes.
- `auto_index_promotion.py`: entry points do DEV com paths locais conhecidos e consentimento explícito.

Se houver erro entre criação de snapshot e geração, diretório parcial é preservado e requer auditoria manual. Falhas antes/depois da troca do catálogo têm journal e são reversíveis se as condições de segurança permanecerem iguais. O software se recusa a sobrepor registros de projetos existentes, inclusive o CodeBridge público.

## Ensaios reais e regressões

Real Jina (índice gerado no RAG-AUTO-02):
`C:\Users\Matheus\CodeBridge-RAG-Workspace\rag-auto02-canary-20261026`
- 2 arquivos, 2 chunks, 1 vetor TEXT e 1 CODE.
- Índice validado, fonte congelada em snapshot, geração copiada e revalidada.
- Ativação em catálogo de laboratório independente; recuperação real do trecho README.md pelo resolvedor multiprojeto.
- Reversão restaurou exatamente o catálogo de laboratório anterior.
- `active-generation.json` real preservado.

Testes de regressão executados após todas as alterações:
- RAG-AUTO-01 DEV: 55 (54 PASS / 1 SKIP)
- RAG-AUTO-02 DEV: 32 (31 PASS / 1 SKIP)
- RAG-AUTO-03 DEV: 26 PASS
- Regressões restantes DEV (busca, contexto, status, Qt, fallback, canário legado): 48 PASS
- Testes MCP dedicados: 12 PASS
- TOTAL: 173 executados, 171 PASS, 2 SKIP e 0 FAIL.
- AST de 23 arquivos Python auditados e válido.

Os dois SKIPs são testes de criação de symlink em contas Windows sem a permissão correspondente. O código que rejeita redirecionamento continua presente; os SKIPs não representam aprovação de uma exploração desse mecanismo.

## Proteções

- Nenhum `active-generation.json` de produção é escrito por este módulo.
- Nenhum projeto já cadastrado é sobrescrito.
- Registro isolado exige geração totalmente validada e snapshot imutável.
- SHA256 do SQLite, manifesto e recibo de geração são conferidos em cada resolução do projeto.
- Busca/get_context continuam validando a fonte congelada antes de devolver conteúdo.
- Rollback exige journal/backup íntegros, comparação com o catálogo ainda vigente e mesmo ponteiro público conhecido.
- Após habilitar e reverter, é possível habilitar novamente com o mesmo backup seguro, sem perder a versão anterior.
- Preparação e ativação não carregam modelos Jina.

## Limitações deliberadas

- **A troca da geração pública ativa não está implementada/liberada para estes projetos.** Precisa de contrato separado de migração entre formatos, teste de compatibilidade stable, backup da geração pública, travamento de leitores e aprovação expressa.
- O novo canário foi ativado apenas em catálogo temporário do laboratório; nenhum novo projeto automático foi registrado no catálogo real do usuário.
- Não se executou o novo RAG-AUTO completo sobre o corpus inteiro de 971 arquivos; usou-se um canário real de duas fontes.
- Testes QT foram offscreen. Ainda é recomendável inspecionar a tela no DEV após abrir o aplicativo.
- A cópia imutável é uma garantia lógica baseada em hashes e caminhos, não uma proibição de escrita por ACL; alterações posteriores falham nos validadores.
- Caso o usuário altere manualmente o catálogo após ativação, o rollback automático falha fechado e pede reconciliação manual, preservando dados.
- A fase RAG-AUTO-04 tratará de operação/observabilidade mais completa; RAG-AUTO-05 tratará de atualização incremental.

## Git e progresso

RAG-AUTO-01 = 100%; RAG-AUTO-02 = 100%; RAG-AUTO-03 = 100% **no escopo isolado acima**.
RAG-AUTO-COMPLETE = 60% de planejamento (3/5 grandes marcos, de peso igual), não adoção de produção.
Nenhum push GitHub nesta fase; ao final, commit LOCAL no dev-local com auditoria pós-commit, preservando pendências pré-existentes.
