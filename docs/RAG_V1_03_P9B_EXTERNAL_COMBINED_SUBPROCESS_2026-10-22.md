# P9-B ? Recuperador combinado em subprocesso isolado

Novo modulo: installer/rag_p9b_detached_combined_recovery_lab.py.
Executa em outro processo Python como entrypoint, recebe manifesto
JSON temporario de laboratorio e realiza:
- verificacao dos SHA256 dos ZIP arquivo/shell/preimagem;
- verificacao oficial do snapshot de 258 destinos com 236 originais;
- rollback dos arquivos com substituicao atomica e exclusao idempotente;
- backend real de shell com cinco arquivos de atalho e duas chaves HKCU;
- HKCU REAL redirecionado para namespace CodeBridgeP9BLab/<UUID>;
- journal persistente e verificacao final independente dos dados.

Teste de subprocesso separado e teste de recusa de caminho
fora do laboratorio PASS. O instalador NSIS oficial NAO foi
executado. Esta versao e disparada pelo teste e espera o retorno:
NAO e um supervisor persistente destacado capaz de recuperar
apos morte do coordenador. A API inclui mocks de guard de
processos destinados exclusivamente ao laboratorio.
Proximo passo: vincular ao crash NSIS verdadeiro, provar
recuperacao apos terminacao do coordenador e retomar journal.
