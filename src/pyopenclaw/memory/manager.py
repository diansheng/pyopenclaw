import asyncio
import logging
from typing import List, Any, Dict
from pyopenclaw.config import MemoryConfig
from pyopenclaw.memory.base import MemoryHit
from pyopenclaw.memory.short_term import ShortTermCache
from pyopenclaw.memory.long_term import LongTermStore
from pyopenclaw.memory.vector_store import VectorStore
from pyopenclaw.memory.fts_store import FTSStore
from pyopenclaw.memory.embedder import Embedder
from pyopenclaw.memory.hybrid_search import hybrid_search

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self, config: MemoryConfig):
        self.config = config
        self.short_term = ShortTermCache(ttl_seconds=config.short_term_ttl)
        self.long_term = LongTermStore(db_path=config.db_path)
        self.embedder = Embedder(provider=config.embedder)
        self.vector_store = VectorStore(db_path=config.db_path, embedder=self.embedder)
        self.fts_store = FTSStore(db_path=config.db_path)

    async def search(self, query: str, top_k: int = 5) -> List[MemoryHit]:
        # Check cache
        cached = self.short_term.get(query)
        if cached:
            return cached
            
        # Hybrid search
        hits = await hybrid_search(
            query=query,
            vector_store=self.vector_store,
            fts_store=self.fts_store,
            long_term=self.long_term,
            top_k=top_k
        )
        
        # Update cache
        self.short_term.set(query, hits)
        return hits

    async def write(self, content: str, metadata: Dict[str, Any] = None) -> str:
        if metadata is None:
            metadata = {}
            
        memory_id = await self.long_term.upsert(content, metadata)
        
        # Update indexes asynchronously
        # For robustness, we could await them, but design says "async background task"
        # In this implementation, I'll await them to ensure consistency for now,
        # or use create_task if latency is critical.
        # Given "Agent Runtime" flow, awaiting write ensures next search finds it.
        # So I will await.
        
        await asyncio.gather(
            self.vector_store.index(memory_id, content),
            self.fts_store.index(memory_id, content)
        )
        
        return memory_id

    async def delete(self, memory_id: str) -> bool:
        # Delete from indexes first (FTS needs content lookup if implemented that way, but my FTS delete handles lookup)
        # Actually FTS delete looks up in LongTermStore (memories table).
        # So we must delete from indexes BEFORE deleting from LongTermStore.
        
        await asyncio.gather(
            self.vector_store.delete(memory_id),
            self.fts_store.delete(memory_id)
        )
        
        success = await self.long_term.delete(memory_id)
        return success

    @classmethod
    async def create(cls, config) -> 'MemoryManager':
        # Factory method if async init is needed (e.g. DB connection pool)
        # Currently everything is per-call connection or sync init.
        return cls(config)

    async def close(self):
        pass
