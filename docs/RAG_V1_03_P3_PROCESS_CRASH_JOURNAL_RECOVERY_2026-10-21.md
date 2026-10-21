# P3 ? Recuperacao de journal apos morte abrupta de processo

Data 2026-10-21. Um processo Python filho executa o escritor real com raiz fake temporaria e termina via os._exit(47) imediatamente apos gravar journal PREPARED. O processo pai confirma exitcode=47, journal persistido e ausencia do ponteiro. A recuperacao exige nome exato da candidata; retorna RECOVERED_LEGACY, preserva bytes do legado e candidata e remove apenas journal reconciliado.

O teste injeta readiness simulada e redireciona _root ao TEMP: nenhuma transicao ou indexacao publica, e nao e autorizacao para corte real.

Teste adicional de morte abrupta apos grava??o de ponteiro: os._exit(48), jornal e ponteiro ficam pendentes, leitor falha fechado, rollback com candidate esperado preserva arquivo recovered-pointer e restaura leitura do legado. Ambos testes de processo filho PASS em TEMP.
