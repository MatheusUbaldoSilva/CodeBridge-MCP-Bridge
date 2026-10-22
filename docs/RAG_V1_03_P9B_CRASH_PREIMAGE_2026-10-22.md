# P9-B ? Preimagem duravel antes de recuperar HKCU/atalhos

O modulo installer/rag_p9b_crash_preimage.py gera um ZIP exclusivo
com snapshot dos cinco atalhos NSIS e dos dois registros HKCU do
CodeBridge, usando apenas valores da whitelist. Persistencia:
escrita nova exclusiva, flush, fsync, SHA256. Verificador separado
recusa membros extras, hashes divergentes e escopo inesperado.

Prova real read-only do Windows: CRASH_PREIMAGE_DURABLE,
CRASH_PREIMAGE_VERIFIED, SHA256
14d201a576a3827925a8fd4819263840c88e569f992f837763d05438443749b9.
ZIP guardado fora do Git em release_staging/P9B_CURRENT_2d99ed4.
Nao foi aplicado NSIS nem alterado registro ou atalhos.

O backend experimental passou a exigir explicitamente
preimage_proof(), que deve retornar CRASH_PREIMAGE_VERIFIED.
Treze testes focalizados, com negacao ao faltar a prova, PASS.

LIMITACAO: prova injetavel isolada nao substitui um coordenador
externo que verifique os bytes da preimagem, os PIDs e o journal
antes de executar a restauracao. Ainda nao e recuperacao contra
crash comprovada de ponta a ponta.


## Verificacao independente apos interromper operacao

O modulo installer/rag_p9b_crash_recovery_gate.py cruza
preimagem SHA256 real, journal persistente e processo
instalado observado. Nao autoriza escrita: retorna
CRASH_RESTORATION_REVIEW_REQUIRED em transacoes interrompidas
com processos efetivamente parados. Nao restaura por conta
propria. O teste sobre a instalacao ativa retornou
CRASH_RECOVERY_REFUSED/CODEBRIDGE_STILL_ACTIVE.
Six testes simulados PASS. O hash antigo desta preimagem
tinha erro de transcricao; o SHA256 correto foi extraido
diretamente do arquivo e tem 64 caracteres.


## Conferencia direta de preimagem e falha simultanea de journal

O backend agora exige caminho do ZIP de preimagem e SHA256
e chama o verificador de conteudo diretamente antes de
qualquer mutacao. O ensaio integrado passou usando ZIP real
de laboratorio, nao uma prova simulada injetada.
Se a gravacao do evento SHELL_BACKEND_PARTIAL_FAILURE falhar,
a compensacao de arquivos e registro ainda e tentada,
e JOURNAL_WRITE_FAILED fica explicito no resultado.
Teste combinado de falha do registro e journal PASS.
Nao houve escrita no HKCU da maquina em uso.


## Reconstrucao independente em scratch

installer/rag_p9b_crash_replay_lab.py reconstruiu cinco atalhos
e os dados das duas chaves HKCU da preimagem real no diret?rio
descartavel CRASH_PREIMAGE_INDEPENDENT_REPLAY_20261022.
Executado por Remote Desktop Commander fora do MCP e confirmado:
CRASH_REPLAY_SCRATCH_VERIFIED; restored_shortcuts=5;
reviewed_registry_keys=2; registry_modified=false;
real_shortcuts_modified=false. Tres testes PASS.
Nao equivale a execucao real de rollback do registro ou NSIS.


## Defesa contra metadados malformados

O verificador de preimagem limita manifest.json a 16 KiB antes
de carrega-lo e exige coerencia do estado da chave HKCU (uma
chave ausente nao pode conter valores). Um teste adulterou o
ZIP com estado impossivel e recalculou o SHA256 valido:
o verificador recusou REGISTRY_SCOPE_INVALID.
Seis testes do componente PASS.
