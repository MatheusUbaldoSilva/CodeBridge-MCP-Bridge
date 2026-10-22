# P9-B ? Ensaio E2E de interrupcao e recuperacao

## Criterio comprovado
Dois subprocessos Python distintos, sem dependencia entre os seus
estados em memoria, executam o laboratorio descartavel.

1. SETUP cria pasta exclusiva, cinco atalhos ficticios e
   preimagem persistente contendo duas chaves HKCU SIMULADAS.
2. CRASH persiste o journal SHELL_BACKEND_ARMED, altera o primeiro
   atalho, grava estado simulado de registro como PARTIALLY_INSTALLED,
   chama os._exit(83) sem rotina de shutdown ou limpeza.
3. RESCUE e iniciado em OUTRO processo Python, valida preimagem e
   journal, restaura 5 atalhos de laboratorio, reconstrui os dados
   das 2 chaves ficticias de registro, e confere os hashes.
4. TESTE NEGATIVO corrompe o journal; rescue recusa com exit 2.

Resultado: LAB_E2E_RECOVERED, 5 arquivos e 2 chaves simuladas,
production_modified=false. Suite unittest: 2 PASS.
O primeiro prototipo foi corrigido apos identificar que o Python
embarcado do CodeBridge ignora PYTHONPATH, e que fsync em
descritor read-only no Windows nao funciona.

## Bloqueio remanescente
Este ensaio NAO atualizou NSIS real nem escreveu no HKCU.
NAO valida rollback de producao; portanto nao fecha a P9-B.
O proximo gate exige supervisor independente com identidade
de processos, snapshot de 236 arquivos, 22 novos destinos,
restauracao de HKCU e atalhos, verificacao depois do restauro,
integracao ao NSIS e handshake publico real.
O instalador instalado e o RAG permanecem sem alteracoes.
