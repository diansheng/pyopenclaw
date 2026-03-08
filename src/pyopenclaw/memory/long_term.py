import aiosqlite
import json
import logging
from hashlib import sha256
from datetime import datetime
from typing import Optional, Dict, Any
from pyopenclaw.memory.base import MemoryRecord

logger = logging.getLogger(__name__)

class LongTermStore:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def upsert(self, content: str, metadata: Dict[str, Any]) -> str:
        memory_id = sha256(content.encode()).hexdigest()[:16]
        ts = datetime.now().timestamp()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO memories (id, content, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    metadata=excluded.metadata,
                    updated_at=excluded.updated_at
                """,
                (memory_id, content, json.dumps(metadata), ts, ts)
            )
            await db.commit()
            
        return memory_id

    async def delete(self, memory_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            await db.commit()
            return cursor.rowcount > 0

    async def get_by_id(self, memory_id: str) -> Optional[MemoryRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, content, metadata, created_at, updated_at FROM memories WHERE id = ?",
                (memory_id,)
            ) as cursor:
                row = await cursor.fetchone()
                
        if not row:
            return None
            
        return MemoryRecord(
            id=row['id'],
            content=row['content'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {},
            created_at=datetime.fromtimestamp(row['created_at']),
            updated_at=datetime.fromtimestamp(row['updated_at'])
        )
