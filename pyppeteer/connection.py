#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Connection/Session management module."""

import asyncio
import json
import logging
from typing import Awaitable, Dict, Union, TYPE_CHECKING, Any

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict

from pyee import EventEmitter
import websockets

from pyppeteer.errors import NetworkError
from pyppeteer.events import Events
from pyppeteer.websocket_transport import WebsocketTransport

if TYPE_CHECKING:
    from typing import Optional

logger = logging.getLogger(__name__)
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


class Connection(EventEmitter):
    """Connection management class."""

    def __init__(
        self, url: str, transport: WebsocketTransport, delay: int = 0, loop: asyncio.AbstractEventLoop = None,
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
        self._transport.onmessage = self._onMessage
        self._transport.onclose = self._onClose

        self._loop = loop or asyncio.get_event_loop()
        self._sessions: Dict[str, CDPSession] = {}
        self.connection: CDPSession
        self._connected = False
        self._recv_fut = self._loop.create_task(self._recv_loop())
        self._closed = False

    @staticmethod
    def fromSession(cls, session: 'CDPSession'):
        return session._connection

    def session(self, sessionId):
        return self._sessions.get(sessionId)

    @property
    def url(self) -> str:
        """Get connected WebSocket url."""
        return self._url

    async def _recv_loop(self) -> None:
        async with self._transport.create(self._url, self._loop) as connection:
            self._connected = True
            self.connection = connection
            while self._connected:
                try:
                    await self.connection.recv()
                except (websockets.ConnectionClosed, ConnectionResetError):
                    logger.info('connection closed')
                    break
                await asyncio.sleep(0)
        if self._connected:
            self._loop.create_task(self.dispose())

    async def _async_send(self, msg: Message) -> None:
        while not self._connected:
            await asyncio.sleep(self._delay)
        try:
            await self.connection.send(json.dumps(msg))
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
        callback = self._loop.create_future()
        self._callbacks[id_] = callback
        callback.error: Exception = NetworkError()  # type: ignore
        callback.method: str = method  # type: ignore
        return callback

    def _rawSend(self, message: Message):
        self._lastId += 1
        id_ = self._lastId
        message['id'] = id_
        logger_connection.debug(f'SEND ► {message}')
        self._loop.create_task(self._async_send(message))
        return id_

    async def _onMessage(self, msg: Message) -> None:
        await asyncio.sleep(self._delay)
        logger_connection.debug(f'◀ RECV {msg}')

        # Handle Target attach/detach methods
        if msg.get('method') == 'Target.attachedToTarget':
            sessionId = msg['params']['sessionId']
            self._sessions[sessionId] = CDPSession(
                connection=self, targetType=msg['params']['targetInfo']['type'], sessionId=sessionId, loop=self._loop
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
                del self._callbacks[msg['id']]
                if msg.get('error'):
                    callback.set_exception(createProtocolError(callback.error, callback.method, msg))
                else:
                    callback.set_result(msg.get('result'))
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
        if not self._recv_fut.done():
            self._recv_fut.cancel()
        self._sessions.clear()
        self.emit(Events.Connection.Disconnected)

    async def dispose(self) -> None:
        """Close all connection."""
        self._connected = False
        await self._transport.close()

    async def createSession(self, targetInfo: Dict) -> 'CDPSession':
        """Create new session."""
        resp = await self.send('Target.attachToTarget', {'targetId': targetInfo['targetId']})
        sessionId = resp.get('sessionId')
        # TODO puppeteer code indicates that _sessions should already have session open
        session = CDPSession(self, targetInfo['type'], sessionId, self._loop)
        self._sessions[sessionId] = session
        return session


class CDPSession(EventEmitter):
    """Chrome Devtools Protocol Session.

    The :class:`CDPSession` instances are used to talk raw Chrome Devtools
    Protocol:

    * protocol methods can be called with :meth:`send` method.
    * protocol events can be subscribed to with :meth:`on` method.

    Documentation on DevTools Protocol can be found
    `here <https://chromedevtools.github.io/devtools-protocol/>`__.
    """

    def __init__(
        self,
        connection: Union[Connection, 'CDPSession'],
        targetType: str,
        sessionId: str,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Make new session."""
        super().__init__()
        self._callbacks: Dict[int, asyncio.Future] = {}
        self._connection: Optional[Connection] = connection
        self._targetType = targetType
        self._sessionId = sessionId
        self._loop = loop

    def send(self, method: str, params: dict = None) -> Awaitable:
        """Send message to the connected session.

        :arg str method: Protocol method name.
        :arg dict params: Optional method parameters.
        """
        if not self._connection:
            raise NetworkError(
                f'Protocol Error ({method}): Session closed. Most likely the ' f'{self._targetType} has been closed.'
            )
        id_ = self._connection._rawSend({'method': method, 'params': params or {}})

        callback = self._loop.create_future()
        self._callbacks[id_] = callback
        callback.error: Exception = NetworkError()  # type: ignore
        callback.method: str = method  # type: ignore
        return callback

    def _onMessage(self, msg: Message) -> None:  # noqa: C901
        id_ = msg.get('id')
        callback = self._callbacks.get(id_)
        if id_ and callback:
            del self._callbacks[id_]
            if msg.get('error'):
                callback.set_exception(
                    createProtocolError(
                        callback.error,  # type: ignore
                        callback.method,  # type: ignore
                        msg,
                    )
                )
            else:
                callback.set_result(msg.get('result'))
        else:
            if msg.get('id'):
                raise ConnectionError('Received unexpected message ' f'with no callback: {msg}')
            self.emit(msg.get('method'), msg.get('params'))

    async def detach(self) -> None:
        """Detach session from target.

        Once detached, session won't emit any events and can't be used to send
        messages.
        """
        if not self._connection:
            raise NetworkError('Session already detached. Most likely' f'the {self._targetType} has been closed')
        await self._connection.send('Target.detachFromTarget', {'sessionId': self._sessionId})

    def _onClosed(self) -> None:
        for cb in self._callbacks.values():
            cb.set_exception(
                rewriteError(
                    cb.error,  # type: ignore
                    f'Protocol error {cb.method}: Target closed.',  # type: ignore
                )
            )
        self._callbacks.clear()
        self._connection = None
        self.emit(Events.CDPSession.Disconnected)

    def _createSession(self, targetType: str, sessionId: str) -> 'CDPSession':
        # TODO this is only used internally and is confusing with createSession
        session = CDPSession(self, targetType, sessionId, self._loop)
        self._sessions[sessionId] = session
        return session


def createProtocolError(error: Exception, method: str, obj: Dict) -> Exception:
    message = f'Protocol error ({method}): {obj["error"]["message"]}'
    if 'data' in obj['error']:
        message += f' {obj["error"]["data"]}'
    return rewriteError(error, message)


def rewriteError(error: Exception, message: str) -> Exception:
    error.args = (message,)
    return error
