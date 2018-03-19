#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Emulation Managet module."""

from pyppeteer import helper
from pyppeteer.connection import CDPSession


class EmulationManager(object):
    """EmulationManager class."""

    def __init__(self, client: CDPSession) -> None:
        """Make new elmulation manager."""
        self._client = client
        self._emulatingMobile = False
        self._injectedTouchScriptId = None

    async def emulateViewport(self, client: CDPSession, viewport: dict
                              ) -> bool:
        """Evaluate viewport."""
        options = dict()
        mobile = viewport.get('isMobile', False)
        options['mobile'] = mobile
        if 'width' in viewport:
            options['width'] = helper.get_positive_int(viewport, 'width')
        if 'height' in viewport:
            options['height'] = helper.get_positive_int(viewport, 'height')

        options['deviceScaleFactor'] = viewport.get('deviceScaleFactor', 1)
        if viewport.get('isLandscape'):
            options['screenOrientation'] = {'angle': 90,
                                            'type': 'landscapePrimary'}
        else:
            options['screenOrientation'] = {'angle': 0,
                                            'type': 'portraitPrimary'}

        await self._client.send('Emulation.setDeviceMetricsOverride', options)
        await self._client.send('Emulation.setTouchEmulationEnabled', {
            'enabled': viewport.get('hasTouch', False),
            'configuration': 'mobile' if mobile else 'desktop'
        })

        injectedTouchEventsFunction = '''
function injectedTouchEventsFunction() {
  const touchEvents = ['ontouchstart', 'ontouchend', 'ontouchmove', 'ontouchcancel'];
  const recepients = [window.__proto__, document.__proto__];
  for (let i = 0; i < touchEvents.length; ++i) {
    for (let j = 0; j < recepients.length; ++j) {
      if (!(touchEvents[i] in recepients[j])) {
        Object.defineProperty(recepients[j], touchEvents[i], {
          value: null, writable: true, configurable: true, enumerable: true
        });
      }
    }
  }
}
        '''  # noqa: E501

        reloadNeeded = False
        if viewport.get('hasTouch') and not self._injectedTouchScriptId:
            source = f'({injectedTouchEventsFunction})()'
            self._injectedTouchScriptId = (await self._client.send(
                'Page.addScriptToEvaluateOnNewDocument',
                {'source': source})).get('identifier')
            reloadNeeded = True
        elif not viewport.get('hasTouch') and self._injectedTouchScriptId:
            await self._client.send(
                'Page.removeScriptToEvaluateOnNewDocument',
                {'identifier': self._injectedTouchScriptId}
            )
            self._injectedTouchScriptId = None
            reloadNeeded = True

        if self._emulatingMobile != mobile:
            reloadNeeded = True
        self._emulatingMobile = mobile
        return reloadNeeded
