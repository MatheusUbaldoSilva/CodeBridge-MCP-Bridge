"""RAG-017-G real two-model integration smoke; no persistent publication."""
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import sqlite3
from rag.runtime.index_request import plan_rag_index,RagIndexScope
from rag.runtime.production_index import build_staged_index
from rag.index.qdrant_local import (
    open_qdrant_local,close_qdrant_local,
    TEXT_VECTOR_COLLECTION,CODE_VECTOR_COLLECTION,
)

with TemporaryDirectory() as td:
    root=Path(td)
    (root/"guide.md").write_text("# Usage\nThe codebridge tracks knowledge and project context.",encoding="utf-8")
    (root/"sample.py").write_text("def search_project_context(query: str) -> str:\n    return query.casefold()\n",encoding="utf-8")
    plan=plan_rag_index("rag017g-dual",root,scope=RagIndexScope.BOTH,paths=("guide.md","sample.py"))
    output=build_staged_index(plan)
    stage=Path(output["staging_path"])
    try:
        qdrant=open_qdrant_local(stage/"qdrant")
        try:
            text=qdrant.count(collection_name=TEXT_VECTOR_COLLECTION,exact=True).count
            code=qdrant.count(collection_name=CODE_VECTOR_COLLECTION,exact=True).count
        finally:
            close_qdrant_local(qdrant)
        assert output["documents"]==2
        assert text==output["text_chunks"]>0
        assert code==output["code_chunks"]>0
        assert output["state"]=="STAGED_NOT_PUBLISHED"
        print(f"RAG017G_DUAL_MODEL_OK docs={output['documents']} text_vectors={text} code_vectors={code}")
    finally:
        shutil.rmtree(stage)
