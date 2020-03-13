#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Network Manager module."""

import asyncio
import base64
import copy
import json
import logging
from http import HTTPStatus
from typing import Awaitable, Dict, List, Optional, Union, Set, TYPE_CHECKING, Any

from pyee import AsyncIOEventEmitter

from pyppeteer.connection import CDPSession
from pyppeteer.errors import NetworkError
from pyppeteer.events import Events
from pyppeteer.helper import debugError

if TYPE_CHECKING:
    from pyppeteer.frame_manager import FrameManager, Frame

logger = logging.getLogger(__name__)


class NetworkManager(AsyncIOEventEmitter):
    """NetworkManager class."""

    def __init__(self, client: CDPSession, ignoreHttpsErrors: bool, frameManager: 'FrameManager') -> None:
        """Make new NetworkManager."""
        super().__init__()
        self._client = client
        self._ignoreHTTPSErrors = ignoreHttpsErrors
        self._frameManager = frameManager
        self._requestIdToRequest: Dict[Optional[str], Request] = {}
        self._requestIdToRequestWillBeSent: Dict[Optional[str], Dict] = {}
        self._extraHTTPHeaders: Dict[str, str] = {}
        self._offline: bool = False
        self._credentials: Optional[Dict[str, str]] = None
        self._attemptedAuthentications: Set[Optional[str]] = set()
        self._userRequestInterceptionEnabled = False
        self._protocolRequestInterceptionEnabled = False
        self._userCacheDisabled = False
        self._requestIdToInterceptionId: Dict[str, str] = {}

        self._client.on('Fetch.requestPaused', self._onRequestPaused)
        self._client.on('Fetch.authRequired', self._onAuthRequired)
        self._client.on('Network.requestWillBeSent', self._onRequestWillBeSent)
        self._client.on('Network.requestServedFromCache', self._onRequestServedFromCache)
        self._client.on('Network.responseReceived', self._onResponseReceived)
        self._client.on('Network.loadingFinished', self._onLoadingFinished)
        self._client.on('Network.loadingFailed', self._onLoadingFailed)

    async def initialize(self):
        await self._client.send('Network.enable')
        if self._ignoreHTTPSErrors:
            await self._client.send('Security.setIgnoreCertificateErrors', {'ignore': True})

    async def authenticate(self, credentials: Dict[str, str]) -> None:
        """Provide credentials for http auth."""
        self._credentials = credentials
        await self._updateProtocolRequestInterception()

    async def setExtraHTTPHeaders(self, extraHTTPHeaders: Dict[str, str]) -> None:
        """Set extra http headers."""
        self._extraHTTPHeaders = {}
        for k, v in extraHTTPHeaders.items():
            if not isinstance(v, str):
                raise TypeError(f'Expected value of header "{k}" to be string, ' f'but {type(v)} is found.')
            self._extraHTTPHeaders[k.lower()] = v
        await self._client.send('Network.setExtraHTTPHeaders', {'headers': self._extraHTTPHeaders})

    def extraHTTPHeaders(self) -> Dict[str, str]:
        """Get extra http headers."""
        return dict(**self._extraHTTPHeaders)

    async def setOfflineMode(self, value: bool) -> None:
        """Change offline mode enable/disable."""
        if self._offline == value:
            return
        self._offline = value
        await self._client.send(
            'Network.emulateNetworkConditions',
            {'offline': self._offline, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1, },
        )

    async def setUserAgent(self, userAgent: str) -> None:
        """Set user agent."""
        await self._client.send('Network.setUserAgentOverride', {'userAgent': userAgent})

    async def setCacheEnabled(self, enabled: bool) -> None:
        self._userCacheDisabled = not enabled
        await self._updateProtocolCacheDisabled()

    async def setRequestInterception(self, value: bool) -> None:
        """Enable request interception."""
        self._userRequestInterceptionEnabled = value
        await self._updateProtocolRequestInterception()

    async def _updateProtocolRequestInterception(self) -> None:
        enabled = self._userRequestInterceptionEnabled or bool(self._credentials)
        if enabled == self._protocolRequestInterceptionEnabled:
            return
        self._protocolRequestInterceptionEnabled = enabled
        if enabled:
            await asyncio.gather(
                self._updateProtocolCacheDisabled(),
                self._client.send('Fetch.enable', {'handleAuthRequests': True, 'patterns': {'urlPattern': '*'}}),
            )
        else:
            await asyncio.gather(self._updateProtocolCacheDisabled(), self._client.send('Fetch.disable'))

    async def _updateProtocolCacheDisabled(self):
        await self._client.send(
            'Network.setCacheDisabled',
            {'cacheDisabled': self._userCacheDisabled or self._protocolRequestInterceptionEnabled},
        )

    async def _onRequestWillBeSent(self, event: Dict) -> None:
        is_data_request = event.get('request', {}).get('url', '').startswith('data:')
        if self._protocolRequestInterceptionEnabled and not is_data_request:
            requestId = event['requestId']
            interceptionId = self._requestIdToInterceptionId.get(requestId)  # noqa: E501
            if interceptionId:
                self._onRequest(event, interceptionId)
                self._requestIdToInterceptionId.pop(requestId)  # noqa: E501
            else:
                self._requestIdToResponseWillBeSent[requestId] = event  # noqa: E501
            return
        self._onRequest(event, None)

    async def _onAuthRequired(self, event: Dict):
        response = 'Default'
        requestId = event.get('requestId')
        if requestId in self._attemptedAuthentications:
            response = 'CancelAuth'
        elif self._credentials:
            response = 'ProvideCredentials'
            self._attemptedAuthentications.add(requestId)
        username = self._credentials.get('username')
        password = self._credentials.get('password')
        await self._client.send(
            'Fetch.continueWithAuth',
            {
                'requestId': requestId,
                'authChallengeResponse': {"response": response, "username": username, "password": password, },
            },
        )

    async def _onRequestPaused(self, event: Dict):
        if self._userRequestInterceptionEnabled and self._protocolRequestInterceptionEnabled:
            await self._client.send('Fetch.continueRequest', {'requestId': event.get('requestId')})
        requestId = event.get('networkId')
        interceptionId = event.get('requestId')
        if requestId in self._requestIdToRequestWillBeSent:
            requestWillBeSentEvent = self._requestIdToRequestWillBeSent.pop(requestId)
            self._onRequest(requestWillBeSentEvent, interceptionId)
        else:
            self._requestIdToInterceptionId[requestId] = interceptionId

    def _onRequest(self, event: Dict, interceptionId: Optional[str]) -> None:
        redirectChain: List[Request] = []
        if event.get('redirectResponse'):
            request = self._requestIdToRequest.get(event['requestId'])
            if request:
                redirectResponse = event['redirectResponse']
                self._handleRequestRedirect(request, **redirectResponse)
                redirectChain = request._redirectChain

        frame = self._frameManager.frame(event.get('frameId'))
        request = Request(
            client=self._client,
            frame=frame,
            interceptionId=interceptionId,
            allowInterception=self._userRequestInterceptionEnabled,
            event=event,
            redirectChain=redirectChain,
        )
        self._requestIdToRequest[event['requestId']] = request
        self.emit(Events.NetworkManager.Request, request)

    def _onRequestServedFromCache(self, event: Dict) -> None:
        request = self._requestIdToRequest.get(event.get('requestId'))
        if request:
            request._fromMemoryCache = True

    def _handleRequestRedirect2(self, request: 'Request', responsePayload: Dict):
        resp = Response(self._client, request, **responsePayload)

    def _handleRequestRedirect(
            self,
            request: 'Request',
            status: int,
            headers: Dict,
            fromDiskCache: bool,
            fromServiceWorker: bool,
            securityDetails: Dict = None,
    ) -> None:
        response = Response2(
            client=self._client,
            request=request,
            status=status,
            headers=headers,
            fromDiskCache=fromDiskCache,
            fromServiceWorker=fromServiceWorker,
            securityDetails=securityDetails,
        )
        request._response = response
        request._redirectChain.append(request)
        response._bodyLoadedPromiseFulfill(NetworkError('Response body is unavailable for redirect response'))
        self._requestIdToRequest.pop(request._requestId, None)
        self._attemptedAuthentications.discard(request._interceptionId)
        self.emit(Events.NetworkManager.Response, response)
        self.emit(Events.NetworkManager.RequestFinished, request)

    def _onResponseReceived(self, event: dict) -> None:
        request = self._requestIdToRequest.get(event['requestId'])
        # FileUpload sends a response without a matching request.
        if not request:
            return
        event_response = event.get('response', {})
        event_response['client'] = self._client
        event_response['request'] = request
        response = Response(**event_response)
        request._response = response
        self.emit(Events.NetworkManager.Response, response)

    def _onLoadingFinished(self, event: dict) -> None:
        request = self._requestIdToRequest.get(event['requestId'])
        # For certain requestIds we never receive requestWillBeSent event.
        # @see https://crbug.com/750469
        if not request:
            return
        response = request.response
        if response:
            response._bodyLoadedPromiseFulfill(None)
        self._requestIdToRequest.pop(request._requestId, None)
        self._attemptedAuthentications.discard(request._interceptionId)
        self.emit(Events.NetworkManager.RequestFinished, request)

    def _onLoadingFailed(self, event: dict) -> None:
        request = self._requestIdToRequest.get(event['requestId'])
        # For certain requestIds we never receive requestWillBeSent event.
        # @see https://crbug.com/750469
        if not request:
            return
        request._failureText = event.get('errorText')
        response = request.response
        if response:
            response._bodyLoadedPromiseFulfill(None)
        self._requestIdToRequest.pop(request._requestId, None)
        self._attemptedAuthentications.discard(request._interceptionId)
        self.emit(Events.NetworkManager.RequestFailed, request)


class Request:
    """Request class.

    Whenever the page sends a request, such as for a network resource, the
    following events are emitted by pyppeteer's page:

    - ``'request'``: emitted when the request is issued by the page.
    - ``'response'``: emitted when/if the response is received for the request.
    - ``'requestfinished'``: emitted when the response body is downloaded and
      the request is complete.

    If request fails at some point, then instead of ``'requestfinished'`` event
    (and possibly instead of ``'response'`` event), the ``'requestfailed'``
    event is emitted.

    If request gets a ``'redirect'`` response, the request is successfully
    finished with the ``'requestfinished'`` event, and a new request is issued
    to a redirect url.
    """

    def __init__(
            self,
            client: CDPSession,
            frame: 'Frame',
            interceptionId: Optional[str],
            allowInterception: bool,
            event: dict,
            redirectChain: List['Request'],
    ) -> None:
        self._client = client
        self._requestId = event['requestId']
        self._isNavigationRequest = self._requestId == event.get('loaderId') and event['type'] == 'Document'
        self._interceptionId = interceptionId
        self._allowInterception = allowInterception
        self._interceptionHandled = False
        self._response: Optional[Response] = None
        self._failureText: Optional[str] = None

        req = event['request']
        self._url = req['url']
        self._resourceType = event['type'].lower()
        self._method = req['method']
        self._postData = req.get('postData')
        self._frame = frame
        self._redirectChain = redirectChain
        self._headers = {k.lower(): v for k, v in req.get('headers', {}).items()}
        self._fromMemoryCache = False

    @property
    def url(self) -> str:
        """URL of this request."""
        return self._url

    @property
    def resourceType(self) -> str:
        """Resource type of this request perceived by the rendering engine.

        ResourceType will be one of the following: ``document``,
        ``stylesheet``, ``image``, ``media``, ``font``, ``script``,
        ``texttrack``, ``xhr``, ``fetch``, ``eventsource``, ``websocket``,
        ``manifest``, ``other``.
        """
        return self._resourceType

    @property
    def method(self) -> Optional[str]:
        """Return this request's method (GET, POST, etc.)."""
        return self._method

    @property
    def postData(self) -> Optional[str]:
        """Return post body of this request."""
        return self._postData

    @property
    def headers(self) -> Dict:
        """Return a dictionary of HTTP headers of this request.

        All header names are lower-case.
        """
        return self._headers

    @property
    def response(self) -> Optional['Response']:
        """Return matching :class:`Response` object, or ``None``.

        If the response has not been received, return ``None``.
        """
        return self._response

    @property
    def frame(self) -> Optional['Frame']:
        """Return a matching :class:`~pyppeteer.frame_manager.frame` object.

        Return ``None`` if navigating to error page.
        """
        return self._frame

    def isNavigationRequest(self) -> bool:
        """Whether this request is driving frame's navigation."""
        return self._isNavigationRequest

    @property
    def redirectChain(self) -> List['Request']:
        """Return chain of requests initiated to fetch a resource.

        * If there are no redirects and request was successful, the chain will
          be empty.
        * If a server responds with at least a single redirect, then the chain
          will contain all the requests that were redirected.

        ``redirectChain`` is shared between all the requests of the same chain.
        """
        return copy.copy(self._redirectChain)

    def failure(self) -> Optional[Dict]:
        """Return error text.

        Return ``None`` unless this request was failed, as reported by
        ``requestfailed`` event.

        When request failed, this method return dictionary which has a
        ``errorText`` field, which contains human-readable error message, e.g.
        ``'net::ERR_RAILED'``.
        """
        if not self._failureText:
            return None
        return {'errorText': self._failureText}

    async def continue_(self, overrides: Dict = None) -> None:
        """Continue request with optional request overrides.

        To use this method, request interception should be enabled by
        :meth:`pyppeteer.page.Page.setRequestInterception`. If request
        interception is not enabled, raise ``NetworkError``.

        ``overrides`` can have the following fields:

        * ``url`` (str): If set, the request url will be changed.
        * ``method`` (str): If set, change the request method (e.g. ``GET``).
        * ``postData`` (str): If set, change the post data or request.
        * ``headers`` (dict): If set, change the request HTTP header.
        """
        if self._url.startswith('data:'):
            return
        if overrides is None:
            overrides = {}

        if not self._allowInterception:
            raise NetworkError('Request interception is not enabled.')
        if self._interceptionHandled:
            raise NetworkError('Request is already handled.')

        self._interceptionHandled = True
        options = {'interceptionId': self._interceptionId}
        options.update(overrides)
        try:
            await self._client.send('Network.continueRequest', options)
        except Exception as e:
            debugError(logger, e)

    async def respond(self, response: Dict) -> None:  # noqa: C901
        """Fulfills request with given response.

        To use this, request interception should by enabled by
        :meth:`pyppeteer.page.Page.setRequestInterception`. Request
        interception is not enabled, raise ``NetworkError``.

        ``response`` is a dictionary which can have the following fields:

        * ``status`` (int): Response status code, defaults to 200.
        * ``headers`` (dict): Optional response headers.
        * ``contentType`` (str): If set, equals to setting ``Content-Type``
          response header.
        * ``body`` (str|bytes): Optional response body.
        """
        if self._url.startswith('data:'):
            return
        if not self._allowInterception:
            raise NetworkError('Request interception is not enabled.')
        if self._interceptionHandled:
            raise NetworkError('Request is already handled.')
        self._interceptionHandled = True

        if response.get('body') and isinstance(response['body'], str):
            responseBody: Optional[bytes] = response['body'].encode('utf-8')
        else:
            responseBody = response.get('body')

        responseHeaders = {}
        if response.get('headers'):
            for header in response['headers']:
                responseHeaders[header.lower()] = response['headers'][header]
        if response.get('contentType'):
            responseHeaders['content-type'] = response['contentType']
        if responseBody and 'content-length' not in responseHeaders:
            responseHeaders['content-length'] = len(responseBody)

        status_code = response.get('status', 200)
        status_phrase = STATUS_TEXTS.get(status_code, '')
        try:
            await self._client.send(
                'Fetch.fulfillRequest',
                {
                    'requestId': self._interceptionId,
                    'responseCode': status_code,
                    'responsePhrase': status_phrase,
                    'responseHeaders': responseHeaders,
                    'body': base64.b64encode(responseBody).decode('ascii'),
                },
            )
        except Exception as e:
            debugError(logger, e)

    async def abort(self, errorCode: str = 'failed') -> None:
        """Abort request.

        To use this, request interception should be enabled by
        :meth:`pyppeteer.page.Page.setRequestInterception`.
        If request interception is not enabled, raise ``NetworkError``.

        ``errorCode`` is an optional error code string. Defaults to ``failed``,
        could be one of the following:

        - ``aborted``: An operation was aborted (due to user action).
        - ``accessdenied``: Permission to access a resource, other than the
          network, was denied.
        - ``addressunreachable``: The IP address is unreachable. This usually
          means that there is no route to the specified host or network.
        - ``blockedbyclient``: The client chose to block the request.
        - ``blockedbyresponse``: The request failed because the request was
          delivered along with requirements which are not met
          ('X-Frame-Options' and 'Content-Security-Policy' ancestor check,
          for instance).
        - ``connectionaborted``: A connection timeout as a result of not
          receiving an ACK for data sent.
        - ``connectionclosed``: A connection was closed (corresponding to a TCP
          FIN).
        - ``connectionfailed``: A connection attempt failed.
        - ``connectionrefused``: A connection attempt was refused.
        - ``connectionreset``: A connection was reset (corresponding to a TCP
          RST).
        - ``internetdisconnected``: The Internet connection has been lost.
        - ``namenotresolved``: The host name could not be resolved.
        - ``timedout``: An operation timed out.
        - ``failed``: A generic failure occurred.
        """
        if self._url.startswith('data:'):
            return
        errorReason = errorReasons[errorCode]
        if not errorReason:
            raise NetworkError('Unknown error code: {}'.format(errorCode))
        if not self._allowInterception:
            raise NetworkError('Request interception is not enabled.')
        if self._interceptionHandled:
            raise NetworkError('Request is already handled.')
        self._interceptionHandled = True
        try:
            await self._client.send(
                'Fetch.failRequest', {'requestId': self._interceptionId, 'errorReason': errorReason}
            )
        except Exception as e:
            debugError(logger, e)




class Response(object):
    """Response class represents responses which are received by ``Page``."""

    def __init__(
            self,
            client: CDPSession,
            request: Request,
            status: int,
            headers: Dict[str, str],
            fromDiskCache: bool,
            fromServiceWorker: bool,
            securityDetails: Dict = None,
            remoteIpAddress: str = '',
            remotePort: str = '',
            statusText: str = '',
    ) -> None:
        self._client = client
        self._request = request
        self._contentPromise = self._client.loop.create_future()
        self._bodyLoadedPromise = self._client.loop.create_future()
        self._remoteAddress = {
            'ip': remoteIpAddress,
            'port': remotePort,
        }
        self._status = status
        self._statusText = statusText
        self._url = request.url
        self._fromDiskCache = fromDiskCache
        self._fromServiceWorker = fromServiceWorker
        self._headers = {k.lower(): v for k, v in headers.items()}
        self._securityDetails: Union[Dict, SecurityDetails] = {}
        if securityDetails:
            self._securityDetails = SecurityDetails(
                securityDetails['subjectName'],
                securityDetails['issuer'],
                securityDetails['validFrom'],
                securityDetails['validTo'],
                securityDetails['protocol'],
            )

    @property
    def remoteAddress(self):
        return self._remoteAddress

    @property
    def url(self) -> str:
        """URL of the response."""
        return self._url

    @property
    def ok(self) -> bool:
        """Return bool whether this request is successful (200-299) or not."""
        return self._status == 0 or 200 <= self._status <= 299

    @property
    def status(self) -> int:
        """Status code of the response."""
        return self._status

    @property
    def statusText(self):
        return self._statusText

    @property
    def headers(self) -> Dict:
        """Return dictionary of HTTP headers of this response.

        All header names are lower-case.
        """
        return self._headers

    @property
    def securityDetails(self) -> Union[Dict, 'SecurityDetails']:
        """Return security details associated with this response.

        Security details if the response was received over the secure
        connection, or `None` otherwise.
        """
        return self._securityDetails

    async def _bufread(self) -> bytes:
        result = await self._bodyLoadedPromise
        if isinstance(result, Exception):
            raise result
        response = await self._client.send('Network.getResponseBody', {'requestId': self._request._requestId})
        body = response.get('body', b'')
        if response.get('base64Encoded'):
            return base64.b64decode(body)
        return body

    def buffer(self) -> Awaitable[bytes]:
        """Return awaitable which resolves to bytes with response body."""
        if not self._contentPromise.done():
            return self._client.loop.create_task(self._bufread())
        return self._contentPromise

    async def text(self) -> str:
        """Get text representation of response body."""
        content = await self.buffer()
        if isinstance(content, str):
            return content
        else:
            return content.decode('utf-8')

    async def json(self) -> dict:
        """Get JSON representation of response body."""
        content = await self.text()
        return json.loads(content)

    @property
    def request(self) -> Request:
        """Get matching :class:`Request` object."""
        return self._request

    @property
    def fromCache(self) -> bool:
        """Return ``True`` if the response was served from cache.

        Here `cache` is either the browser's disk cache or memory cache.
        """
        return self._fromDiskCache or self._request._fromMemoryCache

    @property
    def fromServiceWorker(self) -> bool:
        """Return ``True`` if the response was served by a service worker."""
        return self._fromServiceWorker

    @property
    def frame(self):
        return self._request.frame

    def _bodyLoadedPromiseFulfill(self, value: Optional[Exception]) -> None:
        self._bodyLoadedPromise.set_result(value)


class SecurityDetails:
    """Class represents responses which are received by page."""

    def __init__(self, subjectName: str, issuer: str, validFrom: int, validTo: int, protocol: str) -> None:
        self._subjectName = subjectName
        self._issuer = issuer
        self._validFrom = validFrom
        self._validTo = validTo
        self._protocol = protocol

    @property
    def subjectName(self) -> str:
        """Return the subject to which the certificate was issued to."""
        return self._subjectName

    @property
    def issuer(self) -> str:
        """Return a string with the name of issuer of the certificate."""
        return self._issuer

    @property
    def validFrom(self) -> int:
        """Return UnixTime of the start of validity of the certificate."""
        return self._validFrom

    @property
    def validTo(self) -> int:
        """Return UnixTime of the end of validity of the certificate."""
        return self._validTo

    @property
    def protocol(self) -> str:
        """Return string of with the security protocol, e.g. "TLS1.2"."""
        return self._protocol


class Response2:
    def __init__(self, client: CDPSession, request, responsePayload):
        self._client = client
        self._request = request
        self._contentFuture = None

        self._bodyLoadedFuture = client.loop.create_future()
        self._bodyLoadedFutureFulFill = lambda: self._bodyLoadedFuture.set_result(None)

        self._remoteAddress = {
            'ip': responsePayload.get('remoteIPAddress'),
            'port': responsePayload.get('remotePort'),
        }
        self._status = responsePayload.get('status')
        self._statusText = responsePayload.get('statusText')
        self._url = request.get('url')
        self._fromDiskCache = bool(responsePayload.get('fromDiskCache'))
        self._fromServiceWorker = bool(responsePayload.get('fromServiceWorker'))
        self._headers = {k.lower(): v for k, v in responsePayload.get('headers', {}).items()}
        if responsePayload.get('securityDetails'):
            self._securityDetails = SecurityDetails(**responsePayload.get('securityDetails'))
        else:
            self._securityDetails = None

    @property
    def remoteAddress(self):
        return self._remoteAddress

    @property
    def url(self):
        return self._url

    @property
    def ok(self):
        return self._status == 0 or (200 <= self._status < 300)

    @property
    def status(self):
        return self._status

    @property
    def statusText(self):
        return self._statusText

    @property
    def headers(self):
        return self._headers

    @property
    def securityDetails(self):
        return self._securityDetails

    async def buffer(self):
        # todo: verify
        if self._contentFuture is None:
            async def buffer_read():
                self._contentFuture = await self._bodyLoadedFuture
                response = await self._client.send(
                    'Network.getResponseBody',
                    {'requestId': self._request._requestId}
                )
                body = await response.get('body', b'')
                if response.get('base64Encoded'):
                    return base64.b64decode(body)
                return body

            return self._client.loop.create_task(buffer_read())

    @property
    async def text(self):
        # todo is this a UTF-8 str or not
        return await self.buffer()

    @property
    async def json(self):
        return json.loads(await self.text)

    @property
    def request(self):
        return self._request

    @property
    def fromCache(self):
        return self._fromDiskCache or self._request._fromMemoryCache

    @property
    def fromServiceWorker(self):
        return self._fromServiceWorker

    @property
    def frame(self):
        return self._request.frame()


class Request2:
    _errorReasons = {
        'aborted': 'Aborted',
        'accessdenied': 'AccessDenied',
        'addressunreachable': 'AddressUnreachable',
        'blockedbyclient': 'BlockedByClient',
        'blockedbyresponse': 'BlockedByResponse',
        'connectionaborted': 'ConnectionAborted',
        'connectionclosed': 'ConnectionClosed',
        'connectionfailed': 'ConnectionFailed',
        'connectionrefused': 'ConnectionRefused',
        'connectionreset': 'ConnectionReset',
        'internetdisconnected': 'InternetDisconnected',
        'namenotresolved': 'NameNotResolved',
        'timedout': 'TimedOut',
        'failed': 'Failed',
    }

    def __init__(self, client: CDPSession, frame: Frame, interceptionId: str, allowInterception: bool,
                 event: Dict[str, Any],
                 redirectChain: List['Request2']):
        self._client = client
        self._requestId = event.get('requestId')
        self._isNavigationRequest = self._requestId == event.get('loaderId') and event['type'] == 'Document'
        self._interceptionId = interceptionId
        self._allowInterception = allowInterception
        self._interceptionHandled = False
        self._response = None
        self._failureText = None

        request_event = event['request']
        self._url = request_event['url']
        self._resourceType = request_event['type'].lower()
        self._method = request_event['method']
        self._postData = request_event.get('postData')
        self._frame = frame;
        self._redirectChain = redirectChain;
        self._headers = {k.lower(): v for k, v in request_event.get('headers', {}).items()}

        self._fromMemoryCache = False

    @property
    def url(self):
        return self._url

    @property
    def resourceType(self):
        return self._resourceType

    @property
    def method(self):
        return self._method

    @property
    def postData(self):
        return self._postData

    @property
    def headers(self):
        return self._headers

    @property
    def response(self):
        return self._response

    @property
    def frame(self):
        return self._frame

    @property
    def isNavigationRequest(self):
        return self._isNavigationRequest

    @property
    def redirectChain(self):
        return self._redirectChain

    @property
    def failure(self):
        return None if not self._failureText else {'errorText': self._failureText}

    async def continue_(self, overrides: Dict[str, Any]) -> None:
        if not self._actionable_request:
            return

        available_overrides = {'url', 'method', 'postData', 'headers'}
        overrides = {k: v for k, v in overrides.items() if k in available_overrides}
        if overrides.get('headers'):
            overrides['headers'] = headersArray(overrides['headers'])

        self._interceptionHandled = True
        # todo: verify whether undefined == not specifying at all
        try:
            await self._client.send('Fetch.continueRequest', {'requestId': self._interceptionId, **overrides})
        except Exception as e:
            # In certain cases, protocol will return error if the request was already canceled
            # or the page was closed. We should tolerate these errors.
            debugError(logger, str(e))

    async def respond(self, response: Dict[str, Any]) -> None:
        if not self._actionable_request:
            return
        self._interceptionHandled = True

        if isinstance(response.get('body'), str):
            # todo: buffer stuff here
            responseBody = None
        else:
            responseBody = response.get('body')

        responseHeaders = {k.lower(): v for k, v in response.get('headers', {}).items()}
        if response.get('content-type'):
            responseHeaders['content-type'] = response['content-type']
        if responseBody and 'content-length' not in responseHeaders:
            responseHeaders['content-length'] = str(len(responseBody))
        try:
            await self._client.send('Fetch.fulfillRequest',
                                    {
                                        'requestId': self._interceptionId,
                                        'responseCode': response.get('status', 200),
                                        'responsePhrase': STATUS_TEXTS[int(response.get('status', 200))],
                                        'responseHeaders': headersArray(responseHeaders),
                                        'body': base64.b64encode(responseBody) if responseBody else None,
                                    })
        except Exception as e:
            # todo: find out what error is raised from here
            # In certain cases, protocol will return error if the request was already canceled
            # or the page was closed. We should tolerate these errors.
            debugError(logger, str(e))

    async def abort(self, errorCode: str = 'failed'):
        if not self._actionable_request:
            return

        errorReason = self._errorReasons.get(errorCode)
        if not errorReason:
            raise NetworkError(f'Unknown error code: {errorCode}')

        self._interceptionHandled = True
        try:
            await self._client.send(
                'Fetch.failRequest', {'requestId': self._interceptionId, 'errorReason': errorReason}
            )
        except Exception as e:
            # In certain cases, protocol will return error if the request was already canceled
            # or the page was closed. We should tolerate these errors.
            debugError(logger, e)

    @property
    def _actionable_request(self) -> bool:
        """
        Checks if we can abort/continue/respond to request.
        :return: True if we can, False if we can't
        """
        # Mocking responses for dataURL requests is not currently supported.
        if self._url.startswith('data:'):
            return False
        if not self._allowInterception:
            raise ValueError('Request Interception is not enabled!')
        if self._interceptionHandled:
            raise ValueError('Request is already handled')
        return True


def headersArray(headers: Dict[str, str]) -> List[Dict[str, str]]:
    return [{'name': k, 'value': v} for k, v in headers.items() if v is not None]


STATUS_TEXTS = {num.value: code for code, num in vars(HTTPStatus).items() if isinstance(num, HTTPStatus)}
