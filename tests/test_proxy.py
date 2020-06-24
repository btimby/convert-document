import os

from unittest import TestCase

from os.path import join as pathjoin, dirname

from aiohttp.test_utils import unittest_run_loop
from aiohttp import web
from aioresponses import aioresponses

import jwt

from tests.base import PreviewTestCase

from plugins import proxy


class ProxyPluginTestCase(PreviewTestCase):
    @unittest_run_loop
    async def test_authenticated(self):
        "Make an authenticated request."
        token = jwt.encode({'uid': 1}, proxy.KEY, algorithm=proxy.ALGO)

        with aioresponses(passthrough=['http://127.0.0.1']) as resp:
            # Mock response from Proxy backend.
            resp.get(
                'http://api/api/2/path/data/sample.pdf?preview=true',
                headers={
                    'X-Accel-Redirect': '/files/fixtures/sample.pdf'
                },
            )

            r = await self.client.request(
                'GET',
                '/api/2/path/data/sample.pdf',
                params={
                    'format': 'pdf',
                },
                cookies={
                    'sessionid': token.decode('utf8'),
                }
            )
        self.assertEqual(r.status, 200)
        self.assertEqual(r.headers['content-type'], 'application/pdf')

    @unittest_run_loop
    async def test_anonymous_link(self):
        "Make an anonymous request to longer URL."
        with aioresponses(passthrough=['http://127.0.0.1']) as resp:
            resp.get(
                'http://api/f00b4r/sample.pdf?preview=true',
                headers={
                    'X-Accel-Redirect': '/files/fixtures/sample.pdf',
                },
            )

            r = await self.client.request(
                'GET',
                '/link/f00b4r/sample.pdf',
                params={
                    'format': 'pdf',
                },
            )
        self.assertEqual(r.status, 200)
        self.assertEqual(r.headers['content-type'], 'application/pdf')

    @unittest_run_loop
    async def test_anonymous(self):
        "Make an anonymous request to shorter URL."
        with aioresponses(passthrough=['http://127.0.0.1']) as resp:
            resp.get(
                'http://api/f00b4r/sample.pdf?preview=true',
                headers={
                    'X-Accel-Redirect': '/files/fixtures/sample.pdf',
                },
            )

            r = await self.client.request(
                'GET',
                '/f00b4r/sample.pdf',
                params={
                    'format': 'pdf',
                },
            )
        self.assertEqual(r.status, 200)
        self.assertEqual(r.headers['content-type'], 'application/pdf')

    @unittest_run_loop
    async def test_unsupported(self):
        "Make a request for an unsupported file type"
        with aioresponses(passthrough=['http://127.0.0.1']) as resp:
            resp.get(
                'http://api/f00b4r/w64.exe?preview=true',
                headers={
                    'X-Accel-Redirect': '/files/fixtures/sample.pdf',
                },
            )

            r = await self.client.request(
                'GET',
                '/link/f00b4r/w64.exe',
                params={
                    'format': 'image',
                },
            )
        self.assertEqual(r.status, 200)
        self.assertEqual(r.headers['content-type'], 'image/gif')
