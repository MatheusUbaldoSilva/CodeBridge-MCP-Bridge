# RAG   Contrato proposto para parada externa antes de captura real

Estado: PROPOSTA / NÃO IMPLEMENTADO / PRODUÇÃO NÃO AUTORIZADA.
Auditoria de código local realizada em 2026-10-12.

## Sequência observada no CodeBridge

- `app_rewrite/main.py`: em modo GUI, `run_ui(runtime)` retorna quando
  o evento Qt termina; `finally` invoca `runtime.stop()` e libera
  `SingleInstance`. Em modo headless, o laço fica ativo até a saída.
- `app_rewrite/ui.py`: `MainWindow.closeEvent` encerra primeiro a telemetria.
  O fechamento da GUI, sozinho, não é prova da liberação de todos os handles.
- `app_rewrite/runtime.py`: `BridgeRuntime.stop()` chama nesta ordem:
  secure_tunnel.stop(), author_mcp.stop(), chatgpt_companion.stop(),
  api.stop(), engine.stop(wait=True, timeout=5), terminals.close().
- `app_rewrite/author_mcp_manager.py`: o stack é iniciado com
  adapter_server.py e mcp_server.py via subprocess.Popen e espera
  disponibilidade. O stop dos processos geridos tenta terminate()/wait(3s)
  e, em último caso, kill()/wait(2s). A implementação pode ter processos
  herdados, que exigem verificação adicional.
- O RAG instalado combina SQLite, manifesto e Qdrant em diretório local.
  Nenhuma função acima, isoladamente, comprova fechamento de todos os
  consumidores e arquivos abertos.

## Gate futuro obrigatório (executor FORA da GUI/MCP)

1. Operador autoriza explicitamente janela e destino. Registrar consentimento,
   horário, diretórios de origem/destino, PIDs previstos e versão do app.
2. Inibir novas operações de indexação e novas consultas; permitir encerrar as
   requisições em andamento, registrar flush/checkpoint íntegro dos stores.
3. Pedir encerramento normal da GUI/serviços. NÃO fechar ou matar automaticamente
   o próprio MCP pela conexão remota que depende dele.
4. Supervisor externo, iniciado ANTES da parada, espera os PIDs reais saírem.
   Identidade: caminho executável + command line + PID + creation time, evitando
   equivalência por nome genérico (python.exe).
5. Verificar novamente portas/serviços e TODOS os processos consumidores do
   SQLite/Qdrant, inclusive instâncias não geridas/herdadas.
6. Verificar SQLite sem sidecars inesperados WAL/SHM/journal; não remover nenhum.
   Abrir handles nativos com política que detecta writer ativo, verificando
   integralmente árvore Qdrant e caminhos canônicos/reparse points.
7. Comparar lista completa e fingerprints em janela estável, com processo
   externo responsável por manter os handles até encerrar a cópia.
8. Somente se todas as portas passarem, iniciar captura em novo destino, calcular
   SHA-256 de origem/destino e restaurar em processo independente. Nunca ativar
   automaticamente a cópia ou alterar o ponteiro de produção.
9. Se qualquer etapa falhar: NÃO COPIAR, NÃO APAGAR e retornar relatório
   auditável. Liberação futura exigirá revisão explícita do operador.

## Evidência ainda faltante

Processos herdados, indexadores paralelos, caches mmap, handles no Qdrant e
flush atômico de SQLite/manifesto/Qdrant precisam de auditoria e provas
reproduzíveis. O inventário tasklist é só diagnóstico. Os testes atuais são
fixtures sintéticos. Esta proposta não liga nenhuma ação real.
