import os
import unittest
from os.path import dirname


ROOT = dirname(dirname(__file__))


# Set some settings for testing...
os.environ['PVS_MAX_PAGES'] = '10'
os.environ['PVS_PLUGINS'] = 'plugins/smartfile.py:handler'

# Smartfile plugin settings:
os.environ['JWT_KEY'] = 'foo key bar'
os.environ['JWT_ALGO'] = 'HS256'
os.environ['JWT_UPSTREAM'] = 'http://api/'
os.environ['JWT_BASE_PATH'] = ROOT


from tests.test_preview import *
from tests.test_plugins import *
from tests.test_smartfile import *


unittest.main()
