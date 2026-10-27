# RAG-AUTO-05 — Roadmap DEV
Data: 2026-10-26
Estado: EM DESENVOLVIMENTO; somente dev-local; sem push.
05-A — Delta SHA-256: contrato e testes unitários implementados.
05-B — Job aprovado e geração verificada: contrato e testes unitários implementados.
05-C — Reuso potencial por manifesto: contrato e testes unitários implementados.
05-D — Validação de payload e dimensões TEXT/CODE: contrato e testes unitários implementados.
05-E — Cópia real de vetores, isolamento, checkpoints e rollback: PENDENTE.
05-F — Testes Jina reais, regressão integral, GUI, commit local, pós-commit: PENDENTE.
Não houve cópia real de embeddings, promoção de índice público ou alteração da Stable.
Preservar três pendências Git antigas; nenhuma subfase isolada é considerada fechada.
05-E preflight: plano inerte de reuso/remoção/novos embeddings implementado e testado; transferência real ainda PENDENTE.
Regressão: 31 testes RAG-AUTO-05 PASS; 151 testes RAG/Qt (149 PASS, 2 SKIP), 5 MCP PASS em ambiente próprio.
Três pendências anteriores preservadas; não houve commit ou push.
Não autorizar reuso, publicação nem modificação do índice público nesta fase.
05-E laboratório: importação Qdrant Local em lote single-model (max 256), lock exclusivo, recibo com fsync/rename, leitura/revalidação após gravar e recusa de replay. Testes em diretórios temporários PASS.
NÃO é ativação operacional: o executor requer Qdrant destino já isolado e aprovado pelo chamador; faltam fencing integrado, rollback seguro após crash e extensão de staging ao ciclo de jobs aprovado.
Não foi acionado Jina; nenhum vetor de produção, geração pública ou Stable foi acessado nesta validação.
05-E: importação Qdrant REAL testada entre duas bases temporárias e em staging oficial de job QUEUED aprovado, com vetor sintético e revalidação de checksum/ID/dimensões.
Particionamento determinístico por coleção TEXT/CODE, máximo 256 vetores por lote; lock exclusivo no staging, recibo fsync + rename, detecção de ponto já existente e corrupção após checkpoint.
Regressão RAG/Qt executada em 2026-10-26: 189 testes, 187 PASS, 2 SKIP (symlink Windows), 0 FAIL.
PENDENTE 05-F: execução Jina real, retomar após crash, rollback da geração isolada, integração ao agendador e revisão final Git. Sem commit/push.
Sessão de continuação: adaptador job QUEUED aprovado, origem de geração-base verificada, particionamento <=256 single-model, exclusividade por lock, recibo, leitura e verificação de Qdrant implementados.
Testes atuais: 195 testes RAG/Qt (193 PASS, 2 SKIP), 66 testes específicos RAG-AUTO-05 PASS, 5 MCP anteriormente PASS.
Limites: não existe integração automática do scheduler, recuperação destrutiva/rollback homologado, nem end-to-end real com Jina. Não marcar fase 05 concluída.
Branch dev-local e HEAD 05d0147 inalterados. Nada de commit/push; pendências antigas preservadas.
RAG-AUTO-05-F — 2026-10-26: fencing real do supervisor validado, lock semântico integrado e token de lease validado antes/depois da operação.
Prova de compatibilidade com o SQLite oficial: candidate pre-write exige content,document_id,project_id,source_type,path,SHA256 iguais; o inventário nativo do estágio confirmou o vetor importado.
Prova Jina CODE opt-in executada sob lock semântico: modelo Jina Code 1.5B CUDA gerou embedding real apenas na origem; staging candidato reutilizou sem re-embedding; inventários de ambas as filas aprovaram os vetores.
Regressão 206 testes RAG/Qt (203 PASS, 3 SKIP), 0 FAIL; canário Jina opt-in separado PASS. NENHUM processo llama-server remanescente.
PENDÊNCIAS PARA FECHAR RAG-AUTO-05: entrada no scheduler, recuperação automática segura com fencing pós-crash, caso TEXT CPU real, verificação de GUI, revisão integral diff/commit apenas local e pós-commit.
Stable, ponteiro público, GitHub e as três pendências anteriores preservados.
Checkpoint RAG-AUTO-05-F adicional: supervisor real com renew fencing pre/post + production semantic lock PASS; SQLite oficial exige correspondência exata antes da escrita.
Canário Jina Code CUDA real PASS sob lock semântico: embedding calculado apenas na base temporária original e reutilizado no staging secundário aprovado sem nova inferência; inventários oficiais de ambos validaram.
Regressão consolidada: 207 testes RAG/Qt, 204 PASS, 3 SKIP (Jina opt-in excluído da regressão normal + 2 permissões symlink Windows), 0 FAIL. Jina opt-in executado separadamente PASS.
Fase RAG-AUTO-05 NÃO FECHADA: faltam scheduler/heartbeat integrado em produção DEV, rollback após crash, TEXT CPU, revisão de diff/commit e pós-commit. Nenhum push ou promoção pública.
Continuação RAG-AUTO-05-F: entrada supervisionada opt-in exige confirmação por job, versão pinada TEXT/CODE, prepara staging isolado, reserva e libera supervisor com fencing.
Lease heartbeat periódico entre 1 e 60 segundos durante transferência; perda do fencing impede retorno de sucesso e exige auditoria.
Quarentena não destrutiva após job PAUSED/FAILED/CANCELLED, com confirmação específica e proibição de lease ativo; teste com fila e staging SQLite/Qdrant reais PASS.
Canário Jina TEXT CPU escrito e validado como opt-in; não executado devido RAM livre abaixo de 3000 MiB. Prova Jina CODE real da sessão anterior permanece aprovada.
Regressão 223 testes (219 PASS, 4 SKIP, 0 FAIL); 4 skips incluem 2 symlink Windows e 2 canários opt-in.
Ainda pendente: homologação TEXT CPU quando RAM disponível, validação GUI e diff final/commit local/pós-commit. Sem push, sem geração pública, sem mutação da Stable.
Continuação RAG-AUTO-05-F: heartbeat supervisor 20 s durante transferências, validação fencing pré/pós, sem sucesso se lease perdido.
Novo runner supervisionado opt-in: confirmação RAG_AUTO_INCREMENTAL_RUN por job, modelos TEXT/CODE oficiais pinados, reserva única, staging aprovado, controle de geração pública e liberação obrigatória do lease.
Rollback conservador opt-in: apenas job PAUSED/FAILED/CANCELLED, sem lease ativo, renomeia staging para quarentena sem apagar; teste de fila/staging reais PASS.
Proteção de RAM abaixo de 1600 MiB devolve WAITING_FOR_MEMORY sem worker; canário TEXT CPU opt-in recusado com RAM abaixo de 3000 MiB para preservar Stable.
Regressão 225 testes RAG/Qt, 221 PASS, 4 SKIP, 0 FAIL. Permanecem pendentes TEXT CPU real, homologação do scheduler automático, GUI e auditoria Git final.
Nenhum commit novo nem push; head dev-local 05d0147; Stable e índice público intocados.
Continuação final: quarentena agora requer estado demonstrável NOT_RESERVED; lease apenas expirado ou desconhecido não autoriza mover SQLite/Qdrant.
Transferência end-to-end validada com geração-base verificada e candidato aprovado reais: recibo, staging, Qdrant, fencing e checkpoint oficial levam job completo a READY_FOR_REVIEW sem publicar.
Pós-cópia reabre Qdrant do candidato e revalida recibo e pontos antes de declarar sucesso; teste de corrupção bloqueia retorno de sucesso.
Falha de checkpoint após BEGIN RUNNING tenta reconciliar como PAUSED pelo mesmo token, sem sobrescrever lease estrangeiro.
Prova de falha real entre upsert e checkpoint: stage colocado em quarentena sem perda de vetor, lock preservado.
Regressão 230 testes RAG/Qt, 226 PASS 4 SKIP 0 FAIL; finalização fase 05 segue pendente de Jina TEXT CPU por RAM insuficiente, GUI de ponta a ponta e auditoria/commit local.
Última rodada AUTO05-F: quarentena agora recusa lease expirado/desconhecido, aceita exclusivamente NOT_RESERVED comprovado.
Após a cópia, Qdrant destino é reaberto e o recibo é confrontado com os vetores reais; falha de verificação bloqueia sucesso.
Integração ponta a ponta REAL de laboratório: baseline imutável verificado -> segundo job aprovado -> runner supervisionado com fencing -> transferência -> verificação Qdrant -> checkpoint oficial READY_FOR_REVIEW. Tentativa de segunda execução do mesmo job é recusada.
Falha simulada de disco após upsert deixa lock, e quarentena preserva o vetor; falha de persistência após RUNNING tenta checkpoint PAUSED.
Validação: 230 testes gerais RAG/Qt (226 PASS, 4 SKIP), 101 testes AUTO05 (99 PASS, 2 opt-in SKIP), 5 MCP PASS. 45 arquivos AST válidos.
Não fechar ainda: Jina TEXT CPU opt-in não executado pela RAM abaixo de 3000 MiB, e revisão final e commit do marco ainda dependem de homologação.
Auditoria adicional de segurança: staging raiz redirecionado agora recusado antes da abertura de Qdrant; JSON de recibo maior que 16 KiB, schema inválido, bool e lote acima de 256 são rejeitados.
Inspeção de recuperação: artefatos simbólicos são REDIRECTED_RECOVERY_ARTIFACT, e checkpoint presente sempre exige auditoria/leitura Qdrant antes de retomar; auto_retry permanece sempre False.
Prova de estabilidade: 12 testes reais com fila/Qdrant temporários (6 full-supervised e 6 crash/quarantine) PASS; painel Qt nativo Windows: 17 testes PASS; regressão geral anterior 232/227 PASS/5 SKIP.
Requisito de homologação: validar Jina TEXT CPU somente quando RAM disponível >=3000 MiB; manter DEV sem commit/push até fechamento.
Rodada de auditoria adicional: 45 arquivos Python AUTO05 revisados sintaticamente; sem espaços em fim de linha.
Proteções adicionadas: symlink/junction no staging raiz proibido, recibo durável limitado a 16KiB, contagem integer verdadeira <=256 e schema v1 validado no readback.
Leitor Qdrant recusa recibos malformados ou declarados previamente autorizados; recovery detecta symlinks em lock/recibo e requer auditoria manual mesmo após checkpoint válido.
Regressão 236 testes RAG/Qt, 231 PASS, 5 SKIP, 0 FAIL. Suíte AUTO05 107 testes, 104 PASS, 3 SKIP, 0 FAIL. Qt Windows nativo 17 PASS.
Stress de laboratório: 40 execuções adicionais Qdrant Local/staging aprovadas. Ainda não foi carregado Jina TEXT CPU (RAM < 3000 MiB).
Sem push, sem commit, sem alteração do ponteiro público; preservar três pendências antigas no Git.
Proteção nova: quarentena adquire lock semântico EXCLUSIVE, relê estado do supervisor sob lock e recusa movimentação se nova reserva apareceu.
Teste de corrida (lease NOT_RESERVED antes, LEASE_RECORDED dentro do lock): PASS, estágio mantido intacto.
Regressão geral após a correção: 237 testes, 232 PASS, 5 SKIP, 0 FAIL. Sem Jina TEXT CPU porque RAM abaixo 3000 MiB.
Atualização de fase permanece somente na dev-local. Ainda não commitar nem fazer push.
Continuação de homologação: quarentena relê job/state/caminho dentro do lock semântico; mudança concorrente PAUSED->RUNNING cancela movimentação.
Runner supervisionado aceita batch_index não-negativo explícito, propaga pelo fencing até partition_reuse_receipt, limite até 256 por lote.
Canário end-to-end com coleção TEXT e CODE, dois lotes de max_vectors=1, estado QUEUED após primeiro e READY_FOR_REVIEW após segundo; reuso preserva IDs sem reembedding.
Teste de estabilidade 10 repetições do fluxo multi-lote TEXT/CODE + 5 crash/quarantine: 15 PASS.
Regressão antes da extensão do batch index: 238 testes, 233 PASS, 5 SKIP, 0 FAIL. Ainda falta rodada final após a extensão.
Jina TEXT CPU não forçado: RAM abaixo 3000 MiB. Sem commit/push, Stable e ponteiro público preservados.
Sessão de continuidade: runner e executor fenced agora recebem batch_index explícito e validam inteiro >=0 antes do trabalho.
Canário real de laboratório: origem verificada com TEXT/README.md + CODE/single.py; duas operações de max_vectors=1 no candidato; primeira retorna QUEUED, segunda READY_FOR_REVIEW. IDs preservados, sem geração pública ativada.
batch_index=99 inválido negado antes da cópia, estado do job permanece QUEUED, após isso os lotes 0 e 1 continuam executáveis.
Provas: 241 testes gerais (236 PASS, 5 SKIP); 112 AUTO05 (109 PASS 3 SKIP); 5 MCP PASS; repetição 15 canários multi-lote/crash PASS.
Quarentena recusa corrida de estado do job sob lock semântico. RAM livre segue abaixo de 3000 MiB; Jina TEXT CPU opt-in não executado. Nenhum commit ou push.
Decisao de fechamento 2026-10-26: usuario dispensou provisoriamente o canario Jina TEXT CPU real; fica expressamente PENDENTE POS-FECHAMENTO, sem alterar o resultado do teste nem declarar PASS. Bugs posteriores exigem patch note e revisao.
