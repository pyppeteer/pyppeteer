#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from tornado import web


BASE_HTML = '''
<html>
<head><title>main</title></head>
<body>
<h1 id="hello">Hello</h1>
<a id="link1" href="./1">link1</a>
<a id="link2" href="./2">link2</a>
</body>
</html>
'''


class MainHandler(web.RequestHandler):
    def get(self) -> None:
        self.write(BASE_HTML)


class LinkHandler1(web.RequestHandler):
    def get(self) -> None:
        self.write('''
<head><title>link1</title></head>
<h1 id="link1">Link1</h1>
<a id="back1" href="./">back1</a>
        ''')


class RedirectHandler1(web.RequestHandler):
    def get(self) -> None:
        self.redirect('/redirect2')


class RedirectHandler2(web.RequestHandler):
    def get(self) -> None:
        self.write('<h1 id="red2">redirect2</h1>')


class AuthHandler(web.RequestHandler):
    def get(self) -> None:
        print(self.request.headers, flush=True)


def get_application() -> web.Application:
    return web.Application([
        ('/', MainHandler),
        ('/1', LinkHandler1),
        ('/redirect1', RedirectHandler1),
        ('/redirect2', RedirectHandler2),
        ('/auth', AuthHandler),
    ], logging='error')


if __name__ == '__main__':
    import asyncio
    from pyppeteer.util import install_asyncio
    install_asyncio()
    app = get_application()
    app.listen(9000)
    asyncio.get_event_loop().run_forever()
