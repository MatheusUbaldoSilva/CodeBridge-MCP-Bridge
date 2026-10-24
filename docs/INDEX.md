# CodeBridge — documentação oficial

Esta pasta descreve **o software existente na branch atual**: componentes, interfaces, responsabilidades, comportamento e limites. A fonte de verdade é o código versionado e o estado informado pelos serviços em execução.

## Navegação

| Documento | Conteúdo |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Componentes, processos e comunicação |
| [MCP_TOOLS.md](MCP_TOOLS.md) | Catálogo MCP e exemplos de argumentos |
| [EXECUTOR.md](EXECUTOR.md) | Terminais, ciclo da execução e cancelamento |
| [RAG.md](RAG.md) | Consulta de conhecimentos e gestão de fontes |
| [RAG_INTERNALS.md](RAG_INTERNALS.md) | Índices, modelos, ranking e gerações |
| [DESKTOP_INTERFACE.md](DESKTOP_INTERFACE.md) | Janelas, terminal, telemetria e controles |
| [SECURITY.md](SECURITY.md) | Autenticação, permissões, segredos e isolamento |
| [STORAGE.md](STORAGE.md) | Dados persistentes, ledger, configuração e índices |
| [INSTALLATION.md](INSTALLATION.md) | Empacotamento e instalação Windows |
| [CONFIGURATION.md](CONFIGURATION.md) | Configurações, SSH, túnel e diagnósticos |
| [RECOVERY.md](RECOVERY.md) | Recuperação do executor, RAG e atualização |

## Estado de uma funcionalidade

- **Implementada:** existe no código. Não significa que está disponível nesta conexão.
- **Operacional:** o serviço respondeu a uma verificação real.
- **Condicional:** exige configuração, acesso ou serviço externo.
- **Bloqueada:** o código impõe uma condição de segurança que impede uso operacional.
- **Não certificada:** não há prova suficiente para publicar ou atualizar a instalação de produção.

Consulte o [README principal](../README.md) para uma visão rápida. Esta documentação não contém cronologia de desenvolvimento; mudanças futuras devem atualizar o documento temático correspondente.