#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Chromium dowload module."""

from io import BytesIO
import logging
import os
from pathlib import Path
import stat
import sys
from urllib import request
from zipfile import ZipFile

from pyppeteer import __chromimum_revision__ as REVISION

logger = logging.getLogger(__name__)
DOWNLOADS_FOLDER = Path.home() / '.pyppeteer' / 'local-chromium'
DEFAULT_DOWNLOAD_HOST = 'https://storage.googleapis.com'
DOWNLOAD_HOST = os.environ.get(
    'PYPPETEER_DOWNLOAD_HOST', DEFAULT_DOWNLOAD_HOST)
BASE_URL = f'{DOWNLOAD_HOST}/chromium-browser-snapshots'

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


def curret_platform() -> str:
    """Get current platform name by short string."""
    if sys.platform.startswith('linux'):
        return 'linux'
    elif sys.platform.startswith('darwin'):
        return 'mac'
    elif sys.platform.startswith('win'):
        if sys.maxsize > 2 ** 31 - 1:
            return 'win64'
        return 'win32'
    raise OSError('Unsupported platform: ' + sys.platform)


def get_url() -> str:
    """Get chromium download url."""
    return downloadURLs[curret_platform()]


def download_zip(url: str) -> bytes:
    """Download data from url."""
    logger.warning('start chromium download.\n'
                   'Download may take a few minutes.')
    with request.urlopen(url) as f:
        data = f.read()
    logger.warning('chromium download done.')
    return data


def extract_zip(data: bytes, path: Path) -> None:
    """Extract zipped data to path."""
    # On mac zipfile module cannot extract correctly, so use unzip instead.
    if curret_platform() == 'mac':
        import subprocess
        import shutil
        zip_path = path / 'chrome.zip'
        if not path.exists():
            path.mkdir(parents=True)
        with zip_path.open('wb') as f:
            f.write(data)
        if not shutil.which('unzip'):
            raise OSError('Failed to automatically extract chrome.zip.'
                          f'Please unzip {zip_path} manually.')
        subprocess.run(['unzip', str(zip_path)], cwd=str(path))
        if chromium_excutable().exists() and zip_path.exists():
            zip_path.unlink()
    else:
        with ZipFile(BytesIO(data)) as zf:
            zf.extractall(str(path))
    exec_path = chromium_excutable()
    if not exec_path.exists():
        raise IOError('Failed to extract chromium.')
    exec_path.chmod(exec_path.stat().st_mode | stat.S_IXOTH | stat.S_IXGRP |
                    stat.S_IXUSR)
    logger.warning(f'chromium extracted to: {path}')


def download_chromium() -> None:
    """Downlaod and extract chrmoium."""
    extract_zip(download_zip(get_url()), DOWNLOADS_FOLDER / REVISION)


def chromium_excutable() -> Path:
    """Get path of the chromium executable."""
    return chromiumExecutable[curret_platform()]


def check_chromium() -> bool:
    """Check if chromium is placed at correct path."""
    return chromium_excutable().exists()
