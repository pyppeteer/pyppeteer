#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Chromium download module."""

import logging
import os
import shutil
import struct
import sys
from distutils.util import strtobool
from pathlib import Path
from typing import Union, List, Optional, Sequence
from urllib import request

import urllib3

from pyppeteer import __chromium_revision__, __pyppeteer_home__

try:
    from typing import TypedDict, Literal
except ImportError:
    from typing_extensions import TypedDict, Literal

logger = logging.getLogger(__name__)

DOWNLOADS_FOLDER = Path(__pyppeteer_home__) / 'local-chromium'

Platforms = Literal['linux', 'mac', 'win32', 'win64']


class RevisionInfo(TypedDict):
    folderPath: Union[Path, os.PathLike]
    executablePath: Union[Path, os.PathLike]
    url: str
    local: bool
    revision: str


class BrowserOptions(TypedDict, total=False):
    platform: Platforms
    path: Path
    host: str


DEFAULT_DOWNLOAD_HOST = 'https://storage.googleapis.com'
DOWNLOAD_HOST = os.environ.get(
    'PYPPETEER2_DOWNLOAD_HOST', DEFAULT_DOWNLOAD_HOST)

REVISION = os.environ.get('PYPPETEER2_CHROMIUM_REVISION', __chromium_revision__)

NO_PROGRESS_BAR = bool(strtobool(os.environ.get('PYPPETEER_NO_PROGRESS_BAR', '')))

chromiumExecutable = {
    'linux': DOWNLOADS_FOLDER / '{revision}' / 'chrome-linux' / 'chrome',
    'mac': (DOWNLOADS_FOLDER / REVISION / 'chrome-mac' / 'Chromium.app' /
            'Contents' / 'MacOS' / 'Chromium'),
    'win32': DOWNLOADS_FOLDER / REVISION / windowsArchive / 'chrome.exe',
    'win64': DOWNLOADS_FOLDER / REVISION / windowsArchive / 'chrome.exe',
}


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


def archive_name(platform: str, revision: str) -> str:
    if platform == 'linux':
        return 'chrome-linux'
    if platform == 'mac':
        return 'chrome-mac'
    if platform in ('win32', 'win64'):
        return 'chrome-win' if int(revision) > 591479 else 'chrome-win32'
    return None


def download_url(platform: Platforms, host: str, revision: str) -> str:
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


def parse_folder_path(folder_path: Path) -> Optional[Sequence[str]]:
    name = folder_path.name
    splits = name.split('-')
    if len(splits) != 2 or splits[0] not in Platforms.__args__:
        splits = (None, None)
    return splits


class BrowserFetcher:
    def __init__(self, project_root: Union[Path, os.PathLike], platform: str, path: Union[Path, os.PathLike] = None,
                 host: str = None):
        self.downloadsFolder = path or project_root.joinpath('.local-chromium')
        self.downloadHost = host or DEFAULT_DOWNLOAD_HOST
        self._platform = platform or sys.platform
        if self._platform == 'darwin':
            self._platform = 'mac'
        elif self._platform == 'win32':
            # no really good way to detect system bittedness
            self._platform = self._platform.replace('32', str(struct.calcsize('P') * 8))
        assert platform in Platforms.__args__, f'Unsupported platform: {platform}'

    @property
    def platform(self) -> str:
        return self._platform

    def canDownload(self, revision: str) -> bool:
        url = download_url(self._platform, self.downloadHost, revision)
        return request.urlopen(request.Request(url, method='HEAD')) == 200

    def download(self, revision: str, progress) -> RevisionInfo:
        url = download_url(self._platform, self.downloadHost, revision)
        zip_path = self.downloadsFolder.joinpath(f'download-{self._platform}-{revision}.zip')
        folder_path = self._get_folder_path(revision)
        if folder_path.exists():
            return self.revision_info(revision)
        os.makedirs(self.downloadsFolder, exist_ok=True)
        try:
            download_file(url, zip_path)
            extractZip(zip_path, folder_path)
        finally:
            if zip_path.exists():
                os.rmdir(zip_path)
        return self.revision_info(revision)

    def local_revisions(self) -> List[Path]:
        if not self.downloadsFolder.exists():
            return []
        result = []
        for file in [x for x in self.downloadsFolder.iterdir() if x.is_file()]:
            platform, revision = parse_folder_path(file)
            if platform != self._platform:
                continue
            result.append(revision)

    def remove(self, revision: str) -> None:
        f_path = self._get_folder_path(revision)
        assert f_path, f'Failed to remove: revision {revision} doesn\'t exist on the disk'
        shutil.rmtree(f_path)

    def revision_info(self, revision: str) -> RevisionInfo:
        folder_path = self._get_folder_path(revision)

        if self._platform == 'mac':
            executable_path = folder_path.joinpath(
                archive_name(self._platform, revision), 'Chromium.app',
                'Contents', 'MacOS', 'Chromium')
        elif self._platform == 'linux':
            executable_path = folder_path.joinpath(
                archive_name(self._platform, revision), 'chrome')
        elif self._platform in ('win32', 'win64'):
            executable_path = folder_path.joinpath(
                archive_name(self._platform, revision), 'chrome.exe')
        else:
            raise RuntimeError(f'Unsupported platform: {self._platform}')

        url = download_url(self._platform, self.host, revision)
        local = folder_path.exists()

        return {
            'revision': revision,
            'executablePath': executable_path,
            'folderPath': folder_path,
            'local': local,
            'url': url
        }

    def _get_folder_path(self, revision: str) -> Path:
        return self.downloadsFolder.joinpath(f'{self._platform}-{revision}')

    def can_download(self, revision: str) -> bool:
        url = download_url(self._platform, self.host, revision)
        http = urllib3.PoolManager()

        try:
            res = http.request('HEAD', url)
        except urllib3.exceptions.HTTPError as error:
            logger.error(error)
            return False

        return res.status == 200
