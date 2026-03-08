import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from pyopenclaw.memory.base import MemoryHit

class ShortTermCache:
    def __init__(self, ttl_seconds: int = 300, max_size: int = 1000):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, (List[MemoryHit], float)] = {}

    def get(self, key: str) -> Optional[List[MemoryHit]]:
        if key not in self._cache:
            return None
        
        value, expiry = self._cache[key]
        if time.time() > expiry:
            del self._cache[key]
            return None
            
        return value

    def set(self, key: str, value: List[MemoryHit]) -> None:
        if len(self._cache) >= self.max_size:
            # Simple eviction: remove first key
            # In Python 3.7+ dicts preserve insertion order
            first_key = next(iter(self._cache))
            del self._cache[first_key]
            
        expiry = time.time() + self.ttl_seconds
        self._cache[key] = (value, expiry)

    def evict_expired(self) -> int:
        now = time.time()
        expired_keys = [k for k, (_, exp) in self._cache.items() if now > exp]
        for k in expired_keys:
            del self._cache[k]
        return len(expired_keys)
