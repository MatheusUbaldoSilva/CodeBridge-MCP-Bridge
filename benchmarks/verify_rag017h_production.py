"""RAG-017-H production restart and retrieval verification."""
import sqlite3
from rag.contracts import SearchQuery
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.status import build_rag_status,resolve_rag_sqlite_path
from rag.index.manifest import load_index_manifest

snapshot=build_rag_status()
assert snapshot.index["state"]=="READY",snapshot.index
manifest=load_index_manifest(snapshot.index["manifest_path"])
assert len(manifest.entries)==210
conn=sqlite3.connect(f"{resolve_rag_sqlite_path().resolve().as_uri()}?mode=ro",uri=True)
try:
    docs=conn.execute("SELECT count(*) FROM rag_documents").fetchone()[0]
    chunks=conn.execute("SELECT count(*) FROM rag_chunks").fetchone()[0]
    assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
finally:
    conn.close()
assert docs==210 and chunks==8761,(docs,chunks)
query=SearchQuery(
    query="Where is the deterministic query classifier implemented?",
    project_id="codebridge",top_k=5,
)
results=search_persistent_semantic(query,QueryRoute.CODE)
assert results and all(r.metadata.project_id=="codebridge" for r in results)
print("RAG017H_RESTART_SEARCH_OK",{"state":snapshot.index["state"],"documents":docs,"chunks":chunks,"hits":len(results),"first_path":results[0].metadata.path})
