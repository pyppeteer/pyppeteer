#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Network Manager module."""

import asyncio
import base64
from collections import OrderedDict
import json
from urllib.parse import urldefrag
from types import SimpleNamespace
from typing import Any, Awaitable, Dict, TYPE_CHECKING

from pyee import EventEmitter

from pyppeteer.connection import Session
from pyppeteer.errors import NetworkError
from pyppeteer.multimap import Multimap

if TYPE_CHECKING:
    from typing import Optional, Set  # noqa: F401


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
        self._credentials: Optional[Dict[str, str]] = None
        self._attemptedAuthentications: Set[str] = set()
        self._userRequestInterceptionEnabled = False
        self._protocolRequestInterceptionEnabled = False
        self._requestHashToRequestIds = Multimap()
        self._requestHashToInterceptions = Multimap()

        self._client.on('Network.requestWillBeSent', self._onRequestWillBeSent)
        self._client.on('Network.requestIntercepted', self._onRequestIntercepted)  # noqa: E501
        self._client.on('Network.responseReceived', self._onResponseReceived)
        self._client.on('Network.loadingFinished', self._onLoadingFinished)
        self._client.on('Network.loadingFailed', self._onLoadingFailed)

    async def authenticate(self, credentials: Dict[str, str]) -> None:
        """Provide credentials for http auth."""
        self._credentials = credentials
        await self._updateProtocolRequestInterception()

    async def setExtraHTTPHeaders(self, extraHTTPHeaders: Dict[str, str]
                                  ) -> None:
        """Set extra http headers."""
        self._extraHTTPHeaders = OrderedDict()
        headers = OrderedDict()  # type: Dict[str, str]
        for k, v in extraHTTPHeaders.items():
            self._extraHTTPHeaders[k] = v
            headers[k] = v
        await self._client.send('Network.setExtraHTTPHeaders',
                                {'headers': headers})

    def extraHTTPHeaders(self) -> Dict[str, str]:
        """Get extra http headers."""
        return dict(**self._extraHTTPHeaders)

    async def setUserAgent(self, userAgent: str) -> Any:
        """Set user agent."""
        return await self._client.send('Network.setUserAgentOverride',
                                       {'userAgent': userAgent})

    async def setRequestInterceptionEnabled(self, value: bool) -> None:
        """Enable request intercetion."""
        self._userRequestInterceptionEnabled = value
        await self._updateProtocolRequestInterception()

    async def _updateProtocolRequestInterception(self) -> None:
        enabled = (self._userRequestInterceptionEnabled or
                   bool(self._credentials))
        if enabled == self._protocolRequestInterceptionEnabled:
            return
        self._protocolRequestInterceptionEnabled = enabled
        await self._client.send(
            'Network.setRequestInterceptionEnabled',
            {'enabled': enabled},
        )

    def _onRequestIntercepted(self, event: dict) -> None:
        event['request']['url'] = removeURLHash(
            event['request'].get('url', '')
        )

        if event.get('authChallenge'):
            response = 'Default'
            if event['interceptionId'] in self._attemptedAuthentications:
                response = 'CancelAuth'
            elif self._credentials:
                response = 'ProvideCredentials'
                self._attemptedAuthentications.add(event['interceptionId'])
            username = getattr(self, '_credentials', {}).get('username')
            password = getattr(self, '_credentials', {}).get('password')
            asyncio.ensure_future(self._client.send(
                'Network.continueInterceptedRequest', {
                    'interceptionId': event['interceptionId'],
                    'authChallengeResponse': {
                        'response': response,
                        'username': username,
                        'password': password,
                    }
                }
            ))
            return

        if (not self._userRequestInterceptionEnabled and
                self._protocolRequestInterceptionEnabled):
            asyncio.ensure_future(self._client.send(
                'Network.continueInterceptedRequest', {
                    'interceptionId': event['interceptionId'],
                }
            ))

        if 'redirectStatusCode' in event:
            request = self._interceptionIdToRequest.get(
                event.get('interceptionId', ''))
            if not request:
                raise NetworkError('INTERNAL ERROR: failed to find request '
                                   'for interception redirect.')
            self._handleRequestRedirect(request,
                                        event.get('redirectStatusCode', 0),
                                        event.get('redirectHeaders', {}))
            self._handleRequestStart(request._requestId,
                                     event.get('interceptionId', ''),
                                     event.get('redirectUrl', ''),
                                     event.get('resourceType', ''),
                                     event.get('request', {}))
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
        self._attemptedAuthentications.discard(request._interceptionId)
        self.emit(NetworkManager.Events.Response, response)
        self.emit(NetworkManager.Events.RequestFinished, request)

    def _handleRequestStart(self, requestId: str, interceptionId: str,
                            url: str, resourceType: str, requestPayload: dict
                            ) -> None:
        request = Request(self._client, requestId, interceptionId,
                          self._userRequestInterceptionEnabled, url,
                          resourceType, requestPayload)
        self._requestIdToRequest[requestId] = request
        self._interceptionIdToRequest[interceptionId] = request
        self.emit(NetworkManager.Events.Request, request)

    def _onRequestWillBeSent(self, event: dict) -> None:
        if (self._protocolRequestInterceptionEnabled and
                not event['request'].get('url', '').startswith('data:')):
            if event.get('redirectResponse'):
                return
            requestHash = generateRequestHash(event['request'])
            self._requestHashToRequestIds.set(
                requestHash, event.get('requestId', ''))
            self._maybeResolveInterception(requestHash)
            return
        if event.get('redirectResponse'):
            request = self._requestIdToRequest.get(event['requestId'])
            if request is not None:
                redirectResponse = event.get('redirectResponse', {})
                self._handleRequestRedirect(
                    request,
                    redirectResponse.get('status'),
                    redirectResponse.get('headers'),
                )
        self._handleRequestStart(
            event.get('requestId', ''), '',
            event.get('request', {}).get('url', ''),
            event.get('type', ''),
            event.get('request', {}),
        )

    def _maybeResolveInterception(self, requestHash: str) -> None:
        requestId = self._requestHashToRequestIds.firstValue(requestHash)
        interception = self._requestHashToInterceptions.firstValue(requestHash)
        if not requestId or not interception:
            return
        self._requestHashToRequestIds.delete(requestHash, requestId)
        self._requestHashToInterceptions.delete(requestHash, interception)
        request_obj = interception.get('request', {})
        self._handleRequestStart(
            requestId,
            interception.get('interceptionId', ''),
            request_obj.get('url', ''),
            interception.get('resourceType'),
            request_obj,
        )

    def _onResponseReceived(self, event: dict) -> None:
        request = self._requestIdToRequest.get(event['requestId'])
        # FileUpload sends a response without a matching request.
        if not request:
            return
        _resp = event.get('response', {})
        response = Response(self._client, request,
                            _resp.get('status', 0),
                            _resp.get('headers', {}))
        request._response = response
        self.emit(NetworkManager.Events.Response, response)

    def _onLoadingFinished(self, event: dict) -> None:
        request = self._requestIdToRequest.get(event.get('requestId', ''))
        # For certain requestIds we never receive requestWillBeSent event.
        # @see https://crbug.com/750469
        if not request:
            return
        request._completePromiseFulfill()
        self._requestIdToRequest.pop(request._requestId, None)
        self._interceptionIdToRequest.pop(request._interceptionId, None)
        self._attemptedAuthentications.discard(request._interceptionId)
        self.emit(NetworkManager.Events.RequestFinished, request)

    def _onLoadingFailed(self, event: dict) -> None:
        request = self._requestIdToRequest.get(event['requestId'])
        # For certain requestIds we never receive requestWillBeSent event.
        # @see https://crbug.com/750469
        if not request:
            return
        request._completePromiseFulfill()
        self._requestIdToRequest.pop(request._requestId, None)
        self._interceptionIdToRequest.pop(request._interceptionId, None)
        self._attemptedAuthentications.discard(request._interceptionId)
        self.emit(NetworkManager.Events.RequestFailed, request)


class Request(object):
    """Request class."""

    #: url of this request.
    url: str
    #: headers associated with the request.
    headers: dict
    #: contains the request method (GET/POST/...).
    method: str
    #: contains the request's post body, if any.
    postData: str
    #: contains the request's resource type
    resourceType: str

    def __init__(self, client: Session, requestId: str, interceptionId: str,
                 allowInterception: bool, url: str, resourceType: str,
                 payload: dict) -> None:
        """Make new request class."""
        self._client = client
        self._requestId = requestId
        self._interceptionId = interceptionId
        self._allowInterception = allowInterception
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

    #: whether the repoonse succeeded or not.
    ok: bool
    #: status code of the reponse.
    status: int
    #: url of the reponse.
    url: str

    def __init__(self, client: Session, request: Request, status: int,
                 headers: Dict[str, str]) -> None:
        """Make new response."""
        self._client = client
        self._request = request
        self.status = status
        self._contentPromise = asyncio.get_event_loop().create_future()
        self.ok = 200 <= status <= 299
        self.url = request.url
        self._headers = {k.lower(): v for k, v in headers.items()}

    async def _bufread(self) -> bytes:
        response = await self._client.send('Network.getResponseBody', {
          'requestId': self._request._requestId
        })
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
    url, _ = urldefrag(url)
    return url
