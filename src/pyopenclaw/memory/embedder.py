import logging
import os
from typing import List, Literal
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class Embedder:
    def __init__(self, provider: str = "openai", model: str = "text-embedding-3-small"):
        self.provider = provider
        self.model = model
        self._openai_client = None
        self._local_model = None

    async def embed(self, text: str) -> List[float]:
        if self.provider == "openai":
            return await self._embed_openai(text)
        elif self.provider == "local":
            return await self._embed_local(text)
        else:
            raise ValueError(f"Unsupported embedder provider: {self.provider}")

    async def _embed_openai(self, text: str) -> List[float]:
        if not self._openai_client:
            try:
                from openai import AsyncOpenAI
                self._openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            except ImportError:
                logger.error("OpenAI client not installed. Run `pip install openai`.")
                raise

        try:
            response = await self._openai_client.embeddings.create(
                input=text,
                model=self.model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            raise

    async def _embed_local(self, text: str) -> List[float]:
        if not self._local_model:
            try:
                from sentence_transformers import SentenceTransformer
                self._local_model = SentenceTransformer(self.model)
            except ImportError:
                logger.error("sentence-transformers not installed. Run `pip install sentence-transformers`.")
                # Fallback to random/dummy for testing if strictly required? No, raise error.
                raise

        # sentence-transformers run synchronously. Run in executor?
        # For simplicity in MVP, run sync or wrapped.
        # Ideally: loop.run_in_executor
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._local_model.encode, text)
