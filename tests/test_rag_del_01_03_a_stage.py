"""Temporary-only tests of RAG-DEL-01.03-A candidate staging."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import sqlite3

from rag.index.sqlite_schema import connect_rag_index
from rag.index.fts5 import initialize_fts5
from rag.index.manifest import IndexManifest, ManifestEntry, ManifestIndexKind, save_index_manifest
from rag.runtime.knowledge_deletion_stage import (
    DeletionStageError, stage_removal_sqlite_manifest,
)


class DeletionSqliteStageTests(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.active = self.root / "active"
        self.active.mkdir()
        self.db = self.active / "rag_index.sqlite3"
        self.manifest = self.active / "rag-index-manifest.json"
        with closing(connect_rag_index(self.db)) as cn:
            for key in ("a", "b"):
                cn.execute(
                    "INSERT INTO rag_documents(document_id,project_id,source_type,content,path) "
                    "VALUES(?,?,?,?,?)", (key, "demo", "CODE", key, key+".cpp")
                )
                cn.execute(
                    "INSERT INTO rag_chunks(chunk_id,document_id,project_id,ordinal,content,source_type,path) "
                    "VALUES(?,?,?,?,?,?,?)", ("c"+key,key,"demo",0,key,"CODE",key+".cpp")
                )
            cn.commit()
            initialize_fts5(cn, rebuild=True)
            cn.commit()
        entries = tuple(
            ManifestEntry(project_id="demo",index_kind=ManifestIndexKind.CODE,
                          path=key+".cpp",size=1,mtime_ns=1,sha256="a"*64,
                          chunk_ids=("c"+key,),model_version="test")
            for key in ("a","b")
        )
        save_index_manifest(self.manifest, IndexManifest(entries))
        self.index = SimpleNamespace(
            sqlite=self.db,manifest=self.manifest,
            generation="auto_lab",source_revision="f"*64
        )
        preview = {
            "review_sha256":"b"*64,"generation":"auto_lab",
            "source_revision":"f"*64,"selected_paths":["a.cpp"],
            "documents_to_preserve":1,"chunks_to_preserve":1,
        }
        for name,value in (
            ("rag.runtime.knowledge_deletion_stage.preview_knowledge_removal", preview),
            ("rag.runtime.knowledge_deletion_stage.resolve_isolated_project",self.index),
        ):
            p=patch(name,return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.before_db = self.db.read_bytes()
        self.before_manifest = self.manifest.read_bytes()

    def test_stage_copy_and_preserve_active(self):
        output = self.root / "candidate"
        result=stage_removal_sqlite_manifest("demo",["a.cpp"],"b"*64,output)
        self.assertEqual(result["state"],"SQLITE_MANIFEST_STAGED_NOT_VERIFIED")
        self.assertFalse(result["activated"])
        self.assertFalse(result["vectors_copied"])
        with closing(sqlite3.connect(output/"rag_index.sqlite3")) as cn:
            self.assertEqual(cn.execute(
                "SELECT path FROM rag_documents WHERE project_id='demo'"
            ).fetchall(),[("b.cpp",)])
            self.assertEqual(cn.execute(
                "SELECT COUNT(*) FROM rag_chunks_fts WHERE project_id='demo'"
            ).fetchone()[0],1)
        self.assertEqual(self.db.read_bytes(),self.before_db)
        self.assertEqual(self.manifest.read_bytes(),self.before_manifest)

    def test_stale_digest_rejected_without_destination(self):
        output=self.root/"candidate"
        with self.assertRaises(DeletionStageError):
            stage_removal_sqlite_manifest("demo",["a.cpp"],"0"*64,output)
        self.assertFalse(output.exists())

    def test_existing_destination_not_modified(self):
        output=self.root/"candidate"
        output.mkdir()
        marker=output/"keep.txt"
        marker.write_text("keep")
        with self.assertRaises(DeletionStageError):
            stage_removal_sqlite_manifest("demo",["a.cpp"],"b"*64,output)
        self.assertEqual(marker.read_text(),"keep")

    def test_active_overlap_rejected(self):
        with self.assertRaises(DeletionStageError):
            stage_removal_sqlite_manifest("demo",["a.cpp"],"b"*64,self.active/"other")
        self.assertFalse((self.active/"other").exists())
