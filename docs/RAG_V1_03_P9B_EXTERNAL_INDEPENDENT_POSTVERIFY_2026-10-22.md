# P9-B ? Auditoria externa do rollback NSIS unificado

Teste de laboratorio de NSIS verdadeiro interrompido apos
22 arquivos novos e um antigo substituido, com recuperacao
de 236 originais/22 novos e 5 atalhos/2 HKCU temporarias
via ScopedHKCU winreg real, sem producao.

Apos o rollback, um SEGUNDO PROCESSO Python executa
installer/rag_p9b_external_lab_postverify.py e verifica:
- raiz TEMP descartavel e caminhos internos do shell;
- UUID exclusivo do HKCU no namespace CodeBridgeP9BLab;
- hashes SHA256 dos ZIP de arquivo e shell;
- journal valido com 7 eventos e final verificado;
- os 236 hashes antigos, a ausencia de 22 arquivos novos;
- 5 atalhos e 2 chaves HKCU temporarias.

Nenhuma escrita em HKCU ocorre no verificador (read-only).
Testes negativos para caminho, UUID, hashes e journal.
Limites: o rollback combinado ainda roda no processo de
testes; o verificador, sim, e separado. NSIS e construido
especificamente para o laboratorio, nao e o oficial.
P9-B permanece aberta ate recuperacao executada por
supervisor autonomo e atualizacao oficial segura.
