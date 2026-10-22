# P9-B ? Recuperacao combinada com winreg real em HKCU isolado

Teste versionado tests/test_rag_p9b_combined_actual_hkcu_integration.py
combina restore_files_in_lab, o backend real restore_shell,
snapshot de atalhos, pos-verificacao e ScopedHKCU com winreg
REAL e um facade de remapeamento para subarvore exclusiva
Software/CodeBridgeP9BLab/<UUID>. Nenhuma chave CodeBridge
de producao foi aberta ou modificada.

Dois cenarios direcionados PASS:
- Recupera arquivo antigo e remove arquivo novo numa pasta
  descartavel; recupera atalhos e duas chaves temporarias
  HKCU por meio do backend real; valida journal com 6 eventos.
- Conteudo novo desconhecido bloqueia o fluxo antes da
  recuperacao do shell/HKCU.

Esta integracao usa apenas o exemplo pequeno de arquivos;
o ensaio separado com NSIS verdadeiro e 258 destinos
foi aprovado no marco anterior 1dfae56. A uniao desses
dois ensaios num ciclo UNICO de NSIS real+HKCU+atalhos
ainda nao foi executada. P9-B ABERTA.
