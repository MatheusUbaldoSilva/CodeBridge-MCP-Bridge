# RAG-017 — Consolidação de evidências antes do gate

Foi gerado `benchmarks/rag017_release_evidence_summary.json` a partir dos relatórios experimentais versionados de qualidade Code-only, latência warm, memória de processos, VRAM e recuperação concorrente. Script reexecutável: `benchmarks/summarize_rag017_release_evidence.py`.

O sumário **não certifica produção**, explicitamente `release_approved=false`. Principais bloqueios: (1) holdout independente elaborado/revisado externamente, (2) avaliação de ponta a ponta no serviço instalado, (3) limites de RAM/VRAM e p95 representativos em operação real. Os dados de qualidade conhecidos participaram dos ajustes; a medição de recursos é amostrada; uma das requisições do teste concorrente falhou antes da recuperação do modelo.

Não foi modificado o ranking, modelo, índice, a tag de referência dual `rag-017-candidate-cross-route-quality-20261009` nem os limiares de aprovação. A alteração local anterior em `benchmarks/rag017_code_only_extended_smoke.json` permanece fora dos novos commits. Próximo passo é uma revisão humana independente antes da primeira consulta no holdout e, em paralelo, testes integrados em ambiente isolado.
