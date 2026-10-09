# RAG-017 — Execução cega de perguntas congeladas

`benchmarks/run_rag017_blind_predictions.py` é o runner experimental de predições para um futuro holdout independente. Recebe `--questions`, `--predictions`, `--manifest` e `--sha256`; exige o SHA-256 previamente congelado, valida IDs e consultas, recusa sobrescrever artefatos existentes e **não abre o arquivo de labels**. Escreve caminhos ranqueados e manifesto com hashes, rota e contagem; usa apenas a variante Code-only experimental e fecha o pool e cliente Qdrant ao terminar.

O runner **não cria perguntas independentes nem certifica autoria ou revisão de anotações**. O conjunto de perguntas precisa ser preparado e congelado por revisor independente, sem reutilizar RAG-014 ou o shadow-20. Só depois executar predições, verificar manifesto, revisar labels e passar `evaluate_holdout`. Um hash de perguntas é requisito necessário, não garantia isolada de independência ou ausência de vazamento.

Limites de qualidade permanecem Recall@5>=0,80, Recall@10>=0,90, MRR>=0,60. Até o holdout e a validação completa da integração serem aprovados, `production_approved=False` e **RAG-017-J BLOCKED**. Tag candidata dual `rag-017-candidate-cross-route-quality-20261009` preservada. Nenhuma ativação em produção.
