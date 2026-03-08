import aiosqlite
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

class FTSStore:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def index(self, memory_id: str, content: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            # Check if rowid exists for this memory_id (requires join or separate mapping)
            # But wait, FTS5 external content table mechanism:
            # content='memories', content_rowid='rowid'
            # If memories table is updated, FTS index needs to be updated manually or via triggers.
            # My schema:
            # CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            #     content,
            #     content='memories',
            #     content_rowid='rowid'
            # );
            # With external content tables, you are responsible for keeping the index up to date.
            # "The content option allows the FTS5 table to be created as an external content table...
            # Users must ensure that the FTS index is kept consistent with the content table."
            
            # Since I am using `rowid` of `memories` table as `content_rowid`, I need to find the `rowid` of the memory first.
            # But `memories` has `id TEXT PRIMARY KEY`, so it's a WITHOUT ROWID table? No, SQLite tables have rowid unless WITHOUT ROWID is specified.
            # So I need to get the rowid.
            
            async with db.execute("SELECT rowid FROM memories WHERE id = ?", (memory_id,)) as cursor:
                row = await cursor.fetchone()
                
            if not row:
                logger.warning(f"Cannot index memory {memory_id}: not found in base table")
                return
                
            rowid = row[0]
            
            # Update FTS index
            # Delete old entry (if any) and insert new
            # 'delete' command: INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', ?, ?)
            # But wait, if I use triggers this is automatic. I didn't add triggers.
            # Manual update:
            # INSERT INTO memories_fts(rowid, content) VALUES (?, ?)
            # FTS5 external content documentation says:
            # "To add a row to the FTS index, insert a row with the same rowid and content..."
            
            await db.execute(
                "INSERT INTO memories_fts(rowid, content) VALUES (?, ?)",
                (rowid, content)
            )
            await db.commit()

    async def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT m.id, fm.rank
                FROM memories_fts fm
                JOIN memories m ON m.rowid = fm.rowid
                WHERE memories_fts MATCH ?
                ORDER BY fm.rank
                LIMIT ?
                """,
                (query, top_k)
            ) as cursor:
                rows = await cursor.fetchall()
                
        results = []
        for row in rows:
            # Rank is typically negative (more negative = better match)
            # We convert to positive score for consistency, or just keep as is
            # RRF cares about order, so the value doesn't matter much if we sort by it.
            # But let's invert it to make "higher is better"
            score = -1 * row[1] 
            results.append((row[0], score))
            
        return results

    async def delete(self, memory_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
             async with db.execute("SELECT rowid, content FROM memories WHERE id = ?", (memory_id,)) as cursor:
                row = await cursor.fetchone()
            
             if row:
                rowid, content = row
                # Delete from FTS index
                await db.execute(
                    "INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', ?, ?)",
                    (rowid, content)
                )
                await db.commit()
