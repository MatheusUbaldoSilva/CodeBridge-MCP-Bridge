"""F16 DEV binding test data: crafted preview, never live RAG."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from unittest import TestCase

from rag.runtime.knowledge_deletion_preview_binding_dev import (
    review_deletion_preview_binding_dev as review,
)

def preview(
    project="demo", selected=None, generation="gen-1", revision="rev-1",
    chunks=4, preserved=2,
):
    selected=sorted(["docs/a.md","src/b.py"] if selected is None else selected)
    fields=dict(
        schema_version=1,mode="READ_ONLY_REMOVAL_PREVIEW",
        project_id=project,generation=generation,source_revision=revision,
        selected_paths=selected,documents_to_remove=len(selected),
        chunks_to_remove=chunks,documents_to_preserve=preserved,
        chunks_to_preserve=preserved*2,
    )
    digest=sha256(json.dumps(
        fields,sort_keys=True,ensure_ascii=False,separators=(",",":")
    ).encode("utf-8")).hexdigest()
    fields.update(
        review_sha256=digest,operator_approved=False,deletion_authorized=False,
        candidate_created=False,public_pointer_updated=False,
        source_files_modified=False,
    )
    return fields

def check(proof=None,paths=None,**kw):
    return review("demo",["src/b.py","docs/a.md"] if paths is None else paths,
                  preview() if proof is None else proof,**kw)

class F16PreviewBindingTests(TestCase):
    def test_coherent_caller_pins_still_not_authorized(self):
        r=check(expected_generation="gen-1",expected_source_revision="rev-1")
        self.assertEqual(r["state"],"F16_DEV_PREVIEW_FIELDS_COHERENT_NO_AUTHORITY")
        self.assertTrue(all(r["checks"].values()))
        self.assertFalse(r["activation_authorized"])
        self.assertFalse(r["current_generation_attested"])
        self.assertFalse(r["preview_origin_authenticated"])
        self.assertFalse(r["operational_use_allowed"])
        self.assertIn("OPERATIONAL_DELETION_BLOCKED",r["blockers"])
    def test_missing_caller_pins_fails_closed(self):
        r=check()
        self.assertEqual(r["state"],"F16_DEV_PREVIEW_MISMATCH")
        self.assertFalse(r["checks"]["caller_expected_generation_matches"])
        self.assertFalse(r["checks"]["caller_expected_revision_matches"])
    def test_sorted_selection_is_order_independent(self):
        a=check(paths=["docs/a.md","src/b.py"])
        b=check(paths=["src/b.py","docs/a.md"])
        self.assertEqual(a["selection_sha256"],b["selection_sha256"])
    def test_changed_selection_fails(self):
        p=preview()
        r=check(proof=p, paths=["docs/a.md"])
        self.assertFalse(r["checks"]["exact_sorted_paths_match_selection"])
        self.assertFalse(r["checks"]["document_count_matches_selection"])
    def test_wrong_project_fails(self):
        p=preview(project="another")
        r=check(proof=p)
        self.assertFalse(r["checks"]["project_id_matches_selection"])
    def test_wrong_generation_fails_even_with_valid_digest(self):
        r=check(preview(generation="gen-2"),
                expected_generation="gen-1",expected_source_revision="rev-1")
        self.assertFalse(r["checks"]["caller_expected_generation_matches"])
    def test_wrong_revision_fails_even_with_valid_digest(self):
        r=check(preview(revision="rev-2"),
                expected_generation="gen-1",expected_source_revision="rev-1")
        self.assertFalse(r["checks"]["caller_expected_revision_matches"])
    def test_modified_preview_hash_fails(self):
        p=preview()
        p["review_sha256"]="a"*64
        r=check(proof=p)
        self.assertFalse(r["checks"]["preview_digest_matches_canonical_payload"])
    def test_modified_counts_without_updated_hash_fails(self):
        p=preview()
        p["chunks_to_preserve"]+=1
        r=check(proof=p)
        self.assertFalse(r["checks"]["preview_digest_matches_canonical_payload"])
    def test_modified_counts_with_updated_hash_are_still_untrusted(self):
        p=preview(chunks=999)
        r=check(proof=p,expected_generation="gen-1",
                expected_source_revision="rev-1")
        self.assertTrue(r["checks"]["preview_digest_matches_canonical_payload"])
        self.assertFalse(r["current_generation_attested"])
        self.assertFalse(r["activation_authorized"])
    def test_forged_operation_flags_rejected(self):
        for name in ("operator_approved","deletion_authorized",
                     "candidate_created","public_pointer_updated",
                     "source_files_modified"):
            p=preview()
            p[name]=True
            with self.subTest(flag=name),self.assertRaises(ValueError):
                check(proof=p)
    def test_extra_operational_claim_rejected(self):
        p=preview()
        p["active_generation_authorized"]=True
        with self.assertRaises(ValueError):
            check(proof=p)
    def test_missing_required_field_rejected(self):
        for name in ("review_sha256","selected_paths","generation",
                     "source_revision","schema_version","deletion_authorized"):
            p=preview()
            p.pop(name)
            with self.subTest(field=name),self.assertRaises(ValueError):
                check(proof=p)
    def test_malformed_header_and_versions_rejected(self):
        mutations=(
            ("mode","EXECUTE"),("schema_version",True),
            ("schema_version",2),("generation",""),
            ("source_revision",None),("review_sha256","A"*64),
            ("review_sha256","z"*64),
        )
        for key,value in mutations:
            p=preview()
            p[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                check(proof=p)
    def test_negative_boolean_or_zero_chunks_rejected(self):
        for name,value in (
            ("documents_to_remove",True),("documents_to_remove",-1),
            ("chunks_to_remove",False),("chunks_to_remove",0),
            ("documents_to_preserve",-1),("chunks_to_preserve",-1),
        ):
            p=preview()
            p[name]=value
            with self.subTest(name=name,value=value),self.assertRaises(ValueError):
                check(proof=p)
    def test_unsorted_or_duplicate_preview_selection_mismatch(self):
        p=preview()
        p["selected_paths"].reverse()
        r=check(proof=p)
        self.assertFalse(r["checks"]["exact_sorted_paths_match_selection"])
        p=preview()
        p["selected_paths"]=["docs/a.md","docs/a.md"]
        r=check(proof=p)
        self.assertFalse(r["checks"]["exact_sorted_paths_match_selection"])
    def test_invalid_caller_pins_rejected(self):
        for value in ("",True,123,"g"*257):
            with self.subTest(value=value),self.assertRaises(ValueError):
                check(expected_generation=value)
            with self.subTest(value=value),self.assertRaises(ValueError):
                check(expected_source_revision=value)
    def test_bad_selection_rejected_by_f15(self):
        for selection in (["../escape"],["a","A"],["c:ads"]):
            with self.subTest(selection=selection),self.assertRaises(ValueError):
                check(paths=selection)
    def test_no_modification_and_no_raw_paths_in_response(self):
        p=preview()
        before=deepcopy(p)
        r=check(proof=p)
        self.assertEqual(p,before)
        self.assertNotIn("docs/a.md",str(r))
        self.assertNotIn("src/b.py",str(r))
    def test_preview_type_rejected(self):
        for p in (None,[],True,"preview",0):
            with self.subTest(type=type(p)),self.assertRaises(ValueError):
                review("demo",["docs/a.md","src/b.py"],p)
