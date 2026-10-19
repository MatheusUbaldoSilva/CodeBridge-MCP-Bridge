import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.index.sqlite_schema import connect_rag_index
from rag.index.fts5 import initialize_fts5
from rag.runtime.incremental_sqlite_stage import stage_incremental_sqlite


def seed(path, docs):
    db = connect_rag_index(path)
    try:
        for document_id, project, content in docs:
            db.execute("INSERT INTO rag_documents(document_id,project_id,source_type,content,path) "
                       "VALUES(?,?,?,?,?)", (document_id, project, "DOCUMENTATION", content, document_id + ".md"))
            db.execute("INSERT INTO rag_chunks(chunk_id,document_id,project_id,ordinal,content,source_type,path) "
                       "VALUES(?,?,?,?,?,?,?)", ("chunk-" + document_id, document_id, project, 0,
                                                 content, "DOCUMENTATION", document_id + ".md"))
        db.commit()
        initialize_fts5(db, rebuild=True)
        db.commit()
    finally:
        db.close()


class IncrementalSqliteStageTests(unittest.TestCase):
    def test_add_replace_preserves_other_project_and_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, incoming, output = [root / (name + ".sqlite3") for name in ("source", "incoming", "output")]
            seed(source, [("a1", "a", "before"), ("b1", "b", "untouched")])
            seed(incoming, [("a1", "a", "after"), ("a2", "a", "added")])
            before = source.read_bytes()
            incoming_before = incoming.read_bytes()
            result = stage_incremental_sqlite(source, incoming, output, "a")
            self.assertEqual((result["added"], result["replaced"], result["total_documents"]), (1, 1, 3))
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(incoming.read_bytes(), incoming_before)
            db = sqlite3.connect(output)
            try:
                self.assertEqual(dict(db.execute("SELECT document_id,content FROM rag_documents")),
                                 {"a1": "after", "a2": "added", "b1": "untouched"})
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                db.close()

    def test_failure_does_not_replace_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, incoming, output = [root / (name + ".sqlite3") for name in ("source", "incoming", "output")]
            seed(source, [("a1", "a", "before")])
            seed(incoming, [("b1", "b", "wrong project")])
            before = source.read_bytes()
            with self.assertRaises(Exception):
                stage_incremental_sqlite(source, incoming, output, "a")
            self.assertFalse(output.exists())
            self.assertEqual(source.read_bytes(), before)


class IncrementalStageMetadataTests(unittest.TestCase):
    def test_merged_status_counts_match_isolated_corpus(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            original,incremental,merged=[
                root/(n+".sqlite3") for n in ("original","incremental","merged")
            ]
            seed(original,[("d1","codebridge","original")])
            seed(incremental,[("d2","codebridge","incremental")])
            db=sqlite3.connect(original)
            try:
                db.execute(
                    "INSERT INTO rag_index_state "
                    "(project_id,state,schema_version,document_count,chunk_count) "
                    "VALUES (?,?,?,?,?)",
                    ("codebridge","READY",1,1,1)
                )
                db.commit()
            finally:
                db.close()
            stage_incremental_sqlite(original,incremental,merged,"codebridge")
            db=sqlite3.connect(merged.resolve().as_uri()+"?mode=ro",uri=True)
            try:
                meta=db.execute(
                    "SELECT document_count,chunk_count,state "
                    "FROM rag_index_state WHERE project_id='codebridge'"
                ).fetchone()
                self.assertEqual(meta,(2,2,"READY"))
            finally:
                db.close()
