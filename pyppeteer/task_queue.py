import asyncio
import logging
from typing import Awaitable, Any

logger = logging.getLogger(__name__)


class TaskQueue:
    def __init__(self, loop: asyncio.AbstractEventLoop = None):
        self.loop = loop or asyncio.get_event_loop()
        fut = self.loop.create_future()
        fut.set_result(None)
        self._task_chain = fut

    def post_task(self, task: Awaitable[Any]) -> Awaitable[None]:
        async def run_awaitable(prev):
            try:
                await prev
                await task
                pass  # consider at least logging here
            except Exception as e:
                logger.error(f'Exception while evaluating task queue: {e}')

        self._task_chain = self.loop.create_task(run_awaitable(self._task_chain))
        return self._task_chain
