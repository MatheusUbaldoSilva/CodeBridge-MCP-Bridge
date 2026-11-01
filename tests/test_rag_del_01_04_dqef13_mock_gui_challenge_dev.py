"""F13: offline HMAC protocol adversarial contract (never installed attestation)."""
from copy import deepcopy
from unittest import TestCase
from rag.runtime.knowledge_deletion_gui_challenge_contract_dev import (
    make_offline_gui_challenge_dev as make,
    make_mock_gui_response_dev as sign,
    review_mock_gui_response_dev as verify,
)

KEY = b"this-is-a-test-only-secret-never-deploy-456"
S1 = "1" * 64
S2 = "2" * 64


def challenge():
    return make(S1, 102, 1000, S2, issued_at_ms=2000, ttl_ms=5000)


def check(ch, response=None, *, secret=KEY, now=2500, used=None):
    return verify(ch, response if response is not None else sign(ch, KEY),
                  secret, observed_at_ms=now,
                  consumed_nonces=used if used is not None else set())


class F13OfflineChallengeTests(TestCase):
    def test_mock_valid_still_not_installed(self):
        ch = challenge()
        used = set()
        result = check(ch, used=used)
        self.assertTrue(result["mock_contract_verified"])
        self.assertIn(ch["nonce_hex"], used)
        for name in ("installed_gui_attested", "activation_authorized",
                     "operational_use_allowed", "ready_for_operational_pilot"):
            self.assertFalse(result[name])
        self.assertTrue(result["dev_mock_only"])
        self.assertTrue(result["read_only"])

    def test_expired_and_future_challenges_fail(self):
        ch = challenge()
        for now in (1999, 7001, 20_000):
            with self.subTest(now=now):
                out = check(ch, now=now)
                self.assertFalse(out["mock_contract_verified"])
                self.assertIn("MOCK_CHALLENGE_OUTSIDE_TIME_WINDOW", out["blockers"])

    def test_boundary_timestamps_accepted_only_in_mock(self):
        ch = challenge()
        for now in (2000, 7000):
            with self.subTest(now=now):
                self.assertTrue(check(ch, now=now)["mock_contract_verified"])

    def test_replay_consumed_nonce_rejected(self):
        ch = challenge()
        used = set()
        self.assertTrue(check(ch, used=used)["mock_contract_verified"])
        result = check(ch, used=used)
        self.assertFalse(result["mock_contract_verified"])
        self.assertIn("MOCK_CHALLENGE_REPLAY", result["blockers"])

    def test_different_random_challenges(self):
        self.assertNotEqual(challenge()["nonce_hex"], challenge()["nonce_hex"])

    def test_wrong_secret_and_tampered_mac(self):
        ch = challenge()
        res = sign(ch, KEY)
        self.assertFalse(check(ch, res, secret=b"x" * 32)["mock_contract_verified"])
        res["mock_hmac_sha256"] = "f" * 64
        self.assertFalse(check(ch, res)["mock_contract_verified"])

    def test_mismatch_pid_birth_code_snapshot_nonce_and_time(self):
        ch = challenge()
        signed = sign(ch, KEY)
        for field, value in (
            ("gui_pid", 333), ("gui_birth_epoch_ms", 12345),
            ("snapshot_sha256", "3" * 64),
            ("loaded_code_sha256", "4" * 64),
            ("nonce_hex", "0" * 64),
            ("expires_at_ms", 6000),
        ):
            modified = deepcopy(ch)
            modified[field] = value
            with self.subTest(field=field):
                self.assertFalse(check(modified, signed)["mock_contract_verified"])

    def test_forged_flags_and_extra_fields_rejected(self):
        ch=challenge()
        for key,value in (("activation_authorized",True),
                          ("installed_gui_attested",True),
                          ("loaded_code_attested",True)):
            forged=deepcopy(ch)
            forged[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                check(forged)
        res=sign(ch,KEY)
        res["activation_authorized"]=True
        self.assertFalse(check(ch,res)["mock_contract_verified"])

    def test_invalid_response_types_fail_closed(self):
        ch=challenge()
        for invalid in (None,[],True,0,"signed",{}):
            with self.subTest(value=invalid):
                self.assertFalse(verify(ch, invalid, KEY, observed_at_ms=2500, consumed_nonces=set())["activation_authorized"])

    def test_invalid_challenge_inputs(self):
        for overrides in (
            dict(snapshot_sha256="A"*64), dict(gui_pid=True),
            dict(gui_pid=-1), dict(gui_birth_epoch_ms=False),
            dict(loaded_code_sha256="g"*64),
            dict(issued_at_ms=0), dict(ttl_ms=0),
            dict(ttl_ms=10001), dict(ttl_ms=True),
        ):
            params=dict(snapshot_sha256=S1,gui_pid=102,
                        gui_birth_epoch_ms=1000,loaded_code_sha256=S2,
                        issued_at_ms=2000,ttl_ms=5000)
            params.update(overrides)
            with self.subTest(overrides=overrides),self.assertRaises(ValueError):
                make(**params)

    def test_invalid_mock_verification_context(self):
        ch=challenge()
        res=sign(ch,KEY)
        for bad in (b"",b"weak",True,"secret",None):
            with self.subTest(secret=bad),self.assertRaises(ValueError):
                verify(ch,res,bad,observed_at_ms=2500,consumed_nonces=set())
        for used in ([],None,{"bad"},set(["A"*64])):
            with self.subTest(used=used),self.assertRaises(ValueError):
                verify(ch,res,KEY,observed_at_ms=2500,consumed_nonces=used)
        for now in (True,0,None,"3000"):
            with self.subTest(now=now),self.assertRaises(ValueError):
                verify(ch,res,KEY,observed_at_ms=now,consumed_nonces=set())

    def test_failure_never_consumes_nonce(self):
        ch=challenge()
        used=set()
        result=check(ch,now=8000,used=used)
        self.assertFalse(result["mock_contract_verified"])
        self.assertEqual(used,set())

    def test_challenge_and_response_are_json_serializable(self):
        import json
        ch=challenge()
        self.assertEqual(json.loads(json.dumps(ch)),ch)
        self.assertEqual(json.loads(json.dumps(sign(ch,KEY)))["challenge"],ch)
