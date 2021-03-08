import os
import unittest
from os.path import dirname


ROOT = dirname(dirname(__file__))


# Set some settings for testing...
os.environ['PVS_MAX_PAGES'] = '10'

# Smartfile plugin settings:
os.environ['JWT_KEY'] = 'foo key bar'
os.environ['JWT_ALGO'] = 'HS256'
os.environ['PROXY_UPSTREAM'] = 'http://api/'
os.environ['PROXY_BASE_PATH'] = '/files/:%s' % ROOT


from tests.test_preview import *
from tests.test_plugins import *
from tests.test_icons import *
from tests.test_config import *


unittest.main()
