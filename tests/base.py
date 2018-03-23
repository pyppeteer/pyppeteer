#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import unittest

from syncer import sync

from pyppeteer import launch
from pyppeteer.util import get_free_port

from server import get_application

DEFAULT_OPTIONS = {'args': ['--no-sandbox']}


class BaseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = get_free_port()
        time.sleep(0.1)
        cls.app = get_application()
        cls.server = cls.app.listen(cls.port)
        cls.browser = sync(launch(DEFAULT_OPTIONS))
        cls.url = 'http://localhost:{}/'.format(cls.port)

    @classmethod
    def tearDownClass(cls):
        sync(cls.browser.close())
        cls.server.stop()

    def setUp(self):
        self.page = sync(self.browser.newPage())
        sync(self.page.goto(self.url))

    def tearDown(self):
        sync(self.page.close())
