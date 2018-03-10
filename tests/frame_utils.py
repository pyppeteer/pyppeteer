#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pyppeteer.frame_manager import Frame
from pyppeteer.page import Page


async def attachFrame(page: Page, frameId: str, url: str) -> None:
    func = '''
        (frameId, url) => {
            const frame = document.createElement('iframe');
            frame.src = url;
            frame.id = frameId;
            document.body.appendChild(frame);
            return new Promise(x => frame.onload = x);
        }
    '''
    await page.evaluate(func, frameId, url)


async def detachFrame(page: Page, frameId: str) -> None:
    func = '''
        (frameId) => {
            const frame = document.getElementById(frameId);
            frame.remove();
        }
    '''
    await page.evaluate(func, frameId)


async def navigateFrame(page: Page, frameId: str, url: str) -> None:
    func = '''
        (frameId, url) => {
            const frame = document.getElementById(frameId);
            frame.src = url;
            return new Promise(x => frame.onload = x);
        }
    '''
    await page.evaluate(func, frameId, url)


def dumpFrames(frame: Frame, indentation: str = '') -> str:
    results = []
    results.append(indentation + frame.url)
    for child in frame.childFrames:
        results.append(dumpFrames(child, '    ' + indentation))
    return '\n'.join(results)
