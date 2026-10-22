# P9-B ? Escrita atomica de atalhos no backend de rollback

Criado installer/rag_p9b_atomic_shortcut_restore.py e integrado
ao backend de restauracao HKCU + atalhos.
Para cada atalho: valida pasta de destino, recusa symlink,
cria arquivo temporario no mesmo diretorio, grava com fsync
e substitui por os.replace. No caso de excecao antes da
troca, o atalho anterior permanece intacto. Remove temporario.

O backend registra o alvo para compensacao antes de alterar
e usa o mesmo mecanismo atomico para reparar links.
Um teste induziu falha continua no os.replace e provou que
o arquivo original permaneceu intacto, mas a compensacao
nao foi declarada verificada. O resultado exige revisao.

Cinco testes novos do componente PASS e testes do backend PASS.
Nao executa NSIS nem altera HKCU/atalhos na instalacao real.
O supervisor NSIS real ainda nao esta pronto: a P9-B segue aberta.
