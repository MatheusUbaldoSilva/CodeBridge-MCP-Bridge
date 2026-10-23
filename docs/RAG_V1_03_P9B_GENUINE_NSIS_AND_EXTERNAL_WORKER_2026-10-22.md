# P9-B ? NSIS real interrompido com recuperador em processo independente

Teste versionado test_actual_nsis_interruption_recovers_in_external_child:
- prepara laboratorio Windows de 258 destinos do snapshot oficial;
- compila e executa NSIS verdadeiro com sentinela de laboratorio,
  escreve 22 destinos novos e sobrescreve primeiro antigo;
- interrompe NSIS durante pausa de 15 segundos;
- grava journal SHELL_NSIS_LAB_INTERRUPTED com fsync;
- subprocesso Python distinto executa rollback de arquivos,
  cinco atalhos de laboratorio e duas chaves reais HKCU,
  exclusivamente remapeadas para subarvore temporaria;
- confere retorno 0, 236 originais/22 ausentes, cinco atalhos,
  duas chaves, journal de 7 eventos e bytes do backup oficial.

Ensaios relacionados: sobrevivencia a saida abrupta do iniciador
(codigo 83), retomada de journal incompleto e rejeicao de
reexecucao apos fechamento.

LIMITES: NSIS foi gerado especificamente para o laboratorio,
nao e instalador oficial do CodeBridge. O processo de teste
faz o orquestramento; os ensaios de NSIS real e morte do
iniciador sao distintos. Ainda nao ha prova de resiliencia
ao crash do proprio recuperador enquanto escreve HKCU.
Nao autorizar producao ainda.
