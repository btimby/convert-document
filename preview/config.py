import os
import logging

from os.path import dirname, join as pathjoin
from runpy import run_path

from preview.errors import InvalidPluginError


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

TIME_UNITS = {
    'd': 86400,
    'h': 3600,
    'm': 60,
    's': 1,
}
SIZE_UNITS = {
    't': 1024 ** 4,
    'g': 1024 ** 3,
    'm': 1024 ** 2,
    'b': 1,
}
ROOT = dirname(dirname(__file__))


def boolean(s):
    "Any value besides the 'falsey' values should be True"
    if s in ('', None):
        return False
    return s.lower() not in ('0', 'off', 'no', 'false', 'none')


def parse_unit(s, units):
    if s in ('', None):
        return

    # Default unit is seconds.
    unit, s = 1, s.lower()
    if s[-1] in units.keys():
        unit, s = s[-1], s[:-1]
        try:
            unit = units[unit]

        except KeyError:
            raise ValueError('Unit should be one of: %s' % 
                            (', '.join(units.keys())))

    try:
        value = int(s)

    except ValueError:
        raise ValueError(
            'Must be integer followed by optional unit, ex: 1d')

    return value * unit


def interval(s):
    return parse_unit(s, TIME_UNITS)


def bytesize(s):
    return parse_unit(s, SIZE_UNITS)


def load_plugins(views):
    """
    HTTP handlers can be specified by /the/path/to/file.py:callable.
    
    A handler should be a callable with "pattern" and "method" attributes. The
    callable should accept request and return a tuple of (path, origin). Origin
    is a unique path or key that is used to cache the preview.
    """
    plugins, paths = [], views.split(';')
    for path in paths:
        # Empty string, skip...
        if not path:
            continue

        module, _, function = path.rpartition(':')

        try:
            module = run_path(module, run_name=module)

        except FileNotFoundError:
            raise InvalidPluginError('Python file does not exist: %s' % module)

        try:
            plugin = module[function]

        except KeyError as e:
            raise InvalidPluginError('Plugin function %s does not exist.' % path)

        if not callable(plugin):
            raise InvalidPluginError('Plugin %s is not callable' % path)

        if not hasattr(plugin, 'pattern'):
            raise InvalidPluginError('Plugin %s does not have "pattern" attribute' % path)

        if getattr(plugin, 'method', '').lower() not in ('get', 'post'):
            raise InvalidPluginError('Plugin %s has invalid "method" attribute' % path)

        # Everything seems good.
        plugins.append(plugin)

    return plugins


# Configuration
CACHE_CONTROL = interval(os.environ.get('PVS_CACHE_CONTROL'))
FILE_ROOT = os.environ.get('PVS_FILES', '/mnt/files')
DEFAULT_WIDTH = os.environ.get('PVS_DEFAULT_WIDTH', 320)
DEFAULT_HEIGHT = os.environ.get('PVS_DEFAULT_HEIGHT', 240)
MAX_WIDTH = os.environ.get('PVS_MAX_WIDTH', 4000)
MAX_HEIGHT = os.environ.get('PVS_MAX_HEIGHT', 4000)
DEFAULT_FORMAT = os.environ.get('PVS_DEFAULT_FORMAT', 'image')
LOGLEVEL = getattr(logging, os.environ.get('PVS_LOG_LEVEL', 'WARNING').upper())
HTTP_LOGLEVEL = getattr(
    logging, os.environ.get('PVS_HTTP_LOG_LEVEL', 'INFO').upper())
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
MAX_FILE_SIZE = int(os.environ.get('PVS_MAX_FILE_SIZE', '0'))
MAX_PAGES = int(os.environ.get('PVS_MAX_PAGES', '0'))
CLEANUP_MAX_SIZE = bytesize(os.environ.get('PVS_CLEANUP_MAX_SIZE', None))
CLEANUP_INTERVAL = interval(os.environ.get('PVS_CLEANUP_INTERVAL', None))
MAX_OFFICE_WORKERS = int(os.environ.get('PVS_MAX_OFFICE_WORKERS', 0))
PLUGINS = load_plugins(os.environ.get('PVS_PLUGINS', ''))
ICON_ROOT = os.environ.get('PVS_ICONS', pathjoin(ROOT, 'images/file-types'))
ICON_RESIZE = boolean(os.environ.get('PVS_ICON_RESIZE', 'true'))
ICON_REDIRECT = os.environ.get('PVS_ICON_REDIRECT', None)
