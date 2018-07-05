#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio

from pyppeteer import launch


async def main() -> None:
    browser = await launch(args=['--no-sandbox'])
    print(browser.wsEndpoint, flush=True)


asyncio.get_event_loop().run_until_complete(main())
