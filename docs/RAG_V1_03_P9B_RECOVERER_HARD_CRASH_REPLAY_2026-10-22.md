# P9-B ? Falha for?ada do proprio recuperador e replay

O executor independente em processo Python Windows foi testado
sob duas falhas reais de encerramento abrupto de processo:
- P9B_LAB_FAULT_AFTER_FILES: os._exit(87) apos restauro dos
  arquivos, antes do registro de confirmacao no journal;
- P9B_LAB_FAULT_AFTER_SHELL: os._exit(88) apos escritas do
  backend de atalhos e HKCU temporario, antes do postverify.

Em ambos os testes o journal incompleto e retomado em novo
processo, os 236 arquivos originais voltam ao hash oficial,
os 22 novos ficam ausentes e as cinco ligacoes/duas chaves
HKCU temporarias coincidem com o snapshot autorizado.
O journal final chega a SHELL_COMBINED_RECOVERY_VERIFIED.

Essas inje??es sao exclusivas do EXECUTOR DE LABORATORIO
e nunca se aplicam ao instalador em uso. NSIS de teste
interrompido tambem validado em mesma suite, mas o instalador
oficial completo NAO foi executado nem autorizado.
