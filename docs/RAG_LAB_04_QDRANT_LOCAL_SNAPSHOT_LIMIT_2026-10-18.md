# RAG-LAB.04-B — limite de snapshots Qdrant Local (18/10/2026)

Auditoria local read-only do pacote instalado qdrant-client 1.19.1 e da classe qdrant_client.local.qdrant_local.QdrantLocal.

- create_snapshot, create_full_snapshot e recover_snapshot existem mas implementam apenas NotImplementedError: snapshots nao suportados no Qdrant Local.
- list_snapshots no QdrantLocal retorna lista vazia.
- A API publica de QdrantClient delega para _client; sua existencia nao prova suporte no modo local.
- A fixture testada em modo local contem .lock, meta.json, collection/code/storage.sqlite e collection/text/storage.sqlite.

Conclusao: os testes da RAG-LAB.04 comprovam copia e restauracao isoladas de arquivos locais da versao instalada; NAO validam snapshots nativos de Qdrant Server ou todos os formatos/versionamentos de checkpoint.

Nao instalar Qdrant Server nem acessar stores reais sem aprovacoes e escopo novos.
04-B e fechamento normativo 04 permanecem PARCIAIS.
Qt 7 testes nao executados: PySide6 ausente.
Backend ultima regressao completa: 394 PASS na segunda bateria, apos uma falha intermitente nao explicada na primeira bateria do teste de publicacao concorrente.

production_backup=BLOCKED
production_quiescence_proven=false
