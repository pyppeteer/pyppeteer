#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Connection/Session management module."""

import asyncio
import json
import logging
from typing import Awaitable, TYPE_CHECKING

from pyee import EventEmitter
import websockets

from pyppeteer.errors import NetworkError

if TYPE_CHECKING:
    from typing import Callable, Dict, Optional  # noqa: F401

logger = logging.getLogger(__name__)


class Connection(EventEmitter):
    """Connection management class."""

    def __init__(self, url: str, delay: int = 0) -> None:
        """Make connection.

        :arg str url: WebSocket url to connect devtool.
        :arg int delay: delay to wait until send messages.
        """
        super().__init__()
        self._url = url
        self._lastId = 0
        self._callbacks: Dict[int, asyncio.Future] = dict()
        self._delay = delay
        self._sessions: Dict[str, Session] = dict()
        self.connection: Session
        self._connected = False
        self._ws = websockets.client.connect(self._url)
        self._recv_fut = asyncio.ensure_future(self._recv_loop())

    @property
    def url(self) -> str:
        """Get connected WebSocket url."""
        return self._url

    async def _recv_loop(self) -> None:
        async with self._ws as connection:
            self._connected = True
            self.connection = connection
            while self._connected:
                try:
                    resp = await self.connection.recv()
                    if resp:
                        self._on_message(resp)
                except websockets.ConnectionClosed:
                    logger.info('connection closed')
                    break

    async def _async_send(self, msg: str) -> None:
        while not self._connected:
            await asyncio.sleep(self._delay)
        await self.connection.send(msg)

    def send(self, method: str, params: dict = None) -> Awaitable:
        """Send message via the connection."""
        if params is None:
            params = dict()
        self._lastId += 1
        _id = self._lastId
        msg = json.dumps(dict(
            id=_id,
            method=method,
            params=params,
        ))
        logger.debug(f'SEND▶: {msg}')
        asyncio.ensure_future(self._async_send(msg))
        callback = asyncio.get_event_loop().create_future()
        self._callbacks[_id] = callback
        callback.method = method  # type: ignore
        return callback

    def _on_response(self, msg: dict) -> None:
        callback = self._callbacks.pop(msg.get('id', -1))
        if 'error' in msg:
            error = msg['error']
            callback.set_exception(
                NetworkError(f'Protocol Error: {error}'))
        else:
            callback.set_result(msg.get('result'))

    def _on_query(self, msg: dict) -> None:
        params = msg.get('params', {})
        method = msg.get('method', '')
        sessionId = params.get('sessionId')
        if method == 'Target.receivedMessageFromTarget':
            session = self._sessions.get(sessionId)
            if session:
                session._on_message(params.get('message'))
        elif method == 'Target.detachedFromTarget':
            session = self._sessions.get(sessionId)
            if session:
                session._on_closed()
                del self._sessions[sessionId]
        else:
            self.emit(method, params)

    def _on_message(self, message: str) -> None:
        logger.debug(f'◀RECV: {message}')
        msg = json.loads(message)
        if msg.get('id') in self._callbacks:
            self._on_response(msg)
        else:
            self._on_query(msg)

    async def _on_close(self) -> None:
        if not self._recv_fut.done():
            if hasattr(self, 'connection'):  # may not have connection
                await self.connection.close()
            self._recv_fut.cancel()
        for cb in self._callbacks.values():
            cb.cancel()
        self._callbacks.clear()
        for session in self._sessions.values():
            session._on_closed()
        self._sessions.clear()

    async def dispose(self) -> None:
        """Close all connection."""
        await self._on_close()
        self._connected = False

    async def createSession(self, targetId: str) -> 'Session':
        """Create new session."""
        resp = await self.send(
            'Target.attachToTarget',
            {'targetId': targetId}
        )
        sessionId = resp.get('sessionId')
        session = Session(self, targetId, sessionId)
        self._sessions[sessionId] = session
        return session


class Session(EventEmitter):
    """Session class."""

    def __init__(self, connection: Connection, targetId: str, sessionId: str
                 ) -> None:
        """Make new session."""
        super().__init__()
        self._lastId = 0
        self._callbacks: Dict[int, asyncio.Future] = {}
        self._connection: Optional[Connection] = connection
        self._targetId = targetId
        self._sessionId = sessionId

    @property
    def targetId(self) -> str:
        """Get target id of this session."""
        return self._targetId

    async def send(self, method: str, params: dict = None) -> dict:
        """Send message to the connected session."""
        self._lastId += 1
        _id = self._lastId
        msg = json.dumps(dict(id=_id, method=method, params=params))

        callback = asyncio.get_event_loop().create_future()
        self._callbacks[_id] = callback
        callback.method: str = method  # type: ignore

        if not self._connection:
            raise NetworkError('Connection closed.')
        await self._connection.send('Target.sendMessageToTarget', {
            'sessionId': self._sessionId,
            'message': msg,
        })
        return await callback

    def _on_message(self, msg: str) -> None:
        obj = json.loads(msg)
        _id = obj.get('id')
        if _id and _id in self._callbacks:
            callback = self._callbacks.pop(_id)
            if 'error' in obj:
                error = obj['error']
                msg = error.get('message')
                data = error.get('data')
                callback.set_exception(
                    NetworkError(f'Protocol Error: {msg} {data}')
                )
            else:
                result = obj.get('result')
                callback.set_result(result)
        else:
            self.emit(obj.get('method'), obj.get('params'))

    async def dispose(self) -> None:
        """Close target."""
        if self._connection:
            # broken...?
            await self._connection.send('Target.closeTarget', {
                'targetId': self.targetId,
            })

    def _on_closed(self) -> None:
        for cb in self._callbacks.values():
            cb.cancel()
        self._callbacks.clear()
        self._connection = None
