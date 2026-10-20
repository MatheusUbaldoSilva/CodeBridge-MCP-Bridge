"""V1.03-D-C heartbeat lease tests on isolated temporary Git and SQLite."""
from tests.test_incremental_job_queue import DurableQueueTests
from rag.runtime.incremental_job_queue import renew_job_lease

class WorkerLeaseHeartbeatTests(DurableQueueTests):
    def test_renewal_cas_and_expiry(self):
        self.enqueue(queue_enabled=True, now_epoch=140)
        claim = self.claim(now_epoch=141, lease_seconds=20)
        job, token = claim["job_id"], claim["lease_token"]
        renew = lambda tok, now, **kw: renew_job_lease(
            self.db, job, tok, now_epoch=now, queue_enabled=True, **kw)
        self.assertEqual(renew(token, 145, lease_seconds=30)["state"], "LEASE_RENEWED")
        self.assertEqual(renew("0"*32, 146)["state"], "STALE_OR_EXPIRED_LEASE")
        self.assertEqual(renew(token, 176)["state"], "STALE_OR_EXPIRED_LEASE")
        second = self.claim(now_epoch=176)
        self.assertEqual(second["state"], "CLAIMED_FOR_OFFLINE_STAGING")
        self.assertNotEqual(second["lease_token"], token)
        self.assertEqual(renew(token, 177)["state"], "STALE_OR_EXPIRED_LEASE")
        self.assertEqual(renew(second["lease_token"], 177)["state"], "LEASE_RENEWED")

    def test_disabled_and_invalid_identity_never_change_state(self):
        self.enqueue(queue_enabled=True, now_epoch=140)
        claim = self.claim(now_epoch=141)
        args = (self.db, claim["job_id"], claim["lease_token"])
        self.assertEqual(renew_job_lease(*args, now_epoch=142)["state"], "AUTO_INDEX_DISABLED")
        self.assertEqual(renew_job_lease(self.db, "invalid", claim["lease_token"],
                       queue_enabled=True, now_epoch=142)["state"], "INVALID_LEASE_IDENTITY")
        self.assertEqual(renew_job_lease(*args, lease_seconds=0,
                       queue_enabled=True, now_epoch=142)["state"], "INVALID_LEASE_POLICY")
