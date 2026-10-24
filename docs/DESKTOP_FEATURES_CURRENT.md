# Interface desktop — funcionalidades atuais

**Aplicativo:** CodeBridge 2.0 - MCP Bridge, interface Windows em Python/PySide6. Este documento descreve componentes e funções da branch atual, não o histórico visual ou de versões.

## Estrutura da interface

| Módulo | Papel |
|---|---|
| `app_rewrite/main.py` e `ui.py::MainWindow` | Inicialização e composição da janela principal |
| `app_rewrite/terminal_widget.py::TerminalWidget` | Terminal interativo incorporado e ponte de sinais Qt |
| `app_rewrite/terminal_manager.py::TerminalManager` | Gerência das sessões, entrada, resize, preparação, execução, cancelamento e recuperação |
| `app_rewrite/windows_terminal_session.py` | Sessão PowerShell/terminal Windows |
| `app_rewrite/cmd_terminal_session.py` | Sessão CMD |
| `app_rewrite/linux_terminal_session.py` | Sessão remota SSH |
| `app_rewrite/rag_panel.py::RagPanel` | Gerência e pesquisa de conhecimento |
| `app_rewrite/rag_projects.py` | Catálogo local de projetos exibidos no painel |
| `app_rewrite/theme.py` | Estilo visual e tema |
| `app_rewrite/telemetry_widget.py` | Apresentação da telemetria |

## Controles presentes

`MainWindow` oferece funções para:

- Selecionar e acompanhar terminais; atualizar visualização e aba ativa conforme o estado;
- Alternar o modo de execução automática (`toggle_auto`) e som de conclusão (`toggle_completion_sound`);
- Testar e salvar configuração SSH, sem colocar credenciais em arquivos de documentação;
- Apresentar estados dos terminais, fila, tempo de atividade/telemetria e eventos;
- Interromper a operação ativa (`stop_active`) e encerrar a interface (`closeEvent`).

**Autoexecução** é uma opção de configuração da interface, não uma garantia de que qualquer ação remota seja segura. O uso de comandos MCP continua submetido às permissões efetivas do runtime.

## Terminal

`TerminalManager` possui métodos `normalize_target`, `start`, `configure_ssh`, `test_ssh`, `prepare`, `execute_prepared`, `execute`, `send_input`, `resize`, `discard_prepared`, `cancel_active`, `recycle`, `recover_orphaned`, `status` e `close`.

`TerminalWidget` e `TerminalBridge` fazem entrada, redimensionamento e drenagem de saída para exibição. As sessões reais e os buffers pertencem ao runtime, não aos widgets.

Para estados de execução, comando preparado e saída por cursor, consulte [EXECUTION_RUNTIME_CURRENT.md](EXECUTION_RUNTIME_CURRENT.md).

## Telemetria de sistema

- `app_rewrite/telemetry.py::TelemetryService`: coleta e publicação de snapshots de telemetria Windows e Linux, incluindo amostras de CPU, memória, rede e dados dos processos conforme disponibilidade.
- `app_rewrite/gpu_inventory.py`: enumeração, normalização e seleção da GPU principal.
- `app_rewrite/gpu_providers.py`: provedores de informação de GPU, com integração a ferramentas específicas conforme presentes no sistema.
- `app_rewrite/gpu_telemetry_windows.py::WindowsGpuTelemetry`: leituras Windows por PDH de mecanismos GPU e memória, agregadas por dispositivo.
- `app_rewrite/telemetry_widget.py`: renderização visual dos valores e estados.

As métricas exibidas dependem do sistema operacional, driver, permissões e provedor disponível; leitura ausente não significa automaticamente GPU inativa.

## Sons de conclusão

`app_rewrite/completion_sound.py::CompletionSound` controla habilitação, alternância e emissão de notificação de áudio; na plataforma Windows usa mecanismo de reprodução específico do sistema. O estado do botão está conectado à configuração local da aplicação.

## Conhecimentos na interface

O painel `RagPanel` apresenta **Meus arquivos**, **Pesquisar** e **Adicionar**. Os métodos existentes incluem `change_project`, `new_project`, `refresh`, `browse`, `browse_files`, `search`, `plan`, `cancel_preview`, `confirm_preview` e `review_authorization`.

- `browse_files` usa escolha de múltiplos arquivos via `QFileDialog.getOpenFileNames`, valida existência e pertencimento à pasta do projeto e envia paths relativos para a prévia.
- `plan` cria uma requisição de planejamento da indexação; `cancel_preview` invalida a versão da prévia pendente.
- `review_authorization` está explicitamente marcada no código como **simulação de interface**; não publica, não grava autorização persistente nem credenciais.

O cadastro de projeto no painel **não** prova que foi criado um índice publicado e consultável para esse projeto.

## Diferença entre código e instalação

A branch pode conter interface alterada enquanto a aplicação em execução mantém o módulo anterior carregado na memória. Para confirmar uma funcionalidade, auditar arquivo instalado, reiniciar a interface sob controle e testar a ação; não assumir ativação só porque o Git foi atualizado.

**Fontes:** `app_rewrite/ui.py`, `terminal_widget.py`, `terminal_manager.py`, `windows_terminal_session.py`, `cmd_terminal_session.py`, `linux_terminal_session.py`, `rag_panel.py`, `rag_projects.py`, `telemetry.py`, `telemetry_widget.py`, `gpu_inventory.py`, `gpu_providers.py`, `gpu_telemetry_windows.py`, `completion_sound.py`.
