# P9-B ? Gate de integridade tripla

Novo gate read-only:
installer/rag_p9b_three_way_backup_gate.py

Vincula instalador NSIS, ZIP dos arquivos existentes e novos
destinos, e snapshot complementar de registro/atalhos HKCU.
Valida em conjunto SHA256 de todos os tres artefatos, manifesto
e baseline da instalacao e igualdade de registro/atalhos atual.
Nunca concede autorizacao para NSIS, restore ou limpeza.
Exige ainda parada da stack, NSIS guard e executor de rollback.

Resultado no Windows real:
THREE_WAY_BACKUP_OBSERVED_ONLY
verified=true
authorized=false
nsis_executed=false
installed_modified=false

Origem preview commit 2d99ed4.
Installer 0898124096989d62fd438395bc6f01baa031516f2579860daf275471272e3223
ZIP 236 antigos + 22 novos:
ad8d8c6397a1421a5858fb2f1b1746cfbda941d378cedd7b268b3931bb5fdf0d
Snapshot 2 HKCU + 5 atalhos:
7d2e39b928e829b7be8d23e03def48e97127d78e093f183f159c58c633d2e511

Quatro testes sint?ticos PASS.
P9-B ABERTA, main nao promovida, instalador nao aplicado.
