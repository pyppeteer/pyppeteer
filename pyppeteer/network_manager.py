#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Network Manager module."""

import asyncio
import base64
from collections import OrderedDict
import json
from urllib.parse import urldefrag, urlunparse
from types import SimpleNamespace
from typing import Any, Awaitable, Dict, TYPE_CHECKING

from pyee import EventEmitter

from pyppeteer.connection import Session
from pyppeteer.multimap import Multimap

if TYPE_CHECKING:
    from typing import Optional  # noqa: F401


class NetworkManager(EventEmitter):
    """NetworkManager class."""

    Events = SimpleNamespace(
        Request='request',
        Response='response',
        RequestFailed='requestfailed',
        RequestFinished='requestfinished',
    )

    def __init__(self, client: Session) -> None:
        """Make new NetworkManager."""
        super().__init__()
        self._client = client
        self._requestIdToRequest: Dict[str, Request] = dict()
        self._interceptionIdToRequest: Dict[str, Request] = dict()
        self._extraHTTPHeaders: OrderedDict[str, str] = OrderedDict()
        self._requestInterceptionEnabled = False
        self._requestHashToRequestIds = Multimap()
        self._requestHashToInterceptions = Multimap()

        self._client.on('Network.requestWillBeSent', self._onRequestWillBeSent)
        self._client.on('Network.requestIntercepted', self._onRequestIntercepted)  # noqa: E501
        self._client.on('Network.responseReceived', self._onResponseReceived)
        self._client.on('Network.loadingFinished', self._onLoadingFinished)
        self._client.on('Network.loadingFailed', self._onLoadingFailed)

    async def setExtraHTTPHeaders(self, extraHTTPHeaders: Dict[str, str]
                                  ) -> None:
        """Set extra http headers."""
        self._extraHTTPHeaders = OrderedDict()
        headers = OrderedDict()  # type: Dict[str, str]
        for k, v in extraHTTPHeaders:
            self._extraHTTPHeaders[k] = v
            headers[k] = v
        await self._client.send('Network.setExtraHTTPHeaders',
                                {'headers': headers})

    def extraHTTPHeaders(self) -> Dict[str, str]:
        """Get extra http headers."""
        return dict(**self._extraHTTPHeaders)

    async def setUserAgent(self, userAgent: str) -> Awaitable:
        """Set user agent."""
        return await self._client.send('Network.setUserAgentOverride',
                                       {'userAgent': userAgent})

    async def setRequestInterceptionEnabled(self, value: bool) -> None:
        """Enable request intercetion."""
        await self._client.send('Network.setRequestInterceptionEnabled',
                                {'enabled': bool(value)})
        self._requestInterceptionEnabled = value

    def _onRequestIntercepted(self, event: dict) -> None:
        event['request']['url'] = removeURLHash(
            event['request'].get('url')
        )

        if event.get('redirectStatusCode'):
            request = self._interceptionIdToRequest[event['interceptionId']]
            if not request:
                raise Exception('INTERNAL ERROR: failed to find request for interception redirect.')  # noqa: E501
            self._handleRequestRedirect(request,
                                        event['redirectStatusCode'],
                                        event['redirectHeaders'])
            self._handleRequestStart(request._requestId,
                                     event['interceptionId'],
                                     event['redirectUrl'],
                                     event['request'])
            return
        requestHash = generateRequestHash(event['request'])
        self._requestHashToInterceptions.set(requestHash, event)
        self._maybeResolveInterception(requestHash)

    def _handleRequestRedirect(self, request: 'Request', redirectStatus: int,
                               redirectHeaders: dict) -> None:
        response = Response(
            self._client, request, redirectStatus, redirectHeaders)
        request._response = response
        self._requestIdToRequest.pop(request._requestId, None)
        self._interceptionIdToRequest.pop(request._interceptionId, None)
        self.emit(NetworkManager.Events.Response, response)
        self.emit(NetworkManager.Events.RequestFinished, request)

    def _handleRequestStart(self, requestId: str, interceptionId: str,
                            url: str, requestPayload: dict) -> None:
        request = Request(self._client, requestId, interceptionId, url, requestPayload)  # noqa: E501
        self._requestIdToRequest[requestId] = request
        self._interceptionIdToRequest[interceptionId] = request
        self.emit(NetworkManager.Events.Request, request)

    def _onRequestWillBeSent(self, event: dict) -> None:
        if (self._requestInterceptionEnabled and
                not event['request']['url'].startswith('data:')):
            if event.get('redirectResponse'):
                return
            requestHash = generateRequestHash(event['request'])
            self._requestHashToRequestIds.set(
                requestHash, event.get('requestId'))
            self._maybeResolveInterception(requestHash)
            return
        if event.get('redirectResponse'):
            request = self._requestIdToRequest[event['requestId']]
            self._handleRequestRedirect(
                request, event['redirectResponse']['status'],
                event['redirectResponse']['headers']
            )
        self._handleRequestStart(event['requestId'], '',
                                 event['request']['url'],
                                 event['request'])

    def _maybeResolveInterception(self, requestHash: str) -> None:
        requestId = self._requestHashToRequestIds.firstValue(requestHash)
        interception = self._requestHashToInterceptions.firstValue(requestHash)
        if not requestId or not interception:
            return
        self._requestHashToRequestIds.delete(requestHash, requestId)
        self._requestHashToInterceptions.delete(requestHash, interception)
        self._handleRequestStart(requestId, interception.interceptionId,
                                 interception.request.url,
                                 interception.request)

    def _onResponseReceived(self, event: dict) -> None:
        request = self._requestIdToRequest.get(event['requestId'])
        # FileUpload sends a response without a matching request.
        if not request:
            return
        response = Response(self._client, request,
                            event['response']['status'],
                            event['response']['headers'])
        request._response = response
        self.emit(NetworkManager.Events.Response, response)

    def _onLoadingFinished(self, event: dict) -> None:
        request = self._requestIdToRequest.get(event['requestId'])
        # For certain requestIds we never receive requestWillBeSent event.
        # @see https://crbug.com/750469
        if not request:
            return
        request._completePromiseFulfill()
        self._requestIdToRequest.pop(event['requestId'], None)
        self._interceptionIdToRequest.pop(event['interceptionId'], None)
        self.emit(NetworkManager.Events.RequestFinished, request)

    def _onLoadingFailed(self, event: dict) -> None:
        request = self._requestIdToRequest.get(event['requestId'])
        # For certain requestIds we never receive requestWillBeSent event.
        # @see https://crbug.com/750469
        if not request:
            return
        request._completePromiseFulfill()
        self._requestIdToRequest.pop(event['requestId'], None)
        self._interceptionIdToRequest.pop(event['interceptionId'], None)
        self.emit(NetworkManager.Events.RequestFailed, request)


class Request(object):
    """Request class."""

    def __init__(self, client: Session, requestId: str, interceptionId: str,
                 url: str, payload: dict) -> None:
        """Make new request class."""
        self._client = client
        self._requestId = requestId
        self._interceptionId = interceptionId
        self._interceptionHandled = False
        self._response: Optional[Response] = None
        self._completePromise = asyncio.get_event_loop().create_future()

        self.url = url
        self.method = payload.get('method', '')
        self.postData = payload.get('postData', '')
        self.headers = payload.get('headers', {})

    def _completePromiseFulfill(self) -> None:
        self._completePromise.set_result(None)

    @property
    def response(self) -> Any:
        """Get response."""
        return self._response

    async def continue_(self, overrides: dict) -> None:
        """Continue request."""
        if self.url.startswith('data:'):
            return
        self._interceptionHandled = True
        if 'headers' in overrides:
            headers = dict()
            for entry in overrides['headers']:
                headers[entry[0]] = entry[1]
        await self._client.send('Network.continueInterceptedRequest', dict(
            interceptionId=self._interceptionId,
            url=overrides.get('url'),
            method=overrides.get('method'),
            postData=overrides.get('postData'),
            headers=headers,
        ))

    async def abort(self) -> None:
        """Abort request."""
        if self.url.startswith('data:'):
            return
        self._interceptionHandled = True
        await self._client.send('Network.continueInterceptedRequest', dict(
            interceptionId=self._interceptionId,
            errorReason='Failed',
        ))


class Response(object):
    """Response class."""

    def __init__(self, client: Session, request: Request, status: int,
                 headers: dict) -> None:
        """Make new response."""
        self._client = client
        self._request = request
        self.status = status
        self._headers = headers
        self._contentPromise = asyncio.get_event_loop().create_future()
        self.ok = 200 <= status <= 299
        self.url = request.url

    async def _bufread(self) -> bytes:
        response = await (await self._client.send('Network.getResponseBody', {
          'requestId': self._request._requestId
        }))
        body = response.get('body', b'')
        if response.get('base64Encoded'):
            return base64.b64decode(body)
        return body

    def buffer(self) -> Awaitable:
        """Get buffer."""
        if not self._contentPromise.done():
            return asyncio.ensure_future(self._bufread())
        return self._contentPromise

    async def text(self) -> str:
        """Get content as text."""
        content = await self.buffer()
        return content.decode('utf-8')

    async def json(self) -> dict:
        """Get content as json."""
        content = await self.text()
        return json.loads(content)

    @property
    def request(self) -> Request:
        """Get request."""
        return self._request


def generateRequestHash(request: dict) -> str:
    """Generate request hash."""
    _hash = {
        'url': request.get('url'),
        'method': request.get('method'),
        'postData': request.get('postData'),
        'headers': {},
    }
    headers = list(request['headers'].keys())
    headers.sort()
    for header in headers:
        if (header == 'Accept' or header == 'Referer' or
                header == 'X-DevTools-Emulate-Network-Conditions-Client-Id'):
            continue
        _hash['headers'][header] = request['headers'][header]  # type: ignore
    return json.dumps(_hash)


def removeURLHash(url: str) -> str:
    """Remove url hash."""
    urlObject, _ = urldefrag(url)
    return urlunparse(urlObject)
