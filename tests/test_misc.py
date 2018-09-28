#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import unittest

import pyppeteer
from pyppeteer.helper import debugError, get_positive_int
from pyppeteer.page import convertPrintParameterToInches


class TestVersion(unittest.TestCase):
    def test_version(self):
        version = pyppeteer.version
        self.assertTrue(isinstance(version, str))
        self.assertEqual(version.count('.'), 2)

    def test_version_info(self):
        vinfo = pyppeteer.version_info
        self.assertEqual(len(vinfo), 3)
        for i in vinfo:
            self.assertTrue(isinstance(i, int))


class TestDefaultArgs(unittest.TestCase):
    def test_default_args(self):
        self.assertIn('--no-first-run', pyppeteer.defaultArgs())
        self.assertIn('--headless', pyppeteer.defaultArgs())
        self.assertNotIn('--headless', pyppeteer.defaultArgs({'headless': False}))  # noqa: E501
        self.assertIn('--user-data-dir=foo', pyppeteer.defaultArgs(userDataDir='foo'))  # noqa: E501


class TestToInches(unittest.TestCase):
    def test_px(self):
        self.assertEqual(
            convertPrintParameterToInches('12px'),
            12.0 / 96,
        )

    def test_inch(self):
        self.assertAlmostEqual(
            convertPrintParameterToInches('12in'),
            12.0,
        )

    def test_cm(self):
        self.assertAlmostEqual(
            convertPrintParameterToInches('12cm'),
            12.0 * 37.8 / 96,
        )

    def test_mm(self):
        self.assertAlmostEqual(
            convertPrintParameterToInches('12mm'),
            12.0 * 3.78 / 96,
        )


class TestPositiveInt(unittest.TestCase):
    def test_badtype(self):
        with self.assertRaises(TypeError):
            get_positive_int({'a': 'b'}, 'a')

    def test_negative_int(self):
        with self.assertRaises(ValueError):
            get_positive_int({'a': -1}, 'a')


class TestDebugError(unittest.TestCase):
    def setUp(self):
        self._old_debug = pyppeteer.DEBUG
        self.logger = logging.getLogger('pyppeteer.test')

    def tearDown(self):
        pyppeteer.DEBUG = self._old_debug

    def test_debug_default(self):
        with self.assertLogs('pyppeteer.test', logging.DEBUG):
            debugError(self.logger, 'test')
        with self.assertRaises(AssertionError):
            with self.assertLogs('pyppeteer', logging.INFO):
                debugError(self.logger, 'test')

    def test_debug_enabled(self):
        pyppeteer.DEBUG = True
        with self.assertLogs('pyppeteer.test', logging.ERROR):
            debugError(self.logger, 'test')

    def test_debug_enable_disable(self):
        pyppeteer.DEBUG = True
        with self.assertLogs('pyppeteer.test', logging.ERROR):
            debugError(self.logger, 'test')
        pyppeteer.DEBUG = False
        with self.assertLogs('pyppeteer.test', logging.DEBUG):
            debugError(self.logger, 'test')
        with self.assertRaises(AssertionError):
            with self.assertLogs('pyppeteer.test', logging.INFO):
                debugError(self.logger, 'test')

    def test_debug_logger(self):
        with self.assertRaises(AssertionError):
            with self.assertLogs('pyppeteer', logging.DEBUG):
                debugError(logging.getLogger('test'), 'test message')
