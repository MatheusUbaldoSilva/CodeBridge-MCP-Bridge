# P9-B ? Recuperador autonomo e retomada do journal

O executor em processo separado agora possui teste real Windows
em que o processo iniciador cria o filho DETACHED_PROCESS e sai
abruptamente com codigo 83. O filho conclui sem o iniciador,
restaurando os 236 arquivos anteriores, removendo 22 arquivos
novos e recuperando cinco atalhos e duas chaves HKCU temporarias.

O journal admite retomada de estados incompletos validados,
preservando sequencia monot?nica. A entrada rejeita journal
ja finalizado. O executor aceita uma sequencia interrompida
de dois eventos e produz fechamento validado, mas nao
depende de acessar registro HKCU de producao.

Limites: transacao de LABORATORIO com estados e paths temporarios;
ainda nao usa instalador oficial real junto ao processo destacado,
nem autentica o processo iniciador NSIS. Nao autoriza cutover.
