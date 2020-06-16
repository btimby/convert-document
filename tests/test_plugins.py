import os

from unittest import TestCase

from os.path import join as pathjoin, dirname

from aiohttp.test_utils import unittest_run_loop
from aiohttp import web

from tests.base import PreviewTestCase

from preview.config import load_plugins
from preview.errors import InvalidPluginError


class PluginTestCase(TestCase):
    def test_load_invalid(self):
        with self.assertRaises(InvalidPluginError):
            load_plugins('%s:invalid' % __file__)

    def test_load_valid(self):
        plugins = load_plugins('%s:plugin' % __file__)
        self.assertEqual(len(plugins), 1)
        self.assertTrue(callable(plugins[0]))


def plugin(request):
    pass


plugin.pattern = r''
plugin.method = 'get'


def invalid(request):
    pass
