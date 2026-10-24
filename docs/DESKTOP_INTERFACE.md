# Interface desktop Windows

## Implementação

O aplicativo CodeBridge usa Python e PySide6. A janela principal é composta por `app_rewrite/ui.py::MainWindow`; o terminal visual e a ponte de sinais estão em `terminal_widget.py`, com sessões e comandos sob controle de `terminal_manager.py`.

## Terminais

Há interface para PowerShell 5.1, CMD e SSH, com estado de conexão, saída de comandos, redimensionamento, entrada interativa, troca de sessão e interrupção. O terminal real pertence ao runtime; widgets não são uma autoridade paralela para execução.

## Configuração e controles

`MainWindow` possui funções de seleção de terminal, configuração/teste SSH, opção de execução automática, estado operacional, som de conclusão e fechamento controlado. `completion_sound.py::CompletionSound` emite notificação configurável e persiste a preferência por `ConfigStore`.

## Telemetria

`telemetry.py::TelemetryService` coleta snapshots Windows e Linux. Módulos `gpu_inventory.py`, `gpu_providers.py` e `gpu_telemetry_windows.py` oferecem enumeração e métricas dependentes de driver/provedor. `telemetry_widget.py` apresenta os valores. Ausência de uma leitura não comprova que o recurso físico esteja inativo.

## Conhecimentos

`rag_panel.py::RagPanel` implementa navegação por projetos, lista de arquivos, pesquisa, seleção de pasta/arquivos individuais, prévia e visualização de resultados. A revisão de autorização apresentada por `review_authorization` é simulação de UI; novas fontes ainda dependem dos gates de escrita reais.

## Ciclo de vida

`author_mcp_manager.py::AuthorMCPManager` controla processos MCP/adapter; `secure_tunnel_manager.py::SecureTunnelManager` controla o túnel local. `single_instance.py::SingleInstance` usa mutex local para evitar instâncias duplicadas.

## Atenção às versões

Arquivos no repositório e arquivos carregados pela aplicação instalada podem ser diferentes. Uma alteração da interface no Git não aparece automaticamente em uma janela já aberta. Antes de validar comportamento, confira o módulo instalado e a versão de runtime.

Para ajustes de conexão consulte [CONFIGURATION.md](CONFIGURATION.md); para processos e canais internos consulte [ARCHITECTURE.md](ARCHITECTURE.md).