# P9-B ? Teste real do registro Windows em namespace isolado

Testes em tests/test_rag_p9b_real_hkcu_isolated.py.
Utilizam winreg REAL atraves da interface ScopedHKCU,
mas um adaptador de nomes redireciona todas as operacoes
para uma subarvore temporaria unica do usuario atual:
Software/CodeBridgeP9BLab/<UUID> (separador real do Windows).
As chaves de producao CodeBridge nao sao abertas.

Teste de escrita, leitura, restauracao e exclusao de
duas chaves temporarias PASS. Um caminho fora do escopo
foi corretamente recusado. A limpeza no tearDown remove
somente as chaves pertencentes ao UUID deste ensaio.

313 regress?es P9-B/processos PASS na maquina.
Este teste valida API winreg real, mas NAO equivale a
rollback de instalador NSIS real nem ao restauro de HKCU
de producao. P9-B permanece aberta. Proxima etapa:
transacao externa supervisionada em ambiente isolado
com instalador real, journal persistente e recovery.
