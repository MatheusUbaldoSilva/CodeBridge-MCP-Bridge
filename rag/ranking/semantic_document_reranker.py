"""Document-level semantic evidence aggregation, independent of benchmark IDs."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import replace
from typing import Sequence
from rag.contracts import SearchResult


def rerank_documents(
    rankings: Sequence[Sequence[SearchResult]],
    *,
    top_k: int = 10,
    rrf_k: int = 20,
    repetition_decay: float = 1.0,
) -> tuple[SearchResult, ...]:
    """Aggregate lexical and semantic evidence across chunks of each source.

    The vector rankings already represent query-document embedding similarities.
    This deterministic score fusion preserves project, branch and path-filter
    boundaries established by the retrieval stage.
    """
    if not isinstance(top_k,int) or top_k<1 or not isinstance(rrf_k,int) or rrf_k<1:
        raise ValueError("top_k and rrf_k must be positive integers")
    if not 0 <= repetition_decay <= 1:
        raise ValueError("repetition_decay must be between 0 and 1")
    scores=defaultdict(float)
    representatives={}
    modes=defaultdict(set)
    namespaces=set()
    for ranking in rankings:
        occurrences=defaultdict(int)
        seen_chunks=set()
        for position, result in enumerate(ranking,1):
            if not isinstance(result,SearchResult):
                raise ValueError("rankings must contain SearchResult")
            if result.chunk_id in seen_chunks:
                continue
            seen_chunks.add(result.chunk_id)
            key=(result.metadata.project_id,result.document_id,result.metadata.path,result.metadata.git_branch)
            namespaces.add(result.metadata.project_id)
            occurrences[key]+=1
            contribution=1.0/(rrf_k+position)
            scores[key]+=contribution/(1+repetition_decay*(occurrences[key]-1))
            modes[key].update(result.retrieval_modes)
            old=representatives.get(key)
            if old is None or position<old[0]:
                representatives[key]=(position,result)
    if len(namespaces)>1:
        raise ValueError("cross-project ranking fusion forbidden")
    order=sorted(scores,key=lambda key:(-scores[key],key[0],key[1],key[2] or ""))
    return tuple(replace(representatives[key][1],score=scores[key],rank=i,retrieval_modes=tuple(sorted(modes[key])))
                 for i,key in enumerate(order[:top_k],1))
