import unittest

from protocol import (
    ProtocolConflict,
    ProtocolLedger,
    new_id,
    sha256_payload,
    validate_request_ack,
    validate_response_syn,
)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.ledger = ProtocolLedger()

    def test_roundtrip_syn_ack_both_directions(self):
        request_id = new_id("req")
        payload = {"target": "STATUS"}
        request_syn = {
            "type": "REQUEST_SYN",
            "request_id": request_id,
            "operation": "codebridge_status",
            "payload": payload,
        }
        request_ack = self.ledger.receive_request_syn("codebridge_status", payload, request_id)
        self.assertTrue(validate_request_ack(request_syn, request_ack))

        response_payload = {"overall": "READY", "terminals": 3}
        response_syn = self.ledger.prepare_response(request_id, response_payload)
        self.assertTrue(validate_response_syn(request_id, response_syn))
        response_ack = self.ledger.receive_response_ack(
            request_id,
            response_syn["response_id"],
            response_syn["response_hash"],
        )
        self.assertEqual(response_ack["type"], "RESPONSE_ACK")
        self.assertEqual(self.ledger.get_exchange(request_id)["state"], "RESPONSE_ACKED")

    def test_duplicate_request_is_idempotent(self):
        request_id = new_id("req")
        payload = {"a": 1}
        ack1 = self.ledger.receive_request_syn("status", payload, request_id)
        ack2 = self.ledger.receive_request_syn("status", payload, request_id)
        self.assertEqual(ack1, ack2)
        self.assertEqual(self.ledger.count(), 1)

    def test_same_request_id_with_other_payload_is_rejected(self):
        request_id = new_id("req")
        self.ledger.receive_request_syn("status", {"a": 1}, request_id)
        with self.assertRaises(ProtocolConflict):
            self.ledger.receive_request_syn("status", {"a": 2}, request_id)

    def test_wrong_response_ack_is_rejected(self):
        request_id = new_id("req")
        self.ledger.receive_request_syn("status", {}, request_id)
        syn = self.ledger.prepare_response(request_id, {"ok": True})
        with self.assertRaises(ProtocolConflict):
            self.ledger.receive_response_ack(request_id, syn["response_id"], "0" * 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
