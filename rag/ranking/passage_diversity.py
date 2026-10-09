"""Deterministic, query-independent passage diversity for document reranking."""
from __future__ import annotations
import re
from typing import Sequence
from rag.contracts import SearchResult

def select_diverse_passages(ranked:Sequence[tuple[float,SearchResult]],limit:int=3)->tuple[SearchResult,...]:
    if not isinstance(limit,int) or not 1<=limit<=3:
        raise ValueError("limit must be 1..3")
    candidates=sorted(ranked,key=lambda v:(-v[0],v[1].chunk_id))
    if not candidates:return ()
    project={x.metadata.project_id for _,x in candidates}
    document={(x.document_id,x.metadata.path,x.metadata.git_branch) for _,x in candidates}
    if len(project)>1 or len(document)>1:raise ValueError("mixed document or project")
    selected=[]
    used=set()
    tokens=[]
    for _,item in candidates:
        if item.chunk_id in used:continue
        used.add(item.chunk_id)
        terms=set(re.findall(r"[a-zA-Z_][a-zA-Z_0-9]{2,}",item.content.casefold()))
        tokens.append((item,terms))
    if not tokens:return ()
    selected.append(tokens.pop(0))
    while tokens and len(selected)<limit:
        def relevance(entry):
            content=entry[1]
            novelty=1-max((len(content & past[1])/max(1,len(content | past[1])) for past in selected),default=0)
            return novelty
        index=max(range(len(tokens)),key=lambda i:(relevance(tokens[i]),-i))
        selected.append(tokens.pop(index))
    return tuple(item for item,_ in selected)
