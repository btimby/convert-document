import os
import unittest
from os.path import dirname


ROOT = dirname(dirname(__file__))


# Set some settings for testing...
os.environ['PVS_MAX_PAGES'] = '10'
os.environ['PVS_PLUGINS'] = 'plugins/proxy.py:authenticated;plugins/proxy.py:anonymous'

# Smartfile plugin settings:
os.environ['PROXY_JWT_KEY'] = 'foo key bar'
os.environ['PROXY_JWT_ALGO'] = 'HS256'
os.environ['PROXY_AUTH_UPSTREAM'] = 'http://api/'
os.environ['PROXY_ANON_UPSTREAM'] = 'http://api/'
os.environ['PROXY_BASE_PATH'] = '/files/:%s' % ROOT


from tests.test_preview import *
from tests.test_plugins import *
from tests.test_proxy import *
from tests.test_icons import *


unittest.main()
