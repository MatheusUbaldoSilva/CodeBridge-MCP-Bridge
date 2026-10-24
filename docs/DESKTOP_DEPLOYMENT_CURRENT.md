# CodeBridge — Interface Windows, instalação e operações

## Aplicativo desktop

A interface Python/PySide6 apresenta terminais, telemetria e painel de conhecimento. O executor oferece PowerShell 5.1, CMD e SSH configurável. O controle do terminal e do MCP pertence ao runtime; a interface exibe estado e resultados.

O painel de conhecimento permite listar documentos já indexados, pesquisar trechos, selecionar pasta ou vários arquivos para prévia e ver detalhes do plano. A seleção de arquivos presente no código pode precisar de reinicialização na instalação Windows para aparecer.

## Serviços locais e conexão

- Servidor MCP autoral: `127.0.0.1:8765/mcp`.
- Adapter local: `127.0.0.1:8766`.
- Túnel seguro: canal `main` para o MCP local, conforme configuração do operador.

Serviços locais são loopback; não publicar as portas diretamente. O túnel não dispensa a autenticação do adapter e as autorizações pertinentes.

### Diagnóstico básico

1. `codebridge_status()`: confirmar `READY`, versões, estado do runtime e terminais.
2. `codebridge_capabilities()`: confirmar alvos, recursos e limites aceitos.
3. `codebridge_rag_status()`: inspecionar a geração RAG sem alterá-la.
4. Para execução real, use `codebridge_exec` com um comando não destrutivo e, se `RUNNING`, continue com `codebridge_wait`.

## Instalador e atualizador

O repositório contém `installer/CodeBridge.nsi`, `installer/build_installer.ps1`, `installer/bootstrap.ps1`, configuração guiada, rotinas de atualização e artefatos em `installer/dist/`.

Um build disponível no repositório não comprova que a atualização transacional está apta à produção. As funcionalidades de recuperação P9-B incluem componentes e ensaios isolados, mas o fluxo completo de supervisão, rollback e liberação de cutover não está certificado para alteração da instalação ativa.

O runtime instalado pode diferir do commit HEAD do repositório. Confirme versão, hashes e o funcionamento real antes de distribuir o instalador ou atualizar serviços.

## Dados locais e segurança

- Configurações de organização, túnel e autenticação devem permanecer fora do Git e de relatórios públicos.
- Os índices locais do RAG são persistidos sob a área de dados do usuário `AppData/Local/CodeBridge/rag` (caminho efetivo consultável via status).
- Não remover backups, geração RAG ativa, ledger ou tarefas agendadas sem inventário e teste de recuperação.
- Terminal pode executar ações com as permissões da conta Windows; confirme alterações de sistema, instalação e exclusão antes de chamar ferramentas de execução.

## Situação funcional

| Área | Estado |
|---|---|
| MCP e execução PowerShell/CMD | Implementados e observados online |
| SSH | Suportado; disponibilidade depende da conexão |
| Leitura do RAG publicado | Observada READY |
| Prévia de novas fontes | Implementada |
| Publicação incremental de fontes | Não liberada/certificada |
| Atualização NSIS transacional e recuperação supervisionada | Não certificada para produção |

Utilize documentação principal apenas para capacidades atuais; resultados de testes históricos não substituem o estado observado.
