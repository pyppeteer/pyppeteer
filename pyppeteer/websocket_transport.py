import asyncio
import logging
from typing import Any, AsyncIterable, Callable, Iterable, Optional, Union

from websockets import Data, WebSocketClientProtocol, connect

logger = logging.getLogger(__name__)


class WebsocketTransport:
    def __init__(self, ws: WebSocketClientProtocol):
        self.onmessage: Optional[Callable[[str], Any]] = None
        self.onclose: Optional[Callable[[], Any]] = None
        self.ws = ws

    @classmethod
    async def create(cls, uri: str, loop: asyncio.AbstractEventLoop = None) -> 'WebsocketTransport':
        return cls(
            await connect(
                uri=uri,
                # chrome doesn't respond to pings
                # todo: remove note after websockets release
                # waiting on websockets to release new version where ping_interval is typed correctly
                ping_interval=None,  # type: ignore
                max_size=256 * 1024 * 1024,  # 256Mb
                loop=loop,
                close_timeout=5,
                # todo check if speed is affected
                # note: seems to work w/ compression
                compression=None,
            )
        )

    async def send(self, message: Union[Data, Iterable[Data], AsyncIterable[Data]]) -> None:
        await self.ws.send(message)

    async def close(self, code: int = 1000, reason: str = '') -> None:
        logger.debug(f'Disposing connection: code={code} reason={reason}')
        await self.ws.close(code=code, reason=reason)
        if self.onclose:
            await self.onclose()

    async def recv(self) -> Data:
        data = await self.ws.recv()
        if self.onmessage and data:
            await self.onmessage(data)
        return data
