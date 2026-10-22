# P9-B ? NSIS real reproduzivel e recuperacao externa

Modulo versionado installer/rag_p9b_real_nsis_interrupt_lab.py:
gera NSIS minimo com first.txt, espera de 15 segundos e
second.txt; compila pelo makensis Windows, executa o EXE
silenciosamente em TEMP/P9B_NSIS_REPRO_<UUID>, confirma o
primeiro arquivo, interrompe o processo real e despacha
um recuperador via processo Python separado.

O recuperador exige jornal inicial valido e destino TEMP
exclusivo, confere conteudo exato do arquivo sentinela,
recusa arquivos extras e remove a pasta isolada, gravando
segundo evento com fsync.

Teste Windows executado: REAL_NSIS_ISOLATED_RECOVERED,
recovery_exit=0, lab_removed=true,
installer_executed=true, production_modified=false.
Quatro testes de contrato de recovery PASS.

Este componente NAO cobre payload oficial 236+22 nem
HKCU/atalhos reais. P9-B continua aberta ate supervisor
externo completo, ensaio de rollback da instalacao oficial,
handshake publico MCP e validacao RAG incremental.
