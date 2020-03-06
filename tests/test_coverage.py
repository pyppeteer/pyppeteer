#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from syncer import sync

from .base import BaseTestCase


class TestJSCoverage(BaseTestCase):
    @sync
    async def test_js_coverage(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(
            self.url + 'static/jscoverage/simple.html',
            waitUntil='networkidle0',
        )
        coverage = await self.page.coverage.stopJSCoverage()
        assert len(coverage) == 1
        assert '/jscoverage/simple.html' in coverage[0]['url']
        assert coverage[0]['ranges'] == [
            {'start': 0, 'end': 17},
            {'start': 35, 'end': 61},
        ]

    @sync
    async def test_js_coverage_source_url(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(self.url + 'static/jscoverage/sourceurl.html')
        coverage = await self.page.coverage.stopJSCoverage()
        assert len(coverage) == 1
        assert coverage[0]['url'] == 'nicename.js'

    @sync
    async def test_js_coverage_ignore_empty(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(self.url + 'empty')
        coverage = await self.page.coverage.stopJSCoverage()
        assert coverage == []

    @sync
    async def test_ignore_eval_script_by_default(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(self.url + 'static/jscoverage/eval.html')
        coverage = await self.page.coverage.stopJSCoverage()
        assert len(coverage) == 1

    @sync
    async def test_not_ignore_eval_script_with_reportAnonymousScript(self):
        await self.page.coverage.startJSCoverage(reportAnonymousScript=True)
        await self.page.goto(self.url + 'static/jscoverage/eval.html')
        coverage = await self.page.coverage.stopJSCoverage()
        assert any(entry for entry in coverage
                            if entry['url'].startswith('debugger://'))
        assert len(coverage) == 2

    @sync
    async def test_ignore_injected_script(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(self.url + 'empty')
        await self.page.evaluate('console.log("foo")')
        await self.page.evaluate('() => console.log("bar")')
        coverage = await self.page.coverage.stopJSCoverage()
        assert len(coverage) == 0

    @sync
    async def test_ignore_injected_script_with_reportAnonymousScript(self):
        await self.page.coverage.startJSCoverage(reportAnonymousScript=True)
        await self.page.goto(self.url + 'empty')
        await self.page.evaluate('console.log("foo")')
        await self.page.evaluate('() => console.log("bar")')
        coverage = await self.page.coverage.stopJSCoverage()
        assert len(coverage) == 0

    @sync
    async def test_js_coverage_multiple_script(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(self.url + 'static/jscoverage/multiple.html')
        coverage = await self.page.coverage.stopJSCoverage()
        assert len(coverage) == 2
        coverage.sort(key=lambda cov: cov['url'])
        assert '/jscoverage/script1.js' in coverage[0]['url']
        assert '/jscoverage/script2.js' in coverage[1]['url']

    @sync
    async def test_js_coverage_ranges(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(self.url + 'static/jscoverage/ranges.html')
        coverage = await self.page.coverage.stopJSCoverage()
        assert len(coverage) == 1
        entry = coverage[0]
        assert len(entry['ranges']) == 1
        range = entry['ranges'][0]
        assert entry['text'][range['start']:range['end']] ==
            'console.log(\'used!\');'

    @sync
    async def test_no_coverage(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(self.url + 'static/jscoverage/unused.html')
        coverage = await self.page.coverage.stopJSCoverage()
        assert len(coverage) == 1
        entry = coverage[0]
        assert 'static/jscoverage/unused.html' in entry['url']
        assert len(entry['ranges']) == 0

    @sync
    async def test_js_coverage_condition(self):
        await self.page.coverage.startJSCoverage()
        await self.page.goto(self.url + 'static/jscoverage/involved.html')
        coverage = await self.page.coverage.stopJSCoverage()
        expected_range = [
            {'start': 0, 'end': 35},
            {'start': 50, 'end': 100},
            {'start': 107, 'end': 141},
            {'start': 148, 'end': 160},
            {'start': 168, 'end': 207},
        ]
        assert coverage[0]['ranges'] == expected_range

    @sync
    async def test_js_coverage_no_reset_navigation(self):
        await self.page.coverage.startJSCoverage(resetOnNavigation=False)
        await self.page.goto(self.url + 'static/jscoverage/multiple.html')
        await self.page.goto(self.url + 'empty')
        coverage = await self.page.coverage.stopJSCoverage()
        assert len(coverage) == 2

    @sync
    async def test_js_coverage_reset_navigation(self):
        await self.page.coverage.startJSCoverage()  # enabled by default
        await self.page.goto(self.url + 'static/jscoverage/multiple.html')
        await self.page.goto(self.url + 'empty')
        coverage = await self.page.coverage.stopJSCoverage()
        assert len(coverage) == 0


class TestCSSCoverage(BaseTestCase):
    @sync
    async def test_css_coverage(self):
        await self.page.coverage.startCSSCoverage()
        await self.page.goto(self.url + 'static/csscoverage/simple.html')
        coverage = await self.page.coverage.stopCSSCoverage()
        assert len(coverage) == 1
        assert '/csscoverage/simple.html' in coverage[0]['url']
        assert coverage[0]['ranges'] == [{'start': 1, 'end': 22}]
        range = coverage[0]['ranges'][0]
        assert coverage[0]['text'][range['start']:range['end']] ==
            'div { color: green; }'

    @sync
    async def test_css_coverage_url(self):
        await self.page.coverage.startCSSCoverage()
        await self.page.goto(self.url + 'static/csscoverage/sourceurl.html')
        coverage = await self.page.coverage.stopCSSCoverage()
        assert len(coverage) == 1
        assert coverage[0]['url'] == 'nicename.css'

    @sync
    async def test_css_coverage_multiple(self):
        await self.page.coverage.startCSSCoverage()
        await self.page.goto(self.url + 'static/csscoverage/multiple.html')
        coverage = await self.page.coverage.stopCSSCoverage()
        assert len(coverage) == 2
        coverage.sort(key=lambda cov: cov['url'])
        assert '/csscoverage/stylesheet1.css' in coverage[0]['url']
        assert '/csscoverage/stylesheet2.css' in coverage[1]['url']

    @sync
    async def test_css_coverage_no_coverage(self):
        await self.page.coverage.startCSSCoverage()
        await self.page.goto(self.url + 'static/csscoverage/unused.html')
        coverage = await self.page.coverage.stopCSSCoverage()
        assert len(coverage) == 1
        assert coverage[0]['url'] == 'unused.css'
        assert coverage[0]['ranges'] == []

    @sync
    async def test_css_coverage_media(self):
        await self.page.coverage.startCSSCoverage()
        await self.page.goto(self.url + 'static/csscoverage/media.html')
        coverage = await self.page.coverage.stopCSSCoverage()
        assert len(coverage) == 1
        assert '/csscoverage/media.html' in coverage[0]['url']
        assert coverage[0]['ranges'] == [{'start': 17, 'end': 38}]

    @sync
    async def test_css_coverage_complicated(self):
        await self.page.coverage.startCSSCoverage()
        await self.page.goto(self.url + 'static/csscoverage/involved.html')
        coverage = await self.page.coverage.stopCSSCoverage()
        assert len(coverage) == 1
        range = coverage[0]['ranges']
        assert range == [
            {'start': 20, 'end': 168},
            {'start': 198, 'end': 304},
        ]

    @sync
    async def test_css_ignore_injected_css(self):
        await self.page.goto(self.url + 'empty')
        await self.page.coverage.startCSSCoverage()
        await self.page.addStyleTag(content='body { margin: 10px; }')
        # trigger style recalc
        margin = await self.page.evaluate(
            '() => window.getComputedStyle(document.body).margin')
        assert margin == '10px'
        coverage = await self.page.coverage.stopCSSCoverage()
        assert coverage == []

    @sync
    async def test_css_coverage_no_reset_navigation(self):
        await self.page.coverage.startCSSCoverage(resetOnNavigation=False)
        await self.page.goto(self.url + 'static/csscoverage/multiple.html')
        await self.page.goto(self.url + 'empty')
        coverage = await self.page.coverage.stopCSSCoverage()
        assert len(coverage) == 2

    @sync
    async def test_css_coverage_reset_navigation(self):
        await self.page.coverage.startCSSCoverage()  # enabled by default
        await self.page.goto(self.url + 'static/csscoverage/multiple.html')
        await self.page.goto(self.url + 'empty')
        coverage = await self.page.coverage.stopCSSCoverage()
        assert len(coverage) == 0
