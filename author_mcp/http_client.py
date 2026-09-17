import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    new_id,
    sha256_payload,
    validate_request_ack,
    validate_response_syn,
)


class ProtocolHTTPClient:
    def __init__(self, base_url="http://127.0.0.1:8766", timeout=3.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)

    def _post(self, path, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise ProtocolError(f"HTTP {exc.code}: {raw}") from exc
        except URLError as exc:
            raise ProtocolError(f"adapter indisponivel: {exc}") from exc
        if not data.get("ok"):
            raise ProtocolError(str(data))
        return data

    def exchange(self, operation, payload=None, request_id=None):
        payload = payload or {}
        request_id = request_id or new_id("req")
        request_syn = {
            "protocol": PROTOCOL_VERSION,
            "type": "REQUEST_SYN",
            "request_id": request_id,
            "operation": operation,
            "payload": payload,
            "request_hash": sha256_payload(payload),
        }
        ack_data = self._post("/v1/request-syn", request_syn)
        request_ack = ack_data["request_ack"]
        validate_request_ack(request_syn, request_ack)

        response_data = self._post("/v1/response-syn", {"request_id": request_id})
        response_syn = response_data["response_syn"]
        validate_response_syn(request_id, response_syn)

        response_ack = {
            "protocol": PROTOCOL_VERSION,
            "type": "RESPONSE_ACK",
            "request_id": request_id,
            "response_id": response_syn["response_id"],
            "response_hash": response_syn["response_hash"],
        }
        final_data = self._post("/v1/response-ack", response_ack)
        echoed_ack = final_data["response_ack"]
        for key in ("request_id", "response_id", "response_hash"):
            if echoed_ack.get(key) != response_ack[key]:
                raise ProtocolError(f"RESPONSE_ACK divergente em {key}")
        return {
            "request_syn": request_syn,
            "request_ack": request_ack,
            "response_syn": response_syn,
            "response_ack": echoed_ack,
            "payload": response_syn["payload"],
        }
