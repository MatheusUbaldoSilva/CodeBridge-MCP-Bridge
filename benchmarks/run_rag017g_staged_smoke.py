from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import sqlite3
from rag.runtime.index_request import plan_rag_index,RagIndexScope
from rag.runtime.production_index import build_staged_index
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local,TEXT_VECTOR_COLLECTION

with TemporaryDirectory() as td:
    root=Path(td)
    (root/"intro.md").write_text("# Retrieval\nAn example document explains semantic retrieval indexes and persistent search.",encoding="utf-8")
    plan=plan_rag_index("rag017g-smoke",root,scope=RagIndexScope.TEXT,paths=("intro.md",))
    output=build_staged_index(plan)
    staging=Path(output["staging_path"])
    try:
        db=sqlite3.connect(str(staging/"rag_index.sqlite3"))
        count=db.execute("SELECT count(*) FROM rag_chunks").fetchone()[0]
        db.close()
        vector=open_qdrant_local(staging/"qdrant")
        points=vector.count(collection_name=TEXT_VECTOR_COLLECTION,exact=True).count
        close_qdrant_local(vector)
        assert output["documents"]==1 and count>0 and points==count
        print(f"SMOKE_OK chunks={count} vectors={points} state={output['state']}")
    finally:
        shutil.rmtree(staging)
