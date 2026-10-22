# P9-B ? Recuperacao combinada em laboratorio

Coordenador installer/rag_p9b_combined_recovery_lab.py executa
file_worker, shell_worker e postverify independente sob um unico
journal persistente, sempre em laboratorio explicitamente
identificado. Recusa resultados parciais ou nao comprovados.

Teste de integracao em pasta descartavel:
- restaura um arquivo antigo real por ZIP de teste;
- remove destino novo com marcador exclusivo do laboratorio;
- restaura cinco atalhos simulados de preimagem de crash;
- recomp?e duas chaves de registro SIMULADAS em JSON;
- verifica os conteudos finais e quatro eventos do journal.
Teste negativo com arquivo novo desconhecido recusou rollback
antes de chamar o restaurador de atalhos.

Cinco testes de contrato e dois testes de integracao PASS.
Nao se trata de executor de NSIS ou HKCU reais. P9-B aberta.
Proximo passo: supervisor externo de producao com provas
de parada, rollback de arquivos reais e HKCU real, validacao
independente e handshake publico do MCP.
