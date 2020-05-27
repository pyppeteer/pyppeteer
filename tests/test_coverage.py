#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from syncer import sync


class TestJSCoverage:
    @sync
    async def test_basic_usage(self, isolated_page, server):
        await isolated_page.coverage.startJSCoverage()
        await isolated_page.goto(server / 'jscoverage/simple.html', waitUntil='networkidle0',)
        coverage = await isolated_page.coverage.stopJSCoverage()
        assert len(coverage) == 1
        assert '/jscoverage/simple.html' in coverage[0]['url']
        assert coverage[0]['ranges'] == [
            {'start': 0, 'end': 17},
            {'start': 35, 'end': 61},
        ]

    @sync
    async def test_reports_source_url(self, isolated_page, server):
        await isolated_page.coverage.startJSCoverage()
        await isolated_page.goto(server / 'jscoverage/sourceurl.html')
        coverage = await isolated_page.coverage.stopJSCoverage()
        assert len(coverage) == 1
        assert coverage[0]['url'] == 'nicename.js'

    @sync
    async def test_ignore_eval_script_by_default(self, isolated_page, server):
        await isolated_page.coverage.startJSCoverage()
        await isolated_page.goto(server / 'jscoverage/eval.html')
        coverage = await isolated_page.coverage.stopJSCoverage()
        assert len(coverage) == 1

    @sync
    async def test_does_not_ignore_eval_script_with_reportAnonymousScript(self, isolated_page, server):
        await isolated_page.coverage.startJSCoverage(reportAnonymousScripts=True)
        await isolated_page.goto(server / 'jscoverage/eval.html')
        coverage = await isolated_page.coverage.stopJSCoverage()
        assert any(True for entry in coverage if entry['url'].startswith('debugger://'))
        assert len(coverage) == 2

    @sync
    async def test_ignores_pptr_internally_injected_script(self, isolated_page, server):
        await isolated_page.coverage.startJSCoverage()
        await isolated_page.goto(server.empty_page)
        await isolated_page.evaluate('console.log("foo")')
        await isolated_page.evaluate('() => console.log("bar")')
        coverage = await isolated_page.coverage.stopJSCoverage()
        assert len(coverage) == 0

    @sync
    async def test_ignore_injected_script_with_reportAnonymousScript(self, isolated_page, server):
        await isolated_page.coverage.startJSCoverage(reportAnonymousScripts=True)
        await isolated_page.goto(server.empty_page)
        await isolated_page.evaluate('console.log("foo")')
        await isolated_page.evaluate('() => console.log("bar")')
        coverage = await isolated_page.coverage.stopJSCoverage()
        assert len(coverage) == 0

    @sync
    async def test_reports_multiple_script(self, isolated_page, server):
        await isolated_page.coverage.startJSCoverage()
        await isolated_page.goto(server / 'jscoverage/multiple.html')
        coverage = await isolated_page.coverage.stopJSCoverage()
        assert len(coverage) == 2
        coverage.sort(key=lambda cov: cov['url'])
        assert '/jscoverage/script1.js' in coverage[0]['url']
        assert '/jscoverage/script2.js' in coverage[1]['url']

    @sync
    async def test_reports_ranges(self, isolated_page, server):
        await isolated_page.coverage.startJSCoverage()
        await isolated_page.goto(server / 'jscoverage/ranges.html')
        coverage = await isolated_page.coverage.stopJSCoverage()
        assert len(coverage) == 1
        entry = coverage[0]
        assert len(entry['ranges']) == 1
        range_ = entry['ranges'][0]
        assert entry['text'][range_['start']:range_['end']] == 'console.log(\'used!\');'

    @sync
    async def test_reports_scripts_with_no_coverage(self, isolated_page, server):
        await isolated_page.coverage.startJSCoverage()
        await isolated_page.goto(server / 'jscoverage/unused.html')
        coverage = await isolated_page.coverage.stopJSCoverage()
        assert len(coverage) == 1
        entry = coverage[0]
        assert '/jscoverage/unused.html' in entry['url']
        assert len(entry['ranges']) == 0

    @sync
    async def test_works_with_conditionals(self, isolated_page, server):
        await isolated_page.coverage.startJSCoverage()
        await isolated_page.goto(server / 'jscoverage/involved.html')
        coverage = await isolated_page.coverage.stopJSCoverage()
        expected_range = [
            {'start': 0, 'end': 35},
            {'start': 50, 'end': 100},
            {'start': 107, 'end': 141},
            {'start': 148, 'end': 160},
            {'start': 168, 'end': 207},
        ]
        assert coverage[0]['ranges'] == expected_range

    class TestResetOnNavigationDisabled:
        @sync
        async def test_reports_scripts_across_navigations_when_disabled(self, isolated_page, server):
            await isolated_page.coverage.startJSCoverage(resetOnNavigation=False)
            await isolated_page.goto(server / 'jscoverage/multiple.html')
            await isolated_page.goto(server.empty_page)
            coverage = await isolated_page.coverage.stopJSCoverage()
            assert len(coverage) == 2

        @sync
        async def test_does_not_report_scripts_across_navigations_when_enabled(self, isolated_page, server):
            await isolated_page.coverage.startJSCoverage()  # enabled by default
            await isolated_page.goto(server / 'jscoverage/multiple.html')
            await isolated_page.goto(server.empty_page)
            coverage = await isolated_page.coverage.stopJSCoverage()
            assert len(coverage) == 0


class TestCSSCoverage:
    @sync
    async def test_basic_usage(self, isolated_page, server):
        await isolated_page.coverage.startCSSCoverage()
        await isolated_page.goto(server / 'csscoverage/simple.html')
        coverage = await isolated_page.coverage.stopCSSCoverage()
        assert len(coverage) == 1
        assert '/csscoverage/simple.html' in coverage[0]['url']
        assert coverage[0]['ranges'] == [{'start': 1, 'end': 22}]
        range = coverage[0]['ranges'][0]
        assert coverage[0]['text'][range['start'] : range['end']] == 'div { color: green; }'

    @sync
    async def test_reports_sourceURLs(self, isolated_page, server):
        await isolated_page.coverage.startCSSCoverage()
        await isolated_page.goto(server / 'csscoverage/sourceurl.html')
        coverage = await isolated_page.coverage.stopCSSCoverage()
        assert len(coverage) == 1
        assert coverage[0]['url'] == 'nicename.css'

    @sync
    async def test_reports_multiple_stylesheets(self, isolated_page, server):
        await isolated_page.coverage.startCSSCoverage()
        await isolated_page.goto(server / 'csscoverage/multiple.html')
        coverage = await isolated_page.coverage.stopCSSCoverage()
        assert len(coverage) == 2
        coverage.sort(key=lambda cov: cov['url'])
        assert '/csscoverage/stylesheet1.css' in coverage[0]['url']
        assert '/csscoverage/stylesheet2.css' in coverage[1]['url']

    @sync
    async def test_reports_stylesheets_with_no_coverage(self, isolated_page, server):
        await isolated_page.coverage.startCSSCoverage()
        await isolated_page.goto(server / 'csscoverage/unused.html')
        coverage = await isolated_page.coverage.stopCSSCoverage()
        assert len(coverage) == 1
        assert coverage[0]['url'] == 'unused.css'
        assert coverage[0]['ranges'] == []

    @sync
    async def test_works_with_media_queries(self, isolated_page, server):
        await isolated_page.coverage.startCSSCoverage()
        await isolated_page.goto(server / 'csscoverage/media.html')
        coverage = await isolated_page.coverage.stopCSSCoverage()
        assert len(coverage) == 1
        assert '/csscoverage/media.html' in coverage[0]['url']
        assert coverage[0]['ranges'] == [{'start': 17, 'end': 38}]

    @sync
    async def test_works_with_complicated_use_cases(self, isolated_page, server):
        await isolated_page.coverage.startCSSCoverage()
        await isolated_page.goto(server / 'csscoverage/involved.html')
        coverage = await isolated_page.coverage.stopCSSCoverage()
        assert len(coverage) == 1
        range_ = coverage[0]['ranges']
        assert range_ == [{'end': 297, 'start': 149}, {'end': 433, 'start': 327}]

    @sync
    async def test_ignores_ignore_injected_stylesheets(self, isolated_page, server):
        await isolated_page.goto(server.empty_page)
        await isolated_page.coverage.startCSSCoverage()
        await isolated_page.addStyleTag(content='body { margin: 10px; }')
        # trigger style recalculation
        margin = await isolated_page.evaluate('() => window.getComputedStyle(document.body).margin')
        assert margin == '10px'
        coverage = await isolated_page.coverage.stopCSSCoverage()
        assert coverage == []

    @sync
    async def test_works_with_recently_loaded_stylesheet(self, isolated_page, server):
        await isolated_page.coverage.startCSSCoverage()
        await isolated_page.evaluate('''async url => {
            document.body.textContent = 'hello, world';
    
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = url;
            document.head.appendChild(link);
            await new Promise(x => link.onload = x);
        }''', server / 'csscoverage/stylesheet1.css')
        coverage = await isolated_page.coverage.stopCSSCoverage()
        assert len(coverage) == 1

    class TestResetOnNavigation:
        @sync
        async def test_reports_stylesheets_across_navigation_when_disabled(self, isolated_page, server):
            await isolated_page.coverage.startCSSCoverage(resetOnNavigation=False)
            await isolated_page.goto(server / 'csscoverage/multiple.html')
            await isolated_page.goto(server.empty_page)
            coverage = await isolated_page.coverage.stopCSSCoverage()
            assert len(coverage) == 2

        @sync
        async def test_does_not_report_stylesheets_across_navigation_when_enabled(self, isolated_page, server):
            await isolated_page.coverage.startCSSCoverage()  # enabled by default
            await isolated_page.goto(server / 'csscoverage/multiple.html')
            await isolated_page.goto(server.empty_page)
            coverage = await isolated_page.coverage.stopCSSCoverage()
            assert len(coverage) == 0
