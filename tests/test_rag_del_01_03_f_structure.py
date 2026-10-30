from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from rag.index.sqlite_schema import connect_rag_index
from rag.index.fts5 import initialize_fts5
from rag.index.manifest import IndexManifest,ManifestEntry,ManifestIndexKind,save_index_manifest
from rag.runtime.knowledge_deletion_structure import inspect_deletion_generation_structure,DeletionCandidateStructureError

class DeletionCandidateStructureTests(TestCase):
    def setUp(self):
        t=TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.db=self.root/"rag_index.sqlite3"
        self.manifest=self.root/"rag-index-manifest.json"
        with closing(connect_rag_index(self.db)) as cn:
            for i in range(2):
                cn.execute("INSERT INTO rag_documents(document_id,project_id,source_type,content,path,sha256) VALUES(?,?,?,?,?,?)",
                    (str(i),"demo","CODE","hello",str(i)+".cpp","a"*64))
                cn.execute("INSERT INTO rag_chunks(chunk_id,document_id,project_id,ordinal,content,source_type,path) VALUES(?,?,?,?,?,?,?)",
                    ("c"+str(i),str(i),"demo",0,"hello","CODE",str(i)+".cpp"))
            cn.commit()
            initialize_fts5(cn,rebuild=True)
            cn.commit()
        save_index_manifest(self.manifest,IndexManifest(tuple(
            ManifestEntry(project_id="demo",index_kind=ManifestIndexKind.CODE,
                path=str(i)+".cpp",size=1,mtime_ns=1,sha256="a"*64,
                chunk_ids=("c"+str(i),),model_version="lab")
            for i in range(2)
        )))
    def inspect(self):
        return inspect_deletion_generation_structure(self.root,"demo",2)
    def test_verified_candidate(self):
        v=self.inspect()
        self.assertEqual(v["chunks"],2)
        self.assertFalse(v["activation_authorized"])
    def test_changed_document_sha_refused(self):
        with closing(connect_rag_index(self.db)) as cn:
            cn.execute("UPDATE rag_documents SET sha256='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' WHERE path='1.cpp'")
            cn.commit()
        with self.assertRaises(DeletionCandidateStructureError):self.inspect()
    def test_deleted_chunk_refused(self):
        with closing(connect_rag_index(self.db)) as cn:
            cn.execute("DELETE FROM rag_chunks WHERE path='1.cpp'")
            cn.commit()
        with self.assertRaises(DeletionCandidateStructureError):self.inspect()
    def test_foreign_project_refused(self):
        with closing(connect_rag_index(self.db)) as cn:
            cn.execute("INSERT INTO rag_documents(document_id,project_id,source_type,content,path,sha256) VALUES(?,?,?,?,?,?)",
                ("x","foreign","CODE","x","x.cpp","b"*64))
            cn.commit()
        with self.assertRaises(DeletionCandidateStructureError):self.inspect()
    def test_wrong_expected_count_refused(self):
        with self.assertRaises(DeletionCandidateStructureError):
            inspect_deletion_generation_structure(self.root,"demo",3)
