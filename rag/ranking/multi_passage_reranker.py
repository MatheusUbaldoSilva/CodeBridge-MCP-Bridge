"""Multi-passage reranking over already authorized retrieval candidates."""
from __future__ import annotations
from dataclasses import replace
from collections import defaultdict
from typing import Sequence
from rag.contracts import SearchResult
from rag.ranking.local_cross_encoder import cross_encoder_rerank
from rag.ranking.passage_diversity import select_diverse_passages

def rerank_multi_passage(query:str,rankings:Sequence[Sequence[SearchResult]],*,top_k:int=10,
                         documents_limit:int=20,passages_per_document:int=3,rrf_k:int=10,
                         endpoint:str="http://127.0.0.1:8081/reranking",diverse:bool=False):
    """Score up to three distinct passages per document; only rerank authorized input."""
    if not 1<=documents_limit<=20 or not 1<=passages_per_document<=3 or not 1<=top_k<=documents_limit:
        raise ValueError("invalid bounded multi-passage limits")
    if not isinstance(rrf_k,int) or rrf_k<=0: raise ValueError("rrf_k must be positive")
    scores=defaultdict(float)
    grouped=defaultdict(dict)
    projects=set()
    for ranking in rankings:
        repeats=defaultdict(int)
        for pos,result in enumerate(ranking,1):
            if not isinstance(result,SearchResult): raise ValueError("invalid candidate")
            projects.add(result.metadata.project_id)
            key=(result.metadata.project_id,result.document_id,result.metadata.path,result.metadata.git_branch)
            repeats[key]+=1
            evidence=1/(rrf_k+pos)/(repeats[key])
            scores[key]+=evidence
            current=grouped[key].get(result.chunk_id)
            if current is None or evidence>current[0]:
                grouped[key][result.chunk_id]=(evidence,result)
    if len(projects)>1:raise ValueError("mixed projects forbidden")
    ranked=sorted(scores,key=lambda k:(-scores[k],k[1],k[2] or ""))[:documents_limit]
    passages=[]
    owners=[]
    for key in ranked:
        selected=sorted(grouped[key].values(),key=lambda pair:(-pair[0],pair[1].chunk_id))[:passages_per_document] if not diverse else [
            (grouped[key][item.chunk_id][0],item) for item in select_diverse_passages(
                tuple(grouped[key].values()),passages_per_document)]
        for _,item in selected:
            owners.append(key)
            passages.append(item)
    if not passages:return ()
    scored=cross_encoder_rerank(query,passages,top_k=len(passages),endpoint=endpoint)
    per_doc=defaultdict(list)
    chosen={}
    for item in scored:
        key=(item.metadata.project_id,item.document_id,item.metadata.path,item.metadata.git_branch)
        per_doc[key].append(item.score)
        if key not in chosen:chosen[key]=item
    # Maximum passage relevance, then weak support from a second passage.
    def aggregate(key):
        values=sorted(per_doc[key],reverse=True)
        return values[0]+(0.05*values[1] if len(values)>1 else 0)
    order=sorted(per_doc,key=lambda key:(-aggregate(key),-scores[key],key[1],key[2] or ""))
    return tuple(replace(chosen[key],rank=i,score=aggregate(key)) for i,key in enumerate(order[:top_k],1))
