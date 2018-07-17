#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'Chromium download module.'
from io import BytesIO
import logging
import os
from pathlib import Path
import stat
import sys
from zipfile import ZipFile
from collections import deque
try:
    # pip 10+
    from pip._vendor import urllib3
    from pip._internal.utils.ui import DownloadProgressProvider
except:
    # pip 9
    from pip._vendor.requests.packages import urllib3
    from pip.utils.ui import DownloadProgressBar

from pyppeteer import __chromimum_revision__, __pyppeteer_home__
logger = logging.getLogger(__name__)
DOWNLOADS_FOLDER = Path(__pyppeteer_home__) / 'local-chromium'
DEFAULT_DOWNLOAD_HOST = 'https://storage.googleapis.com'
DOWNLOAD_HOST = os.environ.get(
    'PYPPETEER_DOWNLOAD_HOST', DEFAULT_DOWNLOAD_HOST)
BASE_URL = f'{DOWNLOAD_HOST}/chromium-browser-snapshots'

REVISION = os.environ.get(
    'PYPPETEER_CHROMIUM_REVISION', __chromimum_revision__)

downloadURLs = {
    'linux': f'{BASE_URL}/Linux_x64/{REVISION}/chrome-linux.zip',
    'mac': f'{BASE_URL}/Mac/{REVISION}/chrome-mac.zip',
    'win32': f'{BASE_URL}/Win/{REVISION}/chrome-win32.zip',
    'win64': f'{BASE_URL}/Win_x64/{REVISION}/chrome-win32.zip',
}

chromiumExecutable = {
    'linux': DOWNLOADS_FOLDER / REVISION / 'chrome-linux' / 'chrome',
    'mac': (DOWNLOADS_FOLDER / REVISION / 'chrome-mac' / 'Chromium.app' /
            'Contents' / 'MacOS' / 'Chromium'),
    'win32': DOWNLOADS_FOLDER / REVISION / 'chrome-win32' / 'chrome.exe',
    'win64': DOWNLOADS_FOLDER / REVISION / 'chrome-win32' / 'chrome.exe',
}

def current_platform() -> str:
    'Get current platform name by short string.'
    if sys.platform.startswith('linux'):
        return 'linux'
    elif sys.platform.startswith('darwin'):
        return 'mac'
    elif (sys.platform.startswith('win') or sys.platform.startswith('msys') or sys.platform.startswith('cyg')):
        if (sys.maxsize > ((2 ** 31) - 1)):
            return 'win64'
        return 'win32'
    raise OSError(('Unsupported platform: ' + sys.platform))


def get_url() -> str:
    'Get chromium download url.'
    return downloadURLs[current_platform()]


def download_zip(url: str) -> urllib3.response.HTTPResponse:
    'Download data from url.'
    logger.warning(
        'start chromium download.\nDownload may take a few minutes.')

    urllib3.disable_warnings()
    http = urllib3.PoolManager()
    data = http.request('GET', 
        url, 
        preload_content=False)
    logger.warning('chromium download done.')
    return data


def extract_zip(data: urllib3.response.HTTPResponse, path: Path) -> None:
    'Extract zipped data to path.'

    try:
        totle_size = int(data.headers['content-length'])
    except:
        totle_size = 0
    try:
        process = DownloadProgressProvider('on', totle_size)
    except:
        process = DownloadProgressBar(max=totle_size).iter

    _data = BytesIO()

    def consume(iterator):
        # consume an iterator at C speed.
        # maxlen is 0 will return deque([])
        # we just need to consume it.
        return deque(iterator, maxlen=0)
          
    def resp_read(r, chunk_size):
        try:
            for chunk in r.stream(chunk_size):
                yield chunk
        except AttributeError:
            while True:
                chunk = resp.raw.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    def written_chunk(chunks, zip_path='/temp.tmp'):
        nonlocal data

        if (current_platform() == 'mac'):
            with open(zip_path, 'wb') as content_file:
                for chunk in chunks:
                    content_file.write(chunk)

                    # consume it!
                    yield chunk
        else:
            for chunk in chunks:
                _data.write(chunk)

                yield chunk

    if (current_platform() == 'mac'):
        import subprocess
        import shutil
        zip_path = (path / 'chrome.zip')
        if (not path.exists()):
            path.mkdir(parents=True)
        consume(written_chunk(process(resp_read(data, 10240), 10240), zip_path))
        if (not shutil.which('unzip')):
            raise OSError(''.join(
                ['Failed to automatically extract chrome.zip.Please unzip ', '{}'.format(zip_path), ' manually.']))
        subprocess.run(['unzip', str(zip_path)], cwd=str(path))
        if (chromium_excutable().exists() and zip_path.exists()):
            zip_path.unlink()
    else:
        consume(written_chunk(process(resp_read(data, 10240), 10240)))
        with ZipFile(_data) as zf:
            zf.extractall(str(path))
    exec_path = chromium_excutable()
    if (not exec_path.exists()):
        raise IOError('Failed to extract chromium.')
    exec_path.chmod(
        (((exec_path.stat().st_mode | stat.S_IXOTH) | stat.S_IXGRP) | stat.S_IXUSR))
    logger.warning(''.join(['chromium extracted to: ', '{}'.format(path)]))


def download_chromium() -> None:
    'Downlaod and extract chrmoium.'
    extract_zip(download_zip(get_url()), (DOWNLOADS_FOLDER / REVISION))


def chromium_excutable() -> Path:
    'Get path of the chromium executable.'
    return chromiumExecutable[current_platform()]


def check_chromium() -> bool:
    'Check if chromium is placed at correct path.'
    return chromium_excutable().exists()
