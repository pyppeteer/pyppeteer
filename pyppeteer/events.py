#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Events module

puppeteer equivalent: Events.js
"""


class Events:
    class Page:
        Close = 'close'
        Console = 'console'
        Dialog = 'dialog'
        DOMContentLoaded = 'domcontentloaded'
        Error = 'error'
        # Can't use just 'error' due to node.js special treatment of error events.
        # @see https://nodejs.org/api/events.html#events_error_events
        PageError = 'pageerror'
        Request = 'request'
        Response = 'response'
        RequestFailed = 'requestfailed'
        RequestFinished = 'requestfinished'
        FrameAttached = 'frameattached'
        FrameDetached = 'framedetached'
        FrameNavigated = 'framenavigated'
        Load = 'load'
        Metrics = 'metrics'
        Popup = 'popup'
        WorkerCreated = 'workercreated'
        WorkerDestroyed = 'workerdestroyed'

    class Browser:
        TargetCreated = 'targetcreated'
        TargetDestroyed = 'targetdestroyed'
        TargetChanged = 'targetchanged'
        Disconnected = 'disconnected'

    class BrowserContext:
        TargetCreated = 'targetcreated'
        TargetDestroyed = 'targetdestroyed'
        TargetChanged = 'targetchanged'

    class NetworkManager:
        Request = 'Events.NetworkManager.Request'
        Response = 'Events.NetworkManager.Response'
        RequestFailed = 'Events.NetworkManager.RequestFailed'
        RequestFinished = 'Events.NetworkManager.RequestFinished'

    class FrameManager:
        FrameAttached = 'Events.FrameManager.FrameAttached'
        FrameNavigated = 'Events.FrameManager.FrameNavigated'
        FrameDetached = 'Events.FrameManager.FrameDetached'
        LifecycleEvent = 'Events.FrameManager.LifecycleEvent'
        FrameNavigatedWithinDocument = 'Events.FrameManager.FrameNavigatedWithinDocument'
        ExecutionContextCreated = 'Events.FrameManager.ExecutionContextCreated'
        ExecutionContextDestroyed = 'Events.FrameManager.ExecutionContextDestroyed'

    class Connection:
        Disconnected = 'Events.Connection.Disconnected'

    class CDPSession:
        Disconnected = 'Events.CDPSession.Disconnected'
