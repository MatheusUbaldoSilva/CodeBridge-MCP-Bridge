"""Strict decoder for synthetic lab snapshot reports; no production access."""
from __future__ import annotations

import json


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate fixture report key")
        result[key] = value
    return result


def _reject_nonfinite_number(token):
    raise ValueError("non-finite number in fixture report")


def decode_fixture_report(contents):
    """Reject ambiguous JSON members at any nesting level."""
    report = json.loads(contents, object_pairs_hook=_reject_duplicate_keys,
                        parse_constant=_reject_nonfinite_number)
    if not isinstance(report, dict):
        raise ValueError("fixture report must be a JSON object")
    return report
