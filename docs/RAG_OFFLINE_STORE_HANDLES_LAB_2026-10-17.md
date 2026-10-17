# RAG   Leitura de handles e sidecars em fixture sintetica
Estado: LABORATORIO; NENHUMA COPIA REAL AUTORIZADA.

`rag.runtime.offline_store_handle_probe.inspect_fixture_handles` verifica
somente a raiz sintetica `codebridge-rag-generation-test`. O probe valida
a presenca de SQLite, manifesto e arquivos Qdrant, rejeita sidecars
`-wal`, `-shm`, `-journal`, links e junctions, arquivos hardlinked,
e segura handles Windows no modo somente leitura para detectar escritores
incompativeis. O teste abre um escritor Python externo e comprova bloqueio.

`LAB_HANDLES_READABLE_UNPROVEN` indica apenas que arquivos da fixture
foram legiveis naquele intervalo. Nao comprova ausencia global de mmap,
consumidores herdados, flush coordenado ou consistencia de producao.
Sempre `copy_authorized=false`, `all_handles_closed=false` e
`production_quiescence_proven=false`. Nenhum dado de producao e copiado.

A verificacao adicional compara SHA-256 de SQLite, manifesto e arquivos Qdrant durante a janela protegida e bloqueia divergencias; nao substitui consistencia semantica entre os stores.

Adicionado ensaio concorrente com escritor Python para SQLite, manifesto e arquivo Qdrant separadamente; todos devem resultar BLOCKED.
