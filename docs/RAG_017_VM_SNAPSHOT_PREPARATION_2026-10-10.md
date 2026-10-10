RAG-017 — Preparação de evidência para rollback em VM (2026-10-10)

Get-ComputerInfo no MatheusPC: HyperVisorPresent=False; requisitos DataExecutionPreventionAvailable, SecondLevelAddressTranslation, VirtualizationFirmwareEnabled e VMMonitorModeExtensions=True. Isso indica recursos de hardware disponíveis, NÃO uma VM descartável iniciada e validada. A consulta administrativa Hyper-V continua sem confirmação.

Implementado `benchmarks/rag017_vm_snapshot_manifest.py`: ferramenta somente leitura para gerar manifest SHA-256 dos arquivos em diretório dedicado `CodeBridge-RAG017-VMTest-*`, recusando substituir manifestação existente. Mantém flags `registry_snapshot_verified=false`, `shortcuts_snapshot_verified=false`, `services_snapshot_verified=false`, `vm_snapshot_verified=false`, pois não captura esses componentes.

O manifesto é auxiliar para futura auditoria em VM, não é um snapshot da máquina nem mecanismo de restauração. Instalação integral e rollback ainda não testados. CodeBridge principal e porta 8765 preservados; RAG-017-J BLOCKED.
