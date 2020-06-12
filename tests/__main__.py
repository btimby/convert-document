import os
import unittest


# Set some settings for testing...
os.environ['PVS_MAX_PAGES'] = '10'


from tests.test_preview import *


unittest.main()
