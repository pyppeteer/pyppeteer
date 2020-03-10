import asyncio
from typing import Iterable, Union, AsyncIterable

from websockets import connect, WebSocketClientProtocol, Data

try:
    from contextlib import asynccontextmanager
except ImportError:
    from async_generator import asynccontextmanager


class WebsocketTransport:
    def __init__(self, ws: WebSocketClientProtocol = None):
        self.onmessage = None
        self.onclose = None
        self.ws = ws

    @classmethod
    @asynccontextmanager
    async def create(cls, uri: str, loop: asyncio.AbstractEventLoop = None) -> 'WebsocketTransport':
        try:
            instance = cls(
                await connect(
                    uri=uri, ping_interval=None, max_size=256 * 1024 * 1024, loop=loop, close_timeout=5,  # 256Mb
                )
            )  # 256Mb
            yield instance
        finally:
            try:
                await instance.close()
            except NameError:
                pass

    async def send(self, message: Union[Data, Iterable[Data], AsyncIterable[Data]]) -> None:
        await self.ws.send(message)

    async def close(self, code: int = 1000, reason: str = '') -> None:
        await self.ws.close(code=code, reason=reason)
        if self.onclose:
            await self.onclose()

    async def recv(self) -> Data:
        data = await self.ws.recv()
        if self.onmessage and data:
            await self.onmessage(data)
        return data
