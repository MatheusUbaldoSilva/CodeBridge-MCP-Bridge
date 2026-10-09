# RAG-017 — Medição de recursos durante consultas Code-only

A branch experimental `rag-017-optimized-inference-after-candidate` foi executada com Jina Code residente e consultas submetidas a três threads. A primeira versão do teste dependia de `psutil`, não instalado, e coletou 0 amostras: descartada. O benchmark corrigido utiliza Windows `GetProcessMemoryInfo` via ctypes e `nvidia-smi` para GPU, sem dependência Python adicional.

Resultado: 28 amostras válidas, nenhum erro; GPU utilizada máxima observada **3204 MiB** em GPU com 6144 MiB; working set máximo observado do processo Jina Code **2017,1 MiB**. São snapshots periódicos, não máximo transitório garantido. O total de RAM da aplicação e de outros subprocessos não foi medido neste ensaio, portanto o teto de 6 GiB de RAM NÃO está comprovado. O crescimento real de VRAM deve ser considerado relativamente à linha de base, e permanece sujeito à qualificação completa.

A build dual candidata permanece preservada pela tag anotada `rag-017-candidate-cross-route-quality-20261009`. Gate de produção **BLOCKED**: ainda faltam holdout cego independente, p95 robusto sob carga, limite de RAM agregado e testes extensos de lifecycle/isolamento. O JSON de smoke alterado anteriormente permanece deliberadamente fora deste commit.
