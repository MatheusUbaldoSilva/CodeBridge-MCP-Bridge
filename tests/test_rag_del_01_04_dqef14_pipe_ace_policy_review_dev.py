"""F14 tests: G18 ACE metadata is not Windows effective access."""
from copy import deepcopy
from unittest import TestCase
from rag.runtime.knowledge_deletion_pipe_acl_policy_review_dev import (
    review_pipe_ace_inventory_policy_dev as review,
)


def ace(kind="ALLOW", principal="OTHER_PRINCIPAL", mask="0012019f"):
    return {
        "ace_type": kind, "principal_class": principal,
        "access_mask_hex": mask, "sid_sha256": "a"*64,
    }


def inventory(aces=None):
    entries = [ace()] if aces is None else aces
    return {
        "state": "WIN32_PIPE_ACE_INVENTORY_READ_ONLY",
        "ace_count": len(entries),
        "aces": entries,
        "broad_allow_ace_detected": any(
            x.get("ace_type")=="ALLOW" and
            x.get("principal_class") in {"EVERYONE","BUILTIN_USERS"}
            for x in entries if type(x) is dict
        ),
        "unsupported_ace_detected": False,
        "dacl_observed": True,
        "private_acl_attested": False,
        "effective_access_attested": False,
        "child_handle_inheritance_attested": False,
        "activation_authorized": False,
        "operational_use_allowed": False,
        "read_only": True,
        "blockers": [],
    }


class PipeAclPolicyReviewDevTests(TestCase):
    def test_even_private_looking_ace_is_not_attested(self):
        r = review(inventory())
        self.assertTrue(r["ace_metadata_consistent"])
        self.assertTrue(r["unknown_allow_sid_needs_owner_binding"])
        self.assertFalse(r["effective_windows_access_attested"])
        self.assertFalse(r["installed_peer_token_attested"])
        self.assertFalse(r["activation_authorized"])
        self.assertIn("WINDOWS_EFFECTIVE_ACCESSCHECK_NOT_PERFORMED",r["blockers"])

    def test_every_broad_principal_allow_blocks(self):
        principals = (
            "EVERYONE","AUTHENTICATED_USERS","ANONYMOUS_LOGON",
            "BUILTIN_USERS","NETWORK","INTERACTIVE","SERVICE",
            "BUILTIN_GUESTS","ALL_APPLICATION_PACKAGES",
            "ALL_RESTRICTED_APPLICATION_PACKAGES","REMOTE_DESKTOP_USERS",
        )
        for name in principals:
            with self.subTest(principal=name):
                entry=inventory([ace(principal=name)])
                r=review(entry)
                self.assertTrue(r["broad_allow_ace_detected"])
                self.assertIn("BROAD_PRINCIPAL_ALLOW_ACE_OBSERVED",r["blockers"])
                self.assertFalse(r["operational_use_allowed"])

    def test_broad_deny_is_not_broad_allow_or_effective_access(self):
        r=review(inventory([ace(kind="DENY",principal="EVERYONE"),ace()]))
        self.assertFalse(r["broad_allow_ace_detected"])
        self.assertFalse(r["effective_windows_access_attested"])

    def test_null_or_failed_inventory_fails(self):
        for mutation in (
            {"state":"WIN32_PIPE_ACE_INVENTORY_BLOCKED"},
            {"dacl_observed":False},
            {"unsupported_ace_detected":True},
            {"blockers":["ACL_UNVERIFIED"]},
            {"ace_count":2},
            {"ace_count":True},
        ):
            data=inventory()
            data.update(mutation)
            with self.subTest(mutation=mutation):
                r=review(data)
                self.assertFalse(r["ace_metadata_consistent"])
                self.assertFalse(r["activation_authorized"])

    def test_unsafe_grant_claims_rejected(self):
        for key in ("private_acl_attested","effective_access_attested",
                    "child_handle_inheritance_attested","activation_authorized",
                    "operational_use_allowed"):
            data=inventory()
            data[key]=True
            with self.subTest(key=key),self.assertRaises(ValueError):
                review(data)

    def test_readonly_must_be_true(self):
        for bad in (None,False,"yes",1):
            data=inventory()
            data["read_only"]=bad
            with self.subTest(value=bad),self.assertRaises(ValueError):
                review(data)

    def test_structural_malformed_aces(self):
        invalid = (
            None,True,{"ace_type":"ALLOW"},
            ace(mask="fffffffff"),ace(mask="FFFFFFFF"),
            ace(mask="zzzzzzzz"),ace(kind="CUSTOM"),
            ace(principal="TRUSTED"),
            ace()|{"sid_sha256":"XYZ"},
            ace()|{"activation_authorized":True},
        )
        for entry in invalid:
            data=inventory([entry])
            with self.subTest(entry=entry):
                r=review(data)
                self.assertIn("MALFORMED_OR_UNSUPPORTED_ACE",r["blockers"])
                self.assertFalse(r["ace_metadata_consistent"])

    def test_no_allow_ace_fail_closed(self):
        r=review(inventory([ace(kind="DENY")]))
        self.assertIn("NO_ALLOW_ACE_OBSERVED",r["blockers"])
        self.assertEqual(r["allow_ace_count"],0)

    def test_none_or_overlimit_aces_rejected(self):
        with self.assertRaises(ValueError):review(inventory([])|{"aces":None})
        with self.assertRaises(ValueError):review(inventory([ace()]*65))
        with self.assertRaises(ValueError):review(inventory([])|{"aces":{}})

    def test_bad_record_types_rejected(self):
        for bad in (None,False,[],0,"x"):
            with self.subTest(value=bad),self.assertRaises(ValueError):
                review(bad)

    def test_no_mutation_and_no_sid_hash_exported(self):
        data=inventory([ace()])
        before=deepcopy(data)
        r=review(data)
        self.assertEqual(data,before)
        self.assertNotIn("sid_sha256",str(r))
        self.assertNotIn("a"*64,str(r))

    def test_forged_inventory_broad_claim_flag_blocks(self):
        data=inventory()
        data["broad_allow_ace_detected"]=True
        r=review(data)
        self.assertIn("BROAD_PRINCIPAL_ALLOW_ACE_OBSERVED",r["blockers"])
        self.assertFalse(r["activation_authorized"])
