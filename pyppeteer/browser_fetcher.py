#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Chromium download module."""

from io import BytesIO
from typing import Union, TypedDict
import logging
import os
from pathlib import Path
import stat
import sys
from zipfile import ZipFile

import urllib3
from tqdm import tqdm

from pyppeteer import __chromium_revision__, __pyppeteer_home__

logger = logging.getLogger(__name__)

DOWNLOADS_FOLDER = Path(__pyppeteer_home__) / 'local-chromium'
DEFAULT_DOWNLOAD_HOST = 'https://storage.googleapis.com'
DOWNLOAD_HOST = os.environ.get(
    'PYPPETEER_DOWNLOAD_HOST', DEFAULT_DOWNLOAD_HOST)

REVISION = os.environ.get(
    'PYPPETEER_CHROMIUM_REVISION', __chromium_revision__)

NO_PROGRESS_BAR = os.environ.get('PYPPETEER_NO_PROGRESS_BAR', '')
if NO_PROGRESS_BAR.lower() in ('1', 'true'):
    NO_PROGRESS_BAR = True  # type: ignore

# Windows archive name changed at r591479.


# chromiumExecutable = {
#     'linux': DOWNLOADS_FOLDER / REVISION / 'chrome-linux' / 'chrome',
#     'mac': (DOWNLOADS_FOLDER / REVISION / 'chrome-mac' / 'Chromium.app' /
#             'Contents' / 'MacOS' / 'Chromium'),
#     'win32': DOWNLOADS_FOLDER / REVISION / windowsArchive / 'chrome.exe',
#     'win64': DOWNLOADS_FOLDER / REVISION / windowsArchive / 'chrome.exe',
# }


class RevisionInfo(TypedDict):
    folderPath: Union[Path, os.PathLike[str]]
    executablePath: Union[Path, os.PathLike[str]]
    url: str
    local: bool
    revision: str


def current_platform() -> str:
    """Get current platform name by short string."""
    if sys.platform.startswith('linux'):
        return 'linux'
    elif sys.platform.startswith('darwin'):
        return 'mac'
    elif (sys.platform.startswith('win') or
          sys.platform.startswith('msys') or
          sys.platform.startswith('cyg')):
        if sys.maxsize > 2 ** 31 - 1:
            return 'win64'
        return 'win32'
    raise OSError('Unsupported platform: ' + sys.platform)


def download_url(platform: str, host: str, revision: str) -> str:
    windows_archive = 'chrome-win' if int(revision) > 591479 \
        else 'chrome-win32'

    base_url = f'{host}/chromium-browser-snapshots'
    download_urls = {
        'linux': f'{base_url}/Linux_x64/{revision}/chrome-linux.zip',
        'mac': f'{base_url}/Mac/{revision}/chrome-mac.zip',
        'win32': f'{base_url}/Win/{revision}/{windows_archive}.zip',
        'win64': f'{base_url}/Win_x64/{revision}/{windows_archive}.zip',
    }

    return download_urls[platform]


def archive_name(platform: str, revision: str) -> str:
    if platform == 'linux':
        return 'chrome-linux'
    if platform == 'mac':
        return 'chrome-mac'
    if platform == 'win32' or platform == 'win64':
        return 'chrome-win' if int(revision) > 591479 else 'chrome-win32'


class BrowserFetcher:
    def __init__(self, project_root: Union[Path, os.PathLike[str]],
                 platform: str, path: Union[Path, os.PathLike[str]],
                 host: str):

        if path is None:
            self.path = project_root.joinpath(project_root, '.local_chromium')
        else:
            self.path = path

        if host is None:
            self.host = DOWNLOAD_HOST
        else:
            self.host = host

        if platform is None:
            self.platform = current_platform()
        else:
            self.platform = platform

    # def download(self, revision: str) -> RevisionInfo:
    #     url = download_url(self.platform, self.host, revision)
    #     folder_path = self.get_folder_path(revision)
    #     zip_path = self.path.joinpath(f'download-{folder_path}.zip')

    #     if folder_path.exists():
    #         return self.revision_info(revision)

    def revision_info(self, revision: str) -> RevisionInfo:
        folder_path = self.get_folder_path(revision)

        if self.platform == 'mac':
            executable_path = folder_path.joinpath(
                archive_name(self.platform, revision), 'Chromium.app',
                'Contents', 'MacOS', 'Chromium')

        if self.platform == 'linux':
            executable_path = folder_path.joinpath(
                archive_name(self.platform, revision), 'chrome')

        if self.platform == 'win32' or self.platform == 'win64':
            executable_path = folder_path.joinpath(
                archive_name(self.platform, revision), 'chrome.exe')

        url = download_url(self.platform, self.host, revision)
        local = folder_path.exists()

        return {
            'revision': revision,
            'executablePath': executable_path,
            'folderPath': folder_path,
            'local': local,
            'url': url
        }

    def get_folder_path(self, revision: str) -> Path:
        return self.path.joinpath(f'{self.platform}-{revision}')

    def can_download(self, revision: str) -> bool:
        url = download_url(self.platform, self.host, revision)
        http = urllib3.PoolManager()

        try:
            res = http.request('HEAD', url)
        except urllib3.exceptions.HTTPError as error:
            logger.error(error)
            return False

        return res.status == 200
