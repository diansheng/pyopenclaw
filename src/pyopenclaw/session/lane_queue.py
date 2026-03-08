import asyncio
from typing import Coroutine, Any, Optional

class LaneQueue:
    def __init__(self, session_id: str, mode: str = "serial"):
        self.session_id = session_id
        self.mode = mode
        self._queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        
        if mode == "serial":
            self._start_worker()

    def _start_worker(self):
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self):
        while True:
            task_coro, future = await self._queue.get()
            try:
                result = await task_coro
                if not future.done():
                    future.set_result(result)
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
            finally:
                self._queue.task_done()

    async def enqueue(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Future:
        if self.mode == "parallel":
            # Just run it immediately
            return asyncio.create_task(coro)
        
        # Serial mode: put on queue
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self._queue.put((coro, future))
        return future

    async def drain(self):
        await self._queue.join()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
