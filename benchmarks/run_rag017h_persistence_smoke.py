"""RAG-017-H smoke: staging -> publish -> restart -> recovery validation."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import shutil
import sqlite3

from rag.runtime.index_request import plan_rag_index,RagIndexScope
from rag.runtime.production_index import build_staged_index
from rag.runtime.production_publish import publish_staged_index, validate_staged_index, RagPublicationError
from rag.runtime.status import build_rag_status

with TemporaryDirectory() as td:
    base=Path(td)
    project=base/"project"
    project.mkdir()
    (project/"README.md").write_text("# Project knowledge\nSearch retrieves project context from persistent embeddings.\n",encoding="utf-8")
    prod=base/"local"/"CodeBridge"/"rag"
    plan=plan_rag_index("rag017h-smoke",project,scope=RagIndexScope.TEXT,paths=("README.md",))
    with patch("rag.runtime.production_index.resolve_rag_sqlite_path",return_value=prod/"rag_index.sqlite3"):
        staged=build_staged_index(plan)
    stage=Path(staged["staging_path"])
    from rag.runtime import production_publish as pub
    try:
        validation=validate_staged_index(stage,"rag017h-smoke")
        with patch.object(pub,"resolve_rag_sqlite_path",return_value=prod/"rag_index.sqlite3"),patch.object(pub,"resolve_qdrant_local_path",return_value=prod/"qdrant"),patch.object(pub,"resolve_rag_manifest_path",return_value=prod/"rag-index-manifest.json"):
            outcome=publish_staged_index(stage,"rag017h-smoke",project)
            assert outcome["state"]=="READY"
            try:
                publish_staged_index(stage,"rag017h-smoke",project)
            except RagPublicationError:
                pass
            else:
                raise AssertionError("overwrite unexpectedly succeeded")
        with patch.dict("os.environ",{"LOCALAPPDATA":str(base/"local")}):
            restarted=build_rag_status()
            assert restarted.index["state"]=="READY",restarted.index
            assert restarted.index["manifest_entries"]==1
        db=sqlite3.connect(str(prod/"rag_index.sqlite3"))
        assert db.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        db.close()
        print("RAG017H_PERSISTENCE_RESTART_OK",validation,outcome["state"],restarted.index["state"])
    finally:
        shutil.rmtree(stage,ignore_errors=True)
