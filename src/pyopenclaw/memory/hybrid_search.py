import asyncio
from typing import List, Tuple, Dict
from collections import defaultdict
from pyopenclaw.memory.base import MemoryHit, MemoryRecord
from pyopenclaw.memory.vector_store import VectorStore
from pyopenclaw.memory.fts_store import FTSStore
from pyopenclaw.memory.long_term import LongTermStore

def _reciprocal_rank_fusion(
    vec_results: List[Tuple[str, float]],
    fts_results: List[Tuple[str, float]],
    k: int = 60,
) -> List[Tuple[str, float]]:
    fused_scores = defaultdict(float)
    
    for rank, (doc_id, _) in enumerate(vec_results):
        fused_scores[doc_id] += 1 / (k + rank + 1)
        
    for rank, (doc_id, _) in enumerate(fts_results):
        fused_scores[doc_id] += 1 / (k + rank + 1)
        
    sorted_results = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results

async def hybrid_search(
    query: str,
    vector_store: VectorStore,
    fts_store: FTSStore,
    long_term: LongTermStore,
    top_k: int = 5,
    alpha: float = 0.5, # Unused in RRF but kept for signature compatibility if needed
) -> List[MemoryHit]:
    # Run searches concurrently
    vec_task = asyncio.create_task(vector_store.search_knn(query, top_k * 2))
    fts_task = asyncio.create_task(fts_store.search(query, top_k * 2))
    
    vec_results, fts_results = await asyncio.gather(vec_task, fts_task)
    
    fused = _reciprocal_rank_fusion(vec_results, fts_results)
    top_ids = [doc_id for doc_id, _ in fused[:top_k]]
    
    hits = []
    for doc_id in top_ids:
        record = await long_term.get_by_id(doc_id)
        if record:
            # Score is the RRF score
            score = next(s for d, s in fused if d == doc_id)
            hits.append(MemoryHit(
                id=record.id,
                content=record.content,
                score=score,
                metadata=record.metadata
            ))
            
    return hits
