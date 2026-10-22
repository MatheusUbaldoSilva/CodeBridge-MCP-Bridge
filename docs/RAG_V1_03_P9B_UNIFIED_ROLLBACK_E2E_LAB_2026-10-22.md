# P9-B ? Rollback E2E integrado de laboratorio

Prova em pasta descartavel: unico experimento encadeia
preimagem de atalhos/HKCU SIMULADO, snapshot real de 236
arquivos anteriores e 22 destinos novos, journal persistente,
termino abrupto os._exit(83), novo processo recuperador
e verificacao posterior.

Resultado Windows: UNIFIED_LAB_RECOVERED;
old_files_checked=236, new_targets_removed=22,
shortcuts_checked=5, fake_registry_keys_checked=2,
production_modified=false.

Tres testes automatizados: ciclo crash/recover por processos
distintos, journal corrompido recusado e preimagem invalida.
O recuperador exige identidade de laboratorio descartavel.

Limite essencial: nao executou NSIS real e nao restaurou
HKCU verdadeiro; nao reiniciou o MCP no mesmo fluxo.
Logo, a P9-B permanece ABERTA e o bloqueio operacional
da atualizacao em producao nao esta resolvido.
