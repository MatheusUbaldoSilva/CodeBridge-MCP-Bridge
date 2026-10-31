"""DQ-E-D-3B: strict synthetic semantic response correlation with real child."""
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import json
import sqlite3
import subprocess

from rag.contracts import SearchQuery
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.knowledge_deletion_semantic_roundtrip_lab import (
    execute_semantic_roundtrip_lab, SemanticRoundtripLabError,
)
from rag.runtime.knowledge_deletion_private_read_session_lab import (
    private_read_session_lab,
)
from rag.runtime.production_generation_lock import production_generation_lock


class StrictScratchSemanticResponseTests(TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.rag=self.root/"CodeBridge"/"rag"
        self.rag.mkdir(parents=True)
        self.catalog=self.root/"project-indexes.json"
        self.db=self.root/"generations"/"private_roundtrip"/"rag_index.sqlite3"
        self.db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("CREATE TABLE rag_documents(project_id TEXT,path TEXT)")
            cn.execute("INSERT INTO rag_documents VALUES ('private-lab','doc.py')")
            cn.commit()
        self.manifest=self.db.with_name("rag-index-manifest.json")
        self.manifest.write_text('{"fake":true}',encoding="utf-8")
        self.catalog.write_text(json.dumps({
            "schema_version":1,"projects":{"private-lab":{
                "project_id":"private-lab","enabled":True,
                "source_revision":"rev-1",
                "generation_directory":str(self.db.parent.resolve()),
                "sqlite_sha256":sha256(self.db.read_bytes()).hexdigest(),
                "manifest_sha256":sha256(self.manifest.read_bytes()).hexdigest(),
            }}
        }),encoding="utf-8")
        self.query=SearchQuery(
            query="where is runtime",project_id="private-lab",top_k=2,
        )
        self.route=QueryRoute.CODE

    def patch_root(self):
        return patch(
            "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
            return_value=self.rag/"rag_index.sqlite3",
        )

    def session(self):
        return private_read_session_lab(
            "private-lab",catalog_file=self.catalog,
            sqlite_path=self.db,manifest_path=self.manifest,
            generation_guard_factory=lambda:production_generation_lock(
                exclusive=False,channel="generation",
            ),
            semantic_guard_factory=lambda:production_generation_lock(
                exclusive=True,channel="semantic",
            ),
            semantic=True,laboratory_mode=True,operator_approved=True,
        )

    def roundtrip(self,pin,**kwargs):
        return execute_semantic_roundtrip_lab(
            self.query,self.route,pin=pin,catalog_file=self.catalog,
            laboratory_mode=True,operator_approved=True,**kwargs,
        )

    def forged(self,key,value):
        def runner(*args,**kwargs):
            from rag.runtime.knowledge_deletion_semantic_request_lab import (
                PinnedSemanticRequestV1,
            )
            req=PinnedSemanticRequestV1.parse(json.loads(kwargs["input"]))
            row={
                "state":"LAB_SEMANTIC_REQUEST_VALIDATED",
                "project_id":req.pin.project_id,
                "generation_id":req.pin.generation_id,
                "nonce":req.pin.nonce,
                "request_sha256":req.request_digest(),
                "route":req.route,
                "top_k":req.top_k,
                "result_count":0,
                "model_executed":False,
                "parent_locks_attested_by_worker":False,
                "activation_authorized":False,
                "operational_use_allowed":False,
            }
            if key is not None:
                row[key]=value
            return SimpleNamespace(returncode=0,stdout=json.dumps(row),stderr="")
        return runner

    def test_real_worker_roundtrip_returns_verified_correlation_not_results(self):
        with self.patch_root():
            with self.session() as pin:
                result=self.roundtrip(pin)
                self.assertEqual(result["state"],
                                 "LAB_PINNED_SEMANTIC_ROUNDTRIP_ONLY")
                self.assertEqual(result["generation_id"],"private_roundtrip")
                self.assertEqual(len(result["nonce"]),32)
                self.assertEqual(len(result["request_sha256"]),64)
                self.assertFalse(result["model_executed"])
                self.assertFalse(result["activation_authorized"])

    def test_forged_nonce_generation_digest_and_project_fail_closed(self):
        for key,value in (
            ("nonce","0"*32),("generation_id","private_wrong"),
            ("request_sha256","1"*64),("project_id","other-project"),
            ("state","LAB_OPERATIONAL_READY"),
            ("route","TEXT"),("top_k",4),
        ):
            with self.subTest(key=key):
                with self.patch_root():
                    with self.session() as pin:
                        with self.assertRaises(SemanticRoundtripLabError):
                            self.roundtrip(pin,runner=self.forged(key,value))

    def test_forged_operational_true_and_extra_response_key_fail_closed(self):
        for key,value in (
            ("activation_authorized",True),
            ("operational_use_allowed",True),
            ("model_executed",True),
            ("parent_locks_attested_by_worker",True),
            ("result_count",1),
            ("extra_field",123),
        ):
            with self.subTest(key=key):
                with self.patch_root():
                    with self.session() as pin:
                        with self.assertRaises(SemanticRoundtripLabError):
                            self.roundtrip(pin,runner=self.forged(key,value))

    def test_child_timeout_is_structured_error_and_lock_released(self):
        def timeout_runner(*args,**kwargs):
            raise subprocess.TimeoutExpired("synthetic",1)
        with self.patch_root():
            with self.assertRaisesRegex(SemanticRoundtripLabError,"timed out"):
                with self.session() as pin:
                    self.roundtrip(pin,runner=timeout_runner)
            with production_generation_lock(exclusive=True,channel="semantic"):
                pass

    def test_invalid_json_and_child_nonzero_fail_closed(self):
        for stdout,returncode in (("{broken",0),("{}",0),("",5)):
            def runner(*args,**kwargs):
                return SimpleNamespace(returncode=returncode,
                                       stdout=stdout,stderr="not disclosed")
            with self.patch_root():
                with self.session() as pin:
                    with self.assertRaises(SemanticRoundtripLabError):
                        self.roundtrip(pin,runner=runner)

    def test_invalid_timeout_and_unapproved_roundtrip_rejected(self):
        with self.patch_root():
            with self.session() as pin:
                for timeout in (0,-1,11,True,float("nan"),"2"):
                    with self.subTest(timeout=timeout):
                        with self.assertRaises(ValueError):
                            self.roundtrip(pin,timeout_seconds=timeout)
                with self.assertRaises(PermissionError):
                    execute_semantic_roundtrip_lab(
                        self.query,self.route,pin=pin,
                        catalog_file=self.catalog,laboratory_mode=False,
                        operator_approved=True,
                    )

    def test_catalog_changed_between_parent_pin_and_child_open_fails_closed(self):
        def swap_between_pin_and_child(*args, **kwargs):
            # Called after parent created its old pin and request, before child.
            original=self.catalog.read_bytes()
            try:
                data=json.loads(original)
                data["projects"]["private-lab"]["source_revision"]="newer"
                self.catalog.write_text(json.dumps(data),encoding="utf-8")
                return subprocess.run(*args, **kwargs)
            finally:
                self.catalog.write_bytes(original)

        with self.patch_root():
            with self.session() as pin:
                with self.assertRaises(SemanticRoundtripLabError):
                    self.roundtrip(pin,runner=swap_between_pin_and_child)
