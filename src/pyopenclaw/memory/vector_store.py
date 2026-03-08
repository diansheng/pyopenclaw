import math
import pickle
import aiosqlite
import logging
from typing import List, Tuple
from pyopenclaw.memory.embedder import Embedder

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, db_path: str, embedder: Embedder):
        self.db_path = db_path
        self.embedder = embedder

    async def index(self, memory_id: str, content: str) -> None:
        try:
            embedding = await self.embedder.embed(content)
        except Exception as e:
            logger.error(f"Failed to generate embedding for memory {memory_id}: {e}")
            return

        # Store embedding as binary (pickle)
        embedding_blob = pickle.dumps(embedding)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO memory_embeddings (memory_id, embedding) VALUES (?, ?)",
                (memory_id, embedding_blob)
            )
            await db.commit()

    async def search_knn(self, query: str, top_k: int) -> List[Tuple[str, float]]:
        try:
            query_embedding = await self.embedder.embed(query)
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            return []
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT memory_id, embedding FROM memory_embeddings") as cursor:
                rows = await cursor.fetchall()
                
        # Brute force cosine similarity
        results = []
        for memory_id, blob in rows:
            try:
                vec = pickle.loads(blob)
                score = self._cosine_similarity(query_embedding, vec)
                results.append((memory_id, score))
            except Exception as e:
                logger.warning(f"Failed to process embedding for {memory_id}: {e}")
                continue
            
        # Sort descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    async def delete(self, memory_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM memory_embeddings WHERE memory_id = ?", (memory_id,))
            await db.commit()

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)
