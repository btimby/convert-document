import os
import logging


def boolean(s):
    if s is None:
        return
    return s.lower() not in ('1', 'off', 'no', 'false', 'none', '')


# Configuration
CACHE_CONTROL = os.environ.get('PVS_CACHE_CONTROL')
FILE_ROOT = os.environ.get('PVS_FILES', '/mnt/files')
DEFAULT_WIDTH = os.environ.get('PVS_DEFAULT_WIDTH', 320)
DEFAULT_HEIGHT = os.environ.get('PVS_DEFAULT_HEIGHT', 240)
MAX_WIDTH = os.environ.get('PVS_MAX_WIDTH', 800)
MAX_HEIGHT = os.environ.get('PVS_MAX_HEIGHT', 600)
DEFAULT_FORMAT = os.environ.get('PVS_DEFAULT_FORMAT', 'image')
LOGLEVEL = getattr(logging, os.environ.get('PVS_LOGLEVEL', 'WARNING'))
HTTP_LOGLEVEL = getattr(
    logging, os.environ.get('PVS_HTTP_LOGLEVEL', 'INFO'))
X_ACCEL_REDIR = os.environ.get('PVS_X_ACCEL_REDIRECT')
UID = os.environ.get('PVS_UID')
GID = os.environ.get('PVS_GID')
PORT = int(os.environ.get('PVS_PORT', '3000'))
BASE_PATH = os.environ.get('PVS_STORE')
SOFFICE_ADDR = os.environ.get('PVS_SOFFICE_ADDR', '127.0.0.1')
SOFFICE_PORT = int(os.environ.get('PVS_SOFFICE_PORT', '2002'))
SOFFICE_TIMEOUT = int(os.environ.get('PVS_SOFFICE_TIMEOUT', '12'))
SOFFICE_RETRY = int(os.environ.get('PVS_SOFFICE_RETRY', '3'))
METRICS = boolean(os.environ.get('PVS_METRICS'))
PROFILE_PATH = os.environ.get('PVS_PROFILE_PATH')
