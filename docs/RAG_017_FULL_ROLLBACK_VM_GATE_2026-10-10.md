RAG-017 — Gate para rollback integral (2026-10-10)

Foi verificado o host Windows: comandos de gerenciamento Get-VM, VBoxManage.exe e vmrun.exe não foram encontrados na pesquisa de comandos; a consulta de recursos Hyper-V pelo Get-WindowsOptionalFeature exigiu elevação. Isso não comprova ausência de hipervisor, mas não há VM descartável verificada nesta execução.

O instalador principal `installer/CodeBridge.nsi` possui WriteRegStr, WriteRegDWORD, CreateShortcut, nsExec::Exec, WriteUninstaller e ExecWait. O novo verificador de código `benchmarks/rag017_full_rollback_preflight.py` retornou `side_effects_present=true`, `disposable_vm_verified=false`, `host_execution_allowed=false`, `rollback_full_test_allowed=false`, `rollback_full_verified=false`, exit code 2. Dois testes de preflight passaram.

O verificador não executa instalação, não prova a existência de VM, não implementa rollback e só inspeciona marcadores textuais de efeitos colaterais. Para teste integral: obter VM descartável, conferir snapshot inicial (incluindo registro, atalhos, arquivos, runtime, estado de serviço), testar atualização, falha e reversão com comparação pós-snapshot. Proibida a execução do instalador principal no Windows ativo. RAG-017-J segue BLOCKED.
