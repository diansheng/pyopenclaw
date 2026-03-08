import aiosqlite
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class Turn:
    id: int
    session_id: str
    user_text: str
    assistant_text: str
    timestamp: float

class ConversationStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_transcript_dir()

    def _ensure_transcript_dir(self):
        # Assuming db_path is like ~/.pyopenclaw/memory.db
        # Transcripts go to ~/.pyopenclaw/transcripts/
        db_file = Path(self.db_path).expanduser()
        self.transcript_dir = db_file.parent / "transcripts"
        self.transcript_dir.mkdir(parents=True, exist_ok=True)

    async def append_turn(self, session_id: str, user_text: str, assistant_text: str) -> None:
        ts = datetime.now().timestamp()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO turns (session_id, user_text, assistant_text, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, user_text, assistant_text, ts)
            )
            await db.commit()

        # Append to JSONL
        transcript_file = self.transcript_dir / f"{session_id}.jsonl"
        entry = {
            "timestamp": ts,
            "user": user_text,
            "assistant": assistant_text
        }
        try:
            with open(transcript_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except IOError as e:
            logger.error(f"Failed to write transcript for {session_id}: {e}")

    async def get_history(self, session_id: str, max_turns: int = 20) -> list[Turn]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, session_id, user_text, assistant_text, timestamp 
                FROM turns 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (session_id, max_turns)
            ) as cursor:
                rows = await cursor.fetchall()
                
        # Reverse to chronological order
        history = []
        for row in reversed(rows):
            history.append(Turn(
                id=row['id'],
                session_id=row['session_id'],
                user_text=row['user_text'],
                assistant_text=row['assistant_text'],
                timestamp=row['timestamp']
            ))
        return history

    async def compact(self, session_id: str, summary: str) -> None:
        # Delete old turns
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
            
            # Insert summary as a special turn
            # Using a special marker or just user_text="Summary"
            ts = datetime.now().timestamp()
            await db.execute(
                "INSERT INTO turns (session_id, user_text, assistant_text, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, "[System Summary]", summary, ts)
            )
            await db.commit()
