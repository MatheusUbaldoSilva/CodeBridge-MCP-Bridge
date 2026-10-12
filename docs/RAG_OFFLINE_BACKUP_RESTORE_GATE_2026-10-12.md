# RAG  Porta de seguran�a para backup e restaura��o offline
Data: 2026-10-12
Estado: LABORAT�RIO VALIDADO / PRODU��O N�O AUTORIZADA

## Escopo e evid�ncias
O commit 9e1509f implementa reconstru��o de backup **somente em raiz experimental**
`codebridge-rag-generation-test`, para uma **nova** gera��o, sem alterar
`active-generation.json`. O comando de recupera��o exige backup com manifesto
de hashes, rejeita sobrescritas e symlinks, valida SQLite + manifesto + Qdrant
e limpa apenas a pasta tempor�ria em interrup��es simuladas.

A regress�o das gera��es aprovou 83 testes; isso N�O comprova backup de
produ��o. �ltima leitura somente leitura do �ndice real: 210 documentos,
8.761 chunks, 210 entradas no manifesto e SQLite �ntegro. Essa fotografia
pode mudar; revalidar no momento da captura.

## Pr�-condi��es obrigat�rias  antes de qualquer c�pia real
1. Consentimento expl�cito do operador para janela de manuten��o e destino
   da c�pia; n�o iniciar por execu��o impl�cita de testes.
2. Encerre completamente GUI, MCP, adapter, consultas e indexadores.
   Confirme aus�ncia de processos, handles e conex�es ativas ao Qdrant/SQLite.
3. Fa�a a captura por executor **externo** ao aplicativo encerrado, n�o
   por uma chamada MCP que dependa do pr�prio servi�o a ser parado.
4. N�o assuma que `operator_asserted_quiesced=True` constitui prova:
   o pr�-diagn�stico existente � informativo e NUNCA autoriza c�pia.
5. Preserve os arquivos de produ��o, sem desativar prote��es ou remover
   WAL/SHM manualmente. Se houver transa��o/sidecar inesperado, bloquear
   at� inspecionar e obter encerramento �ntegro.
6. Espa�o livre e permiss�es do destino devem ser suficientes; nunca
   escolher diret�rio de backup existente para sobrescrever.

## Sequ�ncia proposta (ainda N�O executada na produ��o)
A. Inventariar `%LOCALAPPDATA%\CodeBridge\rag\`, incluindo
   `rag_index.sqlite3`, `rag-index-manifest.json` e todo `qdrant`.
B. Verificar quiesc�ncia efetiva; registrar quantidade, integridade,
   vers�es, manifestos e fingerprints antes da c�pia.
C. Copiar os tr�s armazenamentos para **novo destino de recupera��o**.
   Nunca copiar Qdrant enquanto houver leitor/escritor ativo.
D. Recalcular hashes e comparar origem e destino. Falha cancela
   procedimento sem alterar a produ��o.
E. Validar a c�pia em outro processo/ambiente isolado: `PRAGMA integrity_check`,
   manifesto contra documentos/chunks e identidade dos pontos Qdrant.
F. Simular recupera��o sem apontar buscas reais para a c�pia. Testar
   prote��o de outros projetos, consulta e retorno ao estado anterior.
G. Gerar relat�rio audit�vel (hashes, caminhos, vers�es, testes e resultado).
H. Somente ap�s aprova��o expl�cita, planejar migra��o/publica��o real
   com mecanismo at�mico, leitores coordenados e rollback comprovado.

## Portas de bloqueio
- �NDICE INSTALADO: n�o copiar com a aplica��o ativa.
- RESTAURA��O: n�o ativar gera��o automaticamente.
- QUADRO DE STATUS: resultado `OFFLINE_CANDIDATE` n�o � sinal de permiss�o.
- PUBLICA��O INCREMENTAL: bot�o permanece desabilitado.
- DADOS EXISTENTES: nunca remover ou substituir para abrir espa�o.
- ARQUIVOS GIT ALHEIOS: benchmarks e runbook preexistentes preservados.

## Pr�ximo marco
Criar e testar um **capturador offline separado do MCP**, inicialmente
somente sobre um fixture sint�tico com falhas injetadas. Validar
detec��o de processos ativos, checagem de locks, relat�rio de hashes,
c�pia isolada e ensaio de restaura��o. N�o us�-lo no �ndice real sem
aprova��o e janela segura de manuten��o.
