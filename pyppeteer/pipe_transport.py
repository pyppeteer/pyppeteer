import logging
from typing import Callable, Optional

from pyppeteer import helpers

logger = logging.getLogger(__name__)


class PipeTransport:
    def __init__(
        self, pipeWrite, pipeRead,
    ):
        self._pipeWrite = pipeWrite
        self._pendingMessage = ''
        self.onmessage: Optional[Callable[[Optional[str], str], None]] = None
        self.onclose: Optional[Callable[[], None]] = None

        def _onclose() -> None:
            if self.onclose:
                self.onclose()

        self._eventListeners = [
            helpers.addEventListener(pipeRead, 'data', lambda buffer: self._dispatch(buffer)),
            helpers.addEventListener(pipeRead, 'close', _onclose),
            helpers.addEventListener(
                pipeRead, 'error', lambda e: logger.error(f'An exception occurred on pipe read: {e}')
            ),
            helpers.addEventListener(
                pipeWrite, 'error', lambda e: logger.error(f'An exception occurred on pipe read: {e}')
            ),
        ]

    def send(self, message: str) -> None:
        self._pipeWrite.write(message)
        self._pipeWrite.write('\0')

    def _dispatch(self, buffer: str) -> None:
        end = buffer.find('\0')  # -1 means nothing found
        if end == -1:
            self._pendingMessage += buffer
            return

        message = self._pendingMessage + buffer
        if message and self.onmessage:
            self.onmessage(None, message)

        start = end + 1
        end = buffer.find('\0', start)
        while end != -1:
            if self.onmessage:
                self.onmessage(None, buffer)
            start = end + 1
            end = buffer.find('\0', start)

        self._pendingMessage = buffer

    def close(self) -> None:
        self._pipeWrite = None
        helpers.removeEventListeners(self._eventListeners)
