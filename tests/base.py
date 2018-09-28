#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

from syncer import sync

from pyppeteer import launch
from pyppeteer.util import get_free_port

from .server import get_application

DEFAULT_OPTIONS = {'args': ['--no-sandbox']}


class BaseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = get_free_port()
        cls.app = get_application()
        cls.server = cls.app.listen(cls.port)
        cls.browser = sync(launch(DEFAULT_OPTIONS))
        cls.url = 'http://localhost:{}/'.format(cls.port)

    @classmethod
    def tearDownClass(cls):
        sync(cls.browser.close())
        cls.server.stop()

    def setUp(self):
        self.context = sync(self.browser.createIncognitoBrowserContext())
        self.page = sync(self.context.newPage())
        self.result = False

    def tearDown(self):
        sync(self.context.close())
        self.context = None
        self.page = None

    def set_result(self, value):
        self.result = value
