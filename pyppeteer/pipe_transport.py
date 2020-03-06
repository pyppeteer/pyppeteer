from typing import Callable

from pyppeteer import helper
from pyppeteer.helper import debugError


class PipeTransport:

    def __init__(
            self,
            pipeWrite,
            pipeRead,
    ):
        self._pipeWrite = pipeWrite
        self._pendingMessage = ''
        # TODO maybe it would make sense to have these default to empty lambdas?
        self.onmessage: Callable[[str, str], None] = None
        self.onclose:Callable[[], None] = None

        def _onclose():
            if self.onclose:
                self.onclose()

        self._eventListeners = [
            helper.addEventListener(
                pipeRead, 'data',
                lambda buffer: self._dispatch(buffer)
            ),
            helper.addEventListener(pipeRead, 'close', _onclose),
            helper.addEventListener(pipeRead, 'error', debugError)
            helper.addEventListener(pipeWrite, 'error', debugError)
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
        if self.onmessage:
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
        helper.removeEventListeners(self._eventListeners)

