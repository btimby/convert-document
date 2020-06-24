import os

from unittest import TestCase

from os.path import join as pathjoin, dirname

from aiohttp.test_utils import unittest_run_loop
from aiohttp import web

from tests.base import PreviewTestCase

from preview import parse_pages
from preview.config import MAX_PAGES, boolean, interval


ROOT = dirname(dirname(__file__))
FIXTURE_W64_EXE = pathjoin(ROOT, 'fixtures/w64.exe')


class PreviewFormatTestCase(PreviewTestCase):
    @unittest_run_loop
    async def test_exe(self):
        "Request a preview for unsupported format and ensure icon is returned."
        r = await self.client.request(
            'GET', '/preview/',
            params={'format': 'image', 'path': FIXTURE_W64_EXE}
        )
        # Status 203 indicates success using alternate representation
        # (file type icon).
        self.assertEqual(r.status, 200)
        self.assertEqual(r.headers['content-type'], 'image/gif')
