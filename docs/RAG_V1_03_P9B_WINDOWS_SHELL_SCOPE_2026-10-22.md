# P9-B ? Escopo de efeitos do NSIS no Windows

Inspecao estritamente read-only apos preparar o preview e snapshot.
O installer/CodeBridge.nsi escreve duas chaves HKCU:
Software\CodeBridge e
Software\Microsoft\Windows\CurrentVersion\Uninstall\CodeBridge.

O menu iniciar recebe quatro atalhos e a area de trabalho recebe um.
Os cinco atalhos previstos foram observados presentes. Foi
identificado um atalho legado adicional com codificacao quebrada
no nome de Extensao; ele nao foi modificado ou excluido.
A inspecao nao exporta valores de registro nem copia arquivos.

Modulos novos:
installer/rag_p9b_windows_shell_scope.py
tests/test_rag_p9b_windows_shell_scope.py (3 PASS).

Nenhum backup de registro/atalho foi criado ainda;
rollback integral permanece NAO COMPROVADO e NSIS nao executado.
Proximo passo e criar snapshot reversivel limitado a esse
escopo e ensaiar restauro isolado, sem afetar instalacao ativa.
