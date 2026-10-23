# P9-B ? Ensaios de queda abrupta em processo independente

Data: 2026-10-23
Estado: LABORATORIO PASS; CUTOVER NSIS REAL NAO EXECUTADO

## Evidencia comprovada

- Processo Python separado criou e sincronizou journal (fsync), depois encerrou com os._exit(73).
- Segundo processo validou historico, retomou journal e manteve estado REVIEW_REQUIRED, sem restart implicito.
- Processo separado escreveu etapa file-only de recuperacao combinada e encerrou com os._exit(74). Identidade diferente foi recusada.
- Processo separado executou restauracao atomica de arquivo em diretorio TEMPORARIO, encerrou com os._exit(75) imediatamente depois da substituicao e deixou o journal incompleto.
- Retomada posterior restaurou os destinos restantes e verificou conteudo antigo. Novo alvo conhecido foi removido no laboratorio e repeticao da recuperacao concluida foi recusada.
- Ciclo externo com transacao vinculada a SHA256 foi interrompido com os._exit(76), e replay com SHA256 diferente foi recusado.
- Um comando CLI de triagem fail-closed foi adicionado para diferenciar identidade, journal e parada de processos. A triagem real de staging sem journal retornou JOURNAL_NOT_VERIFIED, sem mutacoes.

## Limites da prova

Estas provas usam fixtures de diretorio temporario, valores de HKCU simulados em ensaios anteriores e nenhum processo CodeBridge real desligado. Nao constituem aprovacao de NSIS, recuperacao de HKCU real ou garantia de resiliencia a perda total de energia.

O supervisor de producao continua necessitando:
1. Processo externo autossuficiente comprovado durante desligamento real.
2. Integracao de restauracao completa (arquivos+HKCU+5 atalhos) com falha real no ponto intermediario.
3. Verificacao dos listeners e da GUI, reinicio seguro e handshake CBMCP/1.
4. Prova do bootstrap RAG, fila e scheduler.
5. Autorizacao explicita para cutover e auditoria Git final.

Preservar os tres arquivos historicos sujos preexistentes. Nenhum arquivo do RAG ativo, SQLite/WAL ou instalacao real deve ser excluido por estes ensaios.
