"""
Python port of https://github.com/puppeteer/puppeteer/blob/master/utils/fetch_devices.js

Used to update ../../device_descriptors.py

No attempt is made to properly format the one line expression that contains every device, we leave that to
autoformatters like black. Support some command line options which can be viewed with fetch_devices.py --help.
The device list is retrieved from
https://raw.githubusercontent.com/ChromeDevTools/devtools-frontend/master/front_end/emulated_devices/module.json
if not specified (which is the same data source used by puppeteer)
"""

import asyncio
import json
import logging
from argparse import ArgumentParser
from pathlib import Path
from textwrap import dedent
from typing import Dict, Any
from urllib.request import urlopen

from pyppeteer import launch

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('[{levelname}] {name}: {message}', style='{'))
logging.getLogger('pyppeteer').addHandler(handler)

logger = logging.getLogger('fetch_devices')
logger.addHandler(handler)
logger.setLevel(logging.INFO)
handler.setLevel(logging.INFO)


class Loader:
    @classmethod
    def from_JSON_V1(cls, parsed_json: Dict[str, Any]):
        res = {
            'type': cls.parse_value(parsed_json, 'type', str),
            'userAgent': cls.parse_value(parsed_json, 'user-agent', str),
        }
        capabilities = cls.parse_value(parsed_json, 'capabilities', list, [])
        if not isinstance(capabilities, list):
            raise ValueError('Emulated device capabilities must be an array')
        if any(True for capability in capabilities if not isinstance(capability, str)):
            raise ValueError('Emulated device capability must be a string')
        res['capabilities'] = capabilities
        device_scale_f = cls.parse_value(parsed_json['screen'], 'device-pixel-ratio', (int, float))
        if 0 > device_scale_f > 100:
            raise ValueError(f'Emulated device has wrong deviceScaleFactor: {device_scale_f}')
        res['deviceScaleFactor'] = device_scale_f
        res['vertical'] = cls.parse_orientation(cls.parse_value(parsed_json['screen'], 'vertical', dict))
        res['horizontal'] = cls.parse_orientation(cls.parse_value(parsed_json['screen'], 'horizontal', dict))
        return res

    @staticmethod
    def parse_value(d: Dict, key: str, type_, defaultVal=None):
        if not isinstance(d, dict) or d is None or key not in d:
            if d is not None:
                return defaultVal
            raise ValueError(f'Emulated device is missing required property \'{key}\'')
        val = d.get(key)
        if val is None or not isinstance(val, type_):
            raise ValueError(f'Emulated device property \'{key}\' has wrong type \'{type(val)}\'')
        return val

    @classmethod
    def parse_int_value(cls, d: Dict, key):
        val = cls.parse_value(d, key, int)
        if val < 0:
            raise ValueError(f'Emulated device value \'{key}\' must be a positive integer')
        return val

    @classmethod
    def parse_orientation(cls, d: Dict):
        parsed_orient = {}
        min_device_size = 50
        max_device_size = 9999
        width = cls.parse_int_value(d, 'width')
        if min_device_size > width > max_device_size:
            raise ValueError(f'Emulated device has wrong width: {width}')
        parsed_orient['width'] = width

        height = cls.parse_int_value(d, 'height')
        if min_device_size > height > max_device_size:
            raise ValueError(f'Emulated device has wrong height: {height}')
        parsed_orient['height'] = height

        return parsed_orient


def create_device(chrome_version, device_name, payload, landscape):
    payload = Loader.from_JSON_V1(payload)
    viewport = payload['horizontal'] if landscape else payload['vertical']
    return {
        'name': f'{device_name}{" landscape" if landscape else ""}',
        'userAgent': payload['userAgent'] % chrome_version if '%s' in payload['userAgent'] else payload['userAgent'],
        'viewport': {
            'width': viewport['width'],
            'height': viewport['height'],
            'deviceScaleFactor': payload['deviceScaleFactor'],
            'isMobile': 'mobile' in payload['capabilities'],
            'hasTouch': 'touch' in payload['capabilities'],
            'isLandscape': landscape,
        },
    }


async def _fetch_devices(output_path: Path, url: str):
    logger.info(f'output path resolved: {output_path.absolute().as_posix()}')
    logger.info(f'retrieving chrome version info: {url}')
    browser = await launch(args=['--no-sandbox', '--disable-setuid-sandbox'])
    chrome_version = (await browser.version()).split('/')[-1]
    await browser.close()
    logger.info(f'retrieving device info from {url}')
    raw_devices = json.load(urlopen(url))
    device_payload = [x['device'] for x in raw_devices['extensions'] if x['type'] == 'emulated-device']
    devices = {}
    for payload in device_payload:
        pl_title = payload['title']
        names = [pl_title]
        if pl_title == 'iPhone 6/7/8':
            names = ['iPhone 6', 'iPhone 7', 'iPhone 8']
        if pl_title == 'iPhone 6/7/8 Plus':
            names = ['iPhone 6 Plus', 'iPhone 7 Plus', 'iPhone 8 Plus']
        if pl_title == 'iPhone 5/SE':
            names = ['iPhone 5', 'iPhone SE']

        for name in names:
            device = create_device(chrome_version, name, payload, False)
            device_l = create_device(chrome_version, name, payload, True)
            # check if landscape width or heights don't match non-landscape
            if any(True for key in ('height', 'width') if device_l['viewport'][key] != device['viewport'][key]):
                devices.update({device_l['name']: {k: v for k, v in device_l.items() if k != 'name'}})
            devices.update({device['name']: {k: v for k, v in device.items() if k != 'name'}})

    devices = {k: v for k, v in sorted(devices.items(), key=lambda t: t[0])}
    logger.info('writing output')
    with open(output_path, 'w') as out:
        out.write(
            dedent(
                f'''\
        # noqa
        # pragma: no cover
        from pyppeteer.models import Devices
        
        devices: Devices = {devices}
        '''
            )
        )


def fetch_devices(output_path: Path, url):
    return asyncio.get_event_loop().run_until_complete(_fetch_devices(output_path, url))


if __name__ == '__main__':
    parser = ArgumentParser(
        description='Fetch Chrome DevTools front-end emulation devices from given URL, '
        'convert them to puppeteer devices and save to the output_path'
    )
    parser.add_argument(
        '-o',
        '--output-path',
        type=str,
        help='Where to save the generated file',
        default='../pyppeteer/device_descriptors.py',
    )
    parser.add_argument(
        '-u',
        '--url',
        type=str,
        help='The URL to load devices descriptor from. '
        'If not set, devices will be fetched from the tip-of-tree of DevTools frontend.',
        default='https://raw.githubusercontent.com/ChromeDevTools/devtools-frontend/master/front_end/emulated_devices/module.json',
    )
    parsed = parser.parse_args()
    parsed.output_path = Path(parsed.output_path)
    fetch_devices(parsed.output_path, parsed.url)
