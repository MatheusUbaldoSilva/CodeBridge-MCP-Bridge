"""Durable isolated batch receipt checks for RAG-AUTO-05-E."""
import json
from pathlib import Path
import tempfile
import unittest

from rag.runtime.auto_index_incremental_checkpoint import (
    persist_isolated_batch_receipt,read_isolated_batch_receipt,
)
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


class BatchReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.id="a"*32
        self.record={"mode":"ISOLATED_STAGE_BATCH_WRITTEN","vectors_written":3,
                     "public_pointer_updated":False,
                     "requires_staging_revalidation":True}

    def test_atomic_receipt_requires_revalidation(self):
        saved=persist_isolated_batch_receipt(self.root,self.id,self.record,allow_write=True)
        self.assertTrue(saved["revalidation_required"])
        read=read_isolated_batch_receipt(self.root,self.id)
        self.assertEqual(read["vectors_written"],3)
        self.assertEqual(read["state"],"NEEDS_QDRANT_REVALIDATION")
        self.assertFalse(read["public_pointer_updated"])
        self.assertFalse((self.root/("batch_"+self.id+".writing")).exists())

    def test_duplicate_and_interrupted_receipts_fail_closed(self):
        persist_isolated_batch_receipt(self.root,self.id,self.record,allow_write=True)
        with self.assertRaises(IncrementalPlanError):
            persist_isolated_batch_receipt(self.root,self.id,self.record,allow_write=True)
        other="b"*32
        (self.root/("batch_"+other+".writing")).write_text("interrupted")
        with self.assertRaises(IncrementalPlanError):
            persist_isolated_batch_receipt(self.root,other,self.record,allow_write=True)

    def test_tampering_detected(self):
        persist_isolated_batch_receipt(self.root,self.id,self.record,allow_write=True)
        target=self.root/("batch_"+self.id+".json")
        payload=json.loads(target.read_text(encoding="utf-8"))
        payload["vectors_written"]=99
        target.write_text(json.dumps(payload),encoding="utf-8")
        with self.assertRaises(IncrementalPlanError):
            read_isolated_batch_receipt(self.root,self.id)

    def test_forged_count_types_and_oversized_batch_refused(self):
        for count in (True, 0, 257, -1, 1.5):
            with self.subTest(count=count):
                with self.assertRaises(IncrementalPlanError):
                    persist_isolated_batch_receipt(
                        self.root,self.id,{**self.record,"vectors_written":count},
                        allow_write=True,
                    )
        self.assertFalse((self.root/("batch_"+self.id+".json")).exists())

    def test_read_denies_invalid_schema_even_with_recomputed_digest(self):
        import hashlib
        persist_isolated_batch_receipt(self.root,self.id,self.record,allow_write=True)
        target=self.root/("batch_"+self.id+".json")
        payload=json.loads(target.read_text(encoding="utf-8"))
        payload["schema_version"]=2
        payload.pop("receipt_sha256")
        compact=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
        payload["receipt_sha256"]=hashlib.sha256(compact).hexdigest()
        target.write_text(json.dumps(payload),encoding="utf-8")
        with self.assertRaises(IncrementalPlanError):
            read_isolated_batch_receipt(self.root,self.id)

    def test_oversized_or_nonobject_json_receipt_is_rejected(self):
        target=self.root/("batch_"+self.id+".json")
        target.write_bytes(b"x"*16385)
        with self.assertRaises(IncrementalPlanError):
            read_isolated_batch_receipt(self.root,self.id)
        target.write_text("[]",encoding="utf-8")
        with self.assertRaises(IncrementalPlanError):
            read_isolated_batch_receipt(self.root,self.id)

    def test_missing_permission_or_wrong_record_denied(self):
        with self.assertRaises(PermissionError):
            persist_isolated_batch_receipt(self.root,self.id,self.record)
        with self.assertRaises(IncrementalPlanError):
            persist_isolated_batch_receipt(
                self.root,self.id,{**self.record,"public_pointer_updated":True},
                allow_write=True,
            )
        with self.assertRaises(IncrementalPlanError):
            read_isolated_batch_receipt(self.root,"not-a-valid-id")
