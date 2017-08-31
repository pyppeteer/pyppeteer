#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

from pyppeteer.page import convertPrintParameterToInches


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
