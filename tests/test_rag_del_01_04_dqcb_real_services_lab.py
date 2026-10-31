"""RAG-DEL-01.04-DQ-C-B: real search/context services in scratch read pin."""
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json

from rag.contracts import SearchResult, SourceMetadata, SourceType
from rag.index.fts5 import initialize_fts5
from rag.index.sqlite_schema import connect_rag_index
from rag.runtime.search_service import search_context
from rag.runtime.context_service import get_context, RagContextSourceMissingError
from rag.runtime.production_generation_lock import production_generation_lock
from rag.runtime.knowledge_deletion_private_read_session_lab import (
    private_read_session_lab, PrivateReadSessionLabError,
)


class RealPrivateReadServicesLabTests(TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.rag=self.root/"CodeBridge"/"rag"
        self.rag.mkdir(parents=True)
        self.catalog=self.root/"project-indexes.json"
        self.db=self.root/"generations"/"private_services"/"rag_index.sqlite3"
        self.db.parent.mkdir(parents=True)
        cn=connect_rag_index(self.db)
        try:
            cn.execute(
                "INSERT INTO rag_documents"
                " (document_id,project_id,source_type,content,path)"
                " VALUES ('document-1','project-lab','CODE',"
                " 'codigo privado aprovado','src/job.py')"
            )
            cn.execute(
                "INSERT INTO rag_chunks"
                " (chunk_id,document_id,project_id,ordinal,content,source_type,path)"
                " VALUES ('chunk-1','document-1','project-lab',0,"
                " 'onde controla cancelamento do runtime','CODE','src/job.py')"
            )
            cn.execute(
                "INSERT INTO rag_documents"
                " (document_id,project_id,source_type,content,path)"
                " VALUES ('foreign-document','other-project','CODE',"
                " 'segredo de outro projeto','other/secret.py')"
            )
            cn.execute(
                "INSERT INTO rag_chunks"
                " (chunk_id,document_id,project_id,ordinal,content,source_type,path)"
                " VALUES ('foreign-chunk','foreign-document','other-project',0,"
                " 'onde controla cancelamento do runtime','CODE','other/secret.py')"
            )
            cn.commit()
            initialize_fts5(cn)
        finally:
            cn.close()
        self.manifest=self.db.with_name("rag-index-manifest.json")
        self.manifest.write_text('{"lab":true}',encoding="utf-8")
        self.catalog.write_text(json.dumps({
            "schema_version":1,"projects":{"project-lab":{
                "project_id":"project-lab",
                "enabled":True,
                "generation_directory":str(self.db.parent.resolve()),
                "sqlite_sha256":sha256(self.db.read_bytes()).hexdigest(),
                "manifest_sha256":sha256(self.manifest.read_bytes()).hexdigest(),
            }}
        }),encoding="utf-8")

    def guarded(self, *, semantic=False):
        return private_read_session_lab(
            "project-lab",catalog_file=self.catalog,sqlite_path=self.db,
            manifest_path=self.manifest,
            generation_guard_factory=lambda:production_generation_lock(
                exclusive=False,channel="generation"
            ),
            semantic_guard_factory=lambda:production_generation_lock(
                exclusive=True,channel="semantic"
            ),
            semantic=semantic,laboratory_mode=True,operator_approved=True,
        )

    def patched_root(self):
        return patch(
            "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
            return_value=self.rag/"rag_index.sqlite3",
        )

    def test_actual_lexical_search_and_get_context_share_one_pinned_generation(self):
        with self.patched_root():
            with self.guarded() as session:
                result=search_context(
                    query="onde controla cancelamento do runtime",
                    project_id="project-lab",
                    sqlite_path=session.sqlite,
                    semantic_executor=None,
                )
                self.assertEqual([x.chunk_id for x in result.results],["chunk-1"])
                selection=get_context(
                    project_id="project-lab",chunk_ids=("chunk-1",),
                    sqlite_path=session.sqlite,
                    include_document_content=True,
                )
                self.assertEqual(selection.items[0].content,
                                 "onde controla cancelamento do runtime")
                self.assertEqual(selection.items[0].document_content,
                                 "codigo privado aprovado")
                self.assertEqual(session.generation,"private_services")

    def test_real_context_denies_foreign_namespace_with_pinned_sqlite(self):
        with self.patched_root():
            with self.guarded() as session:
                with self.assertRaises(RagContextSourceMissingError):
                    get_context(
                        project_id="project-lab",
                        chunk_ids=("foreign-chunk",),
                        sqlite_path=session.sqlite,
                    )

    def test_semantic_executor_is_called_using_existing_session_lock(self):
        calls=[]
        def semantic_result(query,route,pin):
            calls.append(route.value)
            return (pin.call_semantic_already_locked(
                lambda: SearchResult(
                    chunk_id="chunk-1",document_id="document-1",
                    content="onde controla cancelamento do runtime",
                    metadata=SourceMetadata(
                        project_id="project-lab",source_type=SourceType.CODE,
                        path="src/job.py",
                    ),
                    score=1.0,rank=1,retrieval_modes=("LAB_SYNTHETIC",),
                )
            ),)
        with self.patched_root():
            with self.guarded(semantic=True) as pin:
                result=search_context(
                    query="onde controla cancelamento do runtime",
                    project_id="project-lab",sqlite_path=pin.sqlite,
                    semantic_executor=lambda query,route:
                        semantic_result(query,route,pin),
                )
                self.assertEqual(result.results[0].chunk_id,"chunk-1")
                self.assertEqual(result.results[0].retrieval_modes,
                                 ("LAB_SYNTHETIC",))
                self.assertEqual(len(calls),1)
            with self.assertRaises(PrivateReadSessionLabError):
                pin.call_semantic_already_locked(lambda: 1)