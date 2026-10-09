"""Optional local cross-encoder reranking via llama.cpp's /reranking endpoint.

No model downloads, process launches, implicit network exposure or auto-enablement.
The caller must supply an already-running trusted localhost reranking service.
"""
from __future__ import annotations

from dataclasses import replace
import json
import math
from typing import Sequence
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from rag.contracts import SearchResult


class RerankerUnavailable(RuntimeError):
    """The local model endpoint cannot be used safely."""


def _trusted_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"/reranking", "/rerank"} or not parsed.port):
        raise ValueError("Reranker endpoint must be HTTP loopback with /reranking")
    return endpoint


def cross_encoder_rerank(
    query: str,
    candidates: Sequence[SearchResult],
    *,
    endpoint: str = "http://127.0.0.1:8081/reranking",
    top_k: int = 10,
    timeout_seconds: float = 15.0,
) -> tuple[SearchResult, ...]:
    """Rerank scoped candidates, failing closed on model or protocol failures.

    Results are only a permutation of supplied candidates: no new source can
    enter from the reranker service. This is not an automatic model loader.
    """
    _trusted_endpoint(endpoint)
    if not isinstance(query, str) or not query.strip():
        raise ValueError("non-empty query is required")
    if not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be positive")
    if not (0 < float(timeout_seconds) <= 60):
        raise ValueError("timeout must be 0..60s")
    if len(candidates) > 64:
        raise ValueError("too many candidates for local reranking")
    if not candidates:
        return ()
    if any(not isinstance(item, SearchResult) for item in candidates):
        raise ValueError("all candidates must be SearchResult")
    if len({item.metadata.project_id for item in candidates}) != 1:
        raise ValueError("cross-project reranking is forbidden")

    payload = json.dumps(
        {"query": query, "documents": [item.content[:6000] for item in candidates]},
        ensure_ascii=False,
    ).encode("utf-8")
    req = Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=timeout_seconds) as res:
            if res.status != 200:
                raise RerankerUnavailable(f"local reranker returned HTTP {res.status}")
            raw = res.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise RerankerUnavailable("reranker response exceeded size limit")
    except (OSError, URLError) as exc:
        raise RerankerUnavailable("local reranker unavailable") from exc
    try:
        result = json.loads(raw)
        entries = result["results"]
        if not isinstance(entries, list) or len(entries) != len(candidates):
            raise ValueError("incomplete reranker results")
        scores = {}
        for entry in entries:
            index = entry["index"]
            score = float(entry["relevance_score"])
            if (not isinstance(index, int) or isinstance(index, bool)
                    or not 0 <= index < len(candidates) or index in scores
                    or not math.isfinite(score)):
                raise ValueError("invalid reranker index or relevance score")
            scores[index] = score
        if len(scores) != len(candidates):
            raise ValueError("missing reranker scores")
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise RerankerUnavailable("invalid local reranker response") from exc
    ordered = sorted(scores, key=lambda i: (-scores[i], i))
    return tuple(
        replace(candidates[i], score=scores[i], rank=rank)
        for rank, i in enumerate(ordered[:top_k], 1)
    )
