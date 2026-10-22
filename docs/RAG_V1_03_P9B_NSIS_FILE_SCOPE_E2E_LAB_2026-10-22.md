# P9-B ? Ensaio de reversao do escopo de arquivos NSIS

Laboratorio isolado com o ZIP real de rollback:
NSIS_FILE_SCOPE_LAB_RECOVERED
236 arquivos antigos restaurados; 22 destinos novos removidos.
verified=true; production_modified=false; nsis_executed=false.

O ensaio materializa o baseline em pasta descartavel, modifica
um arquivo antigo e cria os 22 destinos artificiais; depois
reverte tudo pelo ZIP e compara os SHA256. Remove apenas arquivos
novos com marcador do proprio laboratorio. Tres testes unitarios
adicionais PASS (sucesso, pasta existente, snapshot invalido).

Nao houve instalacao NSIS, escrita no registro Windows ou
restauracao da instalacao ativa. O rollback operacional completo
ainda NAO foi comprovado. P9-B permanece aberta.
