import os
import unittest


# Set some settings for testing...
os.environ['PVS_MAX_PAGES'] = '10'


from tests.test_preview import *
from tests.test_plugins import *


unittest.main()
