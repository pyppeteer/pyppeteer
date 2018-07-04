#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import sys

from pyppeteer import launch

dumpio = '--dumpio' in sys.argv


async def main():
    browser = await launch(args=['--no-sandbox'], dumpio=dumpio)
    page = await browser.newPage()
    await page.evaluate('console.log("DUMPIO_TEST")')
    await page.close()
    await browser.close()


asyncio.get_event_loop().run_until_complete(main())
