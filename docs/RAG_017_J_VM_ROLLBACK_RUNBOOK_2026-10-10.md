# RAG-017-J — Procedimento de rollback integral em VM descartável

Estado: **BLOCKED — execução real ainda não realizada**.

## Objetivo
Comprovar que uma instalação experimental NSIS do CodeBridge RAG é reversível em uma VM Windows descartável, sem alterações no host principal. A coleta e comparação atuais são direcionadas e **não** bastam para atestar rollback integral de registro, serviços, atalhos ou sistema operacional.

## Pré-requisitos (bloqueantes)
1. VM Windows separada, com identidade e hipervisor documentados. Não executar no computador físico principal.
2. Snapshot/checkpoint inicial criado e conferido no hipervisor, com identificador, data e log externos à VM.
3. Instalador de teste identificado por caminho, hash SHA-256 e commit de origem. Nunca reutilizar a instalação CodeBridge operacional.
4. Diretório isolado dentro da VM chamado `CodeBridge-RAG017-VMTest-<identificador>`, contendo **somente** conteúdo descartável.
5. Diretório para relatórios **fora** do diretório monitorado; preservar os relatórios fora do disco sujeito à restauração.
6. Revisão específica dos efeitos do NSIS no escopo registro, atalhos, serviços, desinstalador, diretórios compartilhados e usuário. Não usar a máquina principal como plano B.
7. Garantir que a VM não alcança credenciais, túneis ou serviços de produção durante o experimento.

## Sequência controlada
1. Registrar `vm_id`, versão Windows, recursos alocados e checkpoint original por ferramenta do hipervisor.
2. Dentro da VM limpa, executar `python -m benchmarks.rag017_vm_windows_inventory --vm-id <ID> --root <DIRETORIO_VM> --out <BEFORE.json>`. Os relatórios devem ficar fora da pasta monitorada.
3. Persistir `BEFORE.json` e o log do hipervisor **fora** da VM; conferir hashes.
4. Executar instalador experimental **somente dentro da VM**, documentando stdout/stderr, códigos de saída e alterações observadas.
5. Registrar evidência do ambiente instalado e testes funcionais separados (sem confundir com evidência do estado restaurado).
6. Desligar a VM e restaurar o checkpoint **pelo hipervisor**, guardando os logs e identificadores da operação.
7. Reiniciar a VM restaurada e executar novamente o coletor com o mesmo `vm_id` e raiz, saída `AFTER.json`; exportar relatório.
8. Comparar `python -m benchmarks.rag017_vm_evidence_compare --before <BEFORE.json> --after <AFTER.json>`.
9. Analisar os diffs, registros, atalhos, serviços, escopo externo ao diretório de teste, rastros de instalação e confirmação independente do hipervisor.
10. Só mudar o estado de RAG-017-J após auditoria humana dos artefatos reais. Nenhum flag `vm_snapshot_verified` deve ser marcado manualmente sem evidência externa verificável.

## Regras de aprovação
- `comparison_passed` é uma **comparação de dados**, não comprovação do rollback integral.
- O comparador propositalmente mantém `rollback_full_verified: false`.
- A coleta atual marca `*_inventory_collected` como concluídos quando realizada, mas mantém `*_snapshot_verified: false`; não inventar completude.
- Se houver qualquer alteração persistente fora do checkpoint ou lacuna de cobertura, a fase permanece **BLOCKED**.
- Preservar o arquivo de benchmark preexistente `benchmarks/rag017_code_only_extended_smoke.json` sem inclusão acidental em commit.

## Diagnóstico do host em 2026-10-10
Windows 11 Pro, 7,73 GiB RAM total, aproximadamente 2,1 GiB livre, espaço C: aproximadamente 259,5 GiB, virtualização de hardware disponível, comandos de Hyper-V ausentes. Nenhuma VM utilizável foi identificada nas verificações locais comuns. **Não** instalar Hyper-V/VirtualBox, executar NSIS, reiniciar host ou encerrar CodeBridge como parte deste procedimento documental.
