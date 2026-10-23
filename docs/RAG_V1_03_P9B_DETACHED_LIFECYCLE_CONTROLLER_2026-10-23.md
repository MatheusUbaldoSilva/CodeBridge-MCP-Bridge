# P9-B ? Controlador de ciclo de vida desacoplado

Data: 2026-10-23
Estado: LABORATORIO APROVADO; PRODUCAO BLOQUEADA; P9-B ABERTO.

## Responsabilidades

Modulo: installer/rag_p9b_detached_shutdown_recovery_controller.py

- Exigir interpretador Python e psutil fora da instalacao CodeBridge.
- Revalidar os quatro artefatos no supervisor existente.
- Comparar SHA256 do plano vivo de processos duas vezes antes do sinal.
- Registrar armado em journal ANTES da primeira tentativa de desligamento.
- Solicitar parada graciosa com validacao de identidade de cada processo.
- Exigir poststop comprovado por processos oficiais e listeners.
- Religar GUI somente depois de poststop verificado.
- Nunca equiparar GUI religada a MCP publico, scheduler ou RAG saudaveis.
- Nunca executar NSIS ou alterar indices RAG.

## Falhas e recuperacao

- Runtime ou identidade nao verificada: nenhuma acao e iniciada.
- Falha na escrita do evento inicial: nenhuma tentativa de desligamento.
- Identidade de processo alterada entre duas leituras: nenhuma tentativa de desligamento.
- Desligamento parcial ou poststop invalido: estado REVIEW_REQUIRED.
- Falha de restart: estado REVIEW_REQUIRED.
- GUI iniciada e processo confirmado: HANDSHAKE_PENDING, jamais sucesso final.

## Limites nao negociaveis

Testes foram executados com trabalhadores simulados. O runtime do supervisor
em processo separado ainda nao foi certificado sob parada efetiva. Nao executar
do proprio MCP instalado. Falta o elo rollback automatico completo de arquivos,
HKCU e atalhos apos uma falha do NSIS e prova do handshake publico CBMCP/1.
Esta etapa nao autoriza shutdown na maquina em uso nem cutover NSIS.

Arquivo de codigo commitado na branch rag-017-optimized-inference-after-candidate.
Tres arquivos locais historicos nao pertencem ao commit.
