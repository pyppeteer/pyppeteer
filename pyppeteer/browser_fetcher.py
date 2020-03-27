#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Browser fetcher module.
Chromium is being downloaded from:
https://storage.googleapis.com/chromium-browser-snapshots
see full download instructions:
https://www.chromium.org/getting-involved/download-chromium
for latest version see:
https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2FLAST_CHANGE?alt=media
"""

import logging
import os
import shutil
import struct
import sys
from distutils.util import strtobool
from io import BytesIO
from pathlib import Path
from typing import Union, List, Optional, Tuple, cast, Sequence, Any
from urllib import request
from zipfile import ZipFile

import urllib3
from tqdm import tqdm

from pyppeteer import __chromium_revision__, __pyppeteer_home__
from pyppeteer.models import Platform, RevisionInfo

if sys.version_info < (3, 8):
    from typing_inspect import get_args
else:
    from typing import get_args

logger = logging.getLogger(__name__)

DEFAULT_DOWNLOAD_HOST = 'https://storage.googleapis.com'
DOWNLOAD_HOST = os.environ.get('PYPPETEER_DOWNLOAD_HOST', DEFAULT_DOWNLOAD_HOST)

NO_PROGRESS_BAR = bool(strtobool(os.environ.get('PYPPETEER_NO_PROGRESS_BAR', 'false')))


def get_archive_name(platform: Platform, revision: str) -> str:
    if platform == 'linux':
        return 'chrome-linux'
    if platform == 'mac':
        return 'chrome-mac'
    if platform in ('win32', 'win64'):
        return 'chrome-win' if int(revision) > 591479 else 'chrome-win32'
    raise ValueError(f'Unsupported platform argument: {platform}')


def download_url(platform: Platform, host: str, revision: str) -> str:
    windows_archive = 'chrome-win' if int(revision) > 591479 else 'chrome-win32'

    base_url = f'{host}/chromium-browser-snapshots'
    download_urls = {
        'linux': f'{base_url}/Linux_x64/{revision}/chrome-linux.zip',
        'mac': f'{base_url}/Mac/{revision}/chrome-mac.zip',
        'win32': f'{base_url}/Win/{revision}/{windows_archive}.zip',
        'win64': f'{base_url}/Win_x64/{revision}/{windows_archive}.zip',
    }

    return download_urls[platform]


def parse_folder_path(folder_path: Path) -> Tuple[Optional[str], Optional[str]]:
    name = folder_path.name
    splits: Sequence[Any] = name.split('-')
    if len(splits) != 2 or splits[0] not in get_args(Platform): # type: ignore
        splits = (None, None)
    return cast(Tuple[Optional[str], Optional[str]], tuple(splits))


def download_file(url: str, zip_path: BytesIO) -> None:
    CHUNK_SIZE = 4096
    file_req = request.urlopen(url)
    progress_bar = tqdm(
        total=int(file_req.getheader('Content-Length', 0)),
        unit_scale=True,
        file=os.devnull if NO_PROGRESS_BAR else None,
    )
    for chunk in iter(lambda: file_req.read(CHUNK_SIZE), b''):
        progress_bar.update(CHUNK_SIZE)
        zip_path.write(chunk)
    progress_bar.close()


def extractZip(zip_file: BytesIO, folder_path: Path) -> None:
    with ZipFile(zip_file) as zf:
        zf.extractall(folder_path)


class BrowserFetcher:
    def __init__(
        self, projectRoot: Union[Path, str] = None, platform: Platform = None, host: str = None,
    ):
        self.downloadsFolder = Path(projectRoot or __pyppeteer_home__) / 'local-chromium'
        self.downloadHost = host or DEFAULT_DOWNLOAD_HOST
        plat = platform or sys.platform  # type: ignore
        if plat == 'darwin':
            plat = 'mac'
        elif plat == 'win32':
            # no really good way to detect system bittedness
            # (other options depend on the python interpreter bittedness == sys.bittedness)
            plat = plat.replace('32', str(struct.calcsize('P') * 8))
        assert plat in get_args(Platform), f'Unsupported platform: {platform}' # type: ignore
        logger.info(f'platform auto detected: {plat}')
        self._platform = cast(Platform, plat)

    @property
    def platform(self) -> Platform:
        return self._platform

    def canDownload(self, revision: str) -> bool:
        url = download_url(self.platform, self.downloadHost, revision)
        return request.urlopen(request.Request(url, method='HEAD')) == 200

    def download(self, revision: Optional[str] = None) -> RevisionInfo:
        revision = revision or __chromium_revision__
        url = download_url(self.platform, self.downloadHost, revision)
        folder_path = self._get_folder_path(revision)
        if folder_path.exists():
            return self.revision_info(revision)
        os.makedirs(self.downloadsFolder, exist_ok=True)
        with BytesIO() as zip_file_obj:
            download_file(url, zip_file_obj)
            extractZip(zip_file_obj, folder_path)
        revision_info = self.revision_info(revision)
        if revision_info:
            os.chmod(revision_info['executablePath'], 0o755)
        return revision_info

    def local_revisions(self) -> List[Path]:
        if not self.downloadsFolder.exists():
            return []
        result = []
        for file in [x for x in self.downloadsFolder.iterdir() if x.is_dir()]:
            platform, revision = parse_folder_path(file)
            if platform != self._platform or not revision:
                continue
            result.append(Path(revision))
        return result

    def remove(self, revision: str) -> None:
        f_path = self._get_folder_path(revision)
        assert f_path.exists(), f'Failed to remove: revision {revision} doesn\'t exist on the disk'
        shutil.rmtree(f_path)

    def revision_info(self, revision: str) -> RevisionInfo:
        folder_path = self._get_folder_path(revision)

        archive_name = get_archive_name(self._platform, revision)
        if self._platform == 'mac':
            executable_path = folder_path / archive_name / 'Chromium.app' / 'Contents' / 'MacOS' / 'Chromium'
        elif self._platform == 'linux':
            executable_path = folder_path / archive_name / 'chrome'
        elif self._platform in ('win32', 'win64'):
            executable_path = folder_path / archive_name / 'chrome.exe'
        else:
            raise RuntimeError(f'Unsupported platform: {self._platform}')

        url = download_url(self._platform, self.downloadHost, revision)
        local = folder_path.exists()

        return {
            'revision': revision,
            'executablePath': executable_path,
            'folderPath': folder_path,
            'local': local,
            'url': url,
        }

    def _get_folder_path(self, revision: str) -> Path:
        return self.downloadsFolder.joinpath(f'{self._platform}-{revision}')

    def can_download(self, revision: str) -> bool:
        url = download_url(self._platform, self.downloadHost, revision)
        http = urllib3.PoolManager()

        try:
            res = http.request('HEAD', url)
        except urllib3.exceptions.HTTPError as error:
            logger.error(error)
            return False

        return res.status == 200
