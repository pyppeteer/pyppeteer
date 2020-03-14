import asyncio
import json
import logging
from typing import Awaitable, Dict, Any

import websockets
from pyee import AsyncIOEventEmitter

from pyppeteer.errors import NetworkError
from pyppeteer.events import Events
from pyppeteer.websocket_transport import WebsocketTransport

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger_connection = logging.getLogger(__name__ + '.Connection')


class TargetInfo(TypedDict, total=False):
    type: str


class MessageParams(TypedDict, total=False):
    targetInfo: TargetInfo
    sessionId: str


class MessageError(TypedDict, total=False):
    message: str
    data: Any


class Message(TypedDict):
    method: str
    id: int
    params: MessageParams
    error: MessageError
    result: Any


class Connection(AsyncIOEventEmitter):
    """Connection management class."""

    def __init__(
        self, url: str, transport: WebsocketTransport, delay: float = 0, loop: asyncio.AbstractEventLoop = None,
    ) -> None:
        """Make connection.

        :arg str url: WebSocket url to connect devtool.
        :arg int delay: delay to wait before processing received messages.
        """
        super().__init__()
        self._url = url
        self._lastId = 0
        self._callbacks: Dict[int, asyncio.Future] = {}
        self._delay = delay / 1000

        self._transport = transport

        self.loop = loop or asyncio.get_event_loop()
        self._sessions: Dict[str, CDPSession] = {}
        self._connected = False
        self._closed = False
        self.loop.create_task(self._recv_loop())

    @staticmethod
    def fromSession(session: 'CDPSession'):
        return session._connection

    def session(self, sessionId):
        return self._sessions.get(sessionId)

    @property
    def url(self) -> str:
        """Get connected WebSocket url."""
        return self._url

    async def _recv_loop(self) -> None:
        async with self._transport as transport_connection:
            self._connected = True
            self.connection = transport_connection
            self.connection.onmessage = lambda msg: self._onMessage(json.loads(msg))
            self.connection.onclose = self._onClose
            while self._connected:
                try:
                    await self.connection.recv()
                except (websockets.ConnectionClosed, ConnectionResetError) as e:
                    logger.warning(f'Transport connection closed: {e}')
                    break
                # wait 1 async loop frame, no other data will be accessible in between frames
                await asyncio.sleep(0)
        if self._connected:
            self.loop.create_task(self.dispose())

    async def _async_send(self, msg: Message) -> None:
        while not self._connected:
            await asyncio.sleep(self._delay)
        try:
            remove_none_items_inplace(msg)
            await self.connection.send(json.dumps(msg))
            logger_connection.debug(f'SEND ▶ {msg}')
        except websockets.ConnectionClosed:
            logger.error('connection unexpectedly closed')
            callback = self._callbacks.get(msg['id'], None)
            if callback and not callback.done():
                callback.set_result(None)
                await self.dispose()

    def send(self, method: str, params: dict = None) -> Awaitable:
        """Send message via the connection."""
        # Detect connection availability from the second transmission
        if self._lastId and not self._connected:
            raise ConnectionError('Connection is closed')
        id_ = self._rawSend({'method': method, 'params': params or {}})
        callback = self.loop.create_future()
        callback.error: Exception = NetworkError()  # type: ignore
        callback.method: str = method  # type: ignore
        self._callbacks[id_] = callback
        return callback

    def _rawSend(self, message: Message):
        self._lastId += 1
        id_ = self._lastId
        message['id'] = id_
        self.loop.create_task(self._async_send(message))
        return id_

    async def _onMessage(self, msg: Message) -> None:
        if self._delay:
            await asyncio.sleep(self._delay)
        logger_connection.debug(f'◀ RECV {msg}')

        # Handle Target attach/detach methods
        if msg.get('method') == 'Target.attachedToTarget':
            sessionId = msg['params']['sessionId']
            self._sessions[sessionId] = CDPSession(
                connection=self, targetType=msg['params']['targetInfo']['type'], sessionId=sessionId, loop=self.loop,
            )
        elif msg.get('method') == 'Target.detachedFromTarget':
            session = self._sessions.get(msg['params']['sessionId'])
            if session:
                session._onClosed()
                del self._sessions[msg['params']['sessionId']]

        if msg.get('sessionId'):
            session = self._sessions.get(msg['sessionId'])
            if session:
                session._onMessage(msg)
        elif msg.get('id'):
            # Callbacks could be all rejected if someone has called `.dispose()`
            callback = self._callbacks.get(msg['id'])
            if callback:
                if msg.get('error'):
                    callback.set_exception(createProtocolError(callback.error, callback.method, msg))
                else:
                    callback.set_result(msg.get('result'))
                del self._callbacks[msg['id']]
        else:
            self.emit(msg['method'], msg['params'])

    async def _onClose(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._transport.onmessage = None
        self._transport.onclose = None

        for cb in self._callbacks.values():
            cb.set_exception(
                rewriteError(
                    cb.error,  # type: ignore
                    f'Protocol error {cb.method}: Target closed.',  # type: ignore
                )
            )
        self._callbacks.clear()

        for session in self._sessions.values():
            session._onClosed()
        self._sessions.clear()

        # close connection
        if hasattr(self, 'connection'):  # may not have connection
            await self.connection.close()
        self._sessions.clear()
        self.emit(Events.Connection.Disconnected)

    async def dispose(self) -> None:
        """Close all connection."""
        self._connected = False
        await self._onClose()
        await self._transport.close()

    async def createSession(self, targetInfo: Dict) -> 'CDPSession':
        """Create new session."""
        resp = await self.send('Target.attachToTarget', {'targetId': targetInfo['targetId'], 'flatten': True})
        sessionId = resp.get('sessionId')
        return self._sessions[sessionId]


def createProtocolError(error: Exception, method: str, obj: Dict) -> Exception:
    message = f'Protocol error ({method}): {obj["error"]["message"]}'
    if 'data' in obj['error']:
        message += f' {obj["error"]["data"]}'
    return rewriteError(error, message)


def rewriteError(error: Exception, message: str) -> Exception:
    error.args = (message,)
    return error


def remove_none_items_inplace(o: Dict[str, Any]):
    """
    Removes items that have a value of None. There are instances in puppeteer where a object (dict) is sent which has
    undefined values, which are then omitted from the resulting json. This function emulates such behaviour, removing
    all k:v pairs where v = None
    :param o:
    :return Dict[str, Any]: dict without any None values
    """
    none_keys = []
    for key, value in o.items():
        if isinstance(value, dict):
            remove_none_items_inplace(value)
        if value is None:
            none_keys.append(key)
    for key in none_keys:
        del o[key]


from pyppeteer.connection.cdpsession import CDPSession
