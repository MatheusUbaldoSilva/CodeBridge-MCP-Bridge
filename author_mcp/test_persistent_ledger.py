import tempfile
import unittest
from pathlib import Path

from persistent_ledger import PersistentProtocolLedger
from protocol import ProtocolConflict, new_id, validate_request_ack, validate_response_syn


class PersistentLedgerTests(unittest.TestCase):
    def test_restart_preserves_full_handshake(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "protocol.db"
            ledger = PersistentProtocolLedger(db)
            request_id = new_id("req")
            payload = {"operation": "status", "n": 1}
            syn = {"request_id": request_id, "payload": payload}
            ack = ledger.receive_request_syn("status", payload, request_id)
            self.assertTrue(validate_request_ack(syn, ack))

            ledger = PersistentProtocolLedger(db)
            response = ledger.prepare_response(request_id, {"overall": "READY"})
            self.assertTrue(validate_response_syn(request_id, response))
            response_ack = ledger.receive_response_ack(
                request_id, response["response_id"], response["response_hash"]
            )
            self.assertEqual(response_ack["type"], "RESPONSE_ACK")

            ledger = PersistentProtocolLedger(db)
            self.assertEqual(ledger.get_exchange(request_id)["state"], "RESPONSE_ACKED")

    def test_duplicate_survives_restart_and_conflict_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "protocol.db"
            request_id = new_id("req")
            ledger = PersistentProtocolLedger(db)
            first = ledger.receive_request_syn("status", {"a": 1}, request_id)

            ledger = PersistentProtocolLedger(db)
            second = ledger.receive_request_syn("status", {"a": 1}, request_id)
            self.assertEqual(first, second)
            with self.assertRaises(ProtocolConflict):
                ledger.receive_request_syn("status", {"a": 2}, request_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
