"""
A plugin that retrieves file paths from backend server.

This module implements a plugin for preview-server that allows preview-server
to proxy requests to a backend server.

Preview requests are received by preview-server, the path is given within the
URL. In order to locate the file on disk, this plugin will make a request to a
backend server, providing a session token and a portion of the URI. The backend
replies with a path in the X-Accel-Redirect header. This path is used to
generate a preview.

Once the path has been resolved, an "origin" value is created that identifies
the file. This origin includes user information from the session token in order
to preserve user-based privileges that the backend enforces. In other words,
the file path alone is not sufficient to identify an individual file. Thus the
user_id is combined with the path and use as a caching key.

By utilizing the URI fragment as well as the user_id as a key, the true path
can be cached, obviating the need for duplicate requests to the backend.
"""

import os
import logging
import hashlib

from os.path import join as pathjoin, exists as pathexists
from urllib.parse import quote as urlquote

import jwt
from jwt.exceptions import DecodeError

from aiohttp import web, ClientSession, CookieJar
from aiomcache_multi import Client as Memcache

from preview import LOOP
from preview.utils import log_duration


# These functions are used to parse configuration into globals.
def _configure_cache(caches):
    if not caches:
        return

    backends = []

    for server in caches.split(';'):
        try:
            host, port = server.split(':')
            port = int(port)

        except ValueError:
            continue

        backends.append((host, port))

    if not backends:
        LOGGER.warn('No memcache backends defined, using only in-memory cache')

    else:
        return Memcache(backends, loop=LOOP)


def _parse_key(key):
    if not key:
        return

    if pathexists(key):
        key = open(key, 'rb').read()

    return key


def _parse_root(mapping):
    if not mapping:
        return

    mappings = []
    for pair in mapping.split(';'):
        try:
            fr, to = pair.split(':')

        except ValueError:
            raise ValueError('Root mapping (JWT_ROOT) should be in form: /uri1:/path1;/uri2:/path2')

        mappings.append((fr, to))

    return mappings


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())
# Cache aiohttp ClientSession instance. ClientSession should be reused if
# possible as it provides connection pooling. CookieJar is set to usafe to
# allow cookies to be used even with backend servers defined by IP address.
SESSION = ClientSession(loop=LOOP, cookie_jar=CookieJar(unsafe=True))

# JWT verification key and algorithm.
KEY = _parse_key(os.environ.get('JWT_KEY', None))
ALGO = os.environ.get('JWT_ALGO', 'HS256')

# Address to proxy requests to.
UPSTREAM = os.environ.get('PROXY_UPSTREAM', None)
# Cache server addresses.
CACHE = _configure_cache(os.environ.get('PROXY_CACHE_ADDRESS', None))
# This configuration option contains a mapping from a URI to a disk path. It
# mirrors an alias configured in nginx that is used to download files. For
# example this configuration option might be: /downloads:/path/to/files. When
# the backend returns a path such as: /downloads/a/file.txt, the true path of
# the file is /path/to/files/a/file.txt.
ROOT = _parse_root(os.environ.get('PROXY_BASE_PATH'))


async def cache_get(origin):
    if not CACHE:
        return None, None

    # Hash origin
    key = 'preview:%s' % hashlib.md5(origin.encode('utf8')).hexdigest()

    # Look up path in cache using hashed origin as cache key
    return await CACHE.get(key), key


async def get_path(request, origin, url, **kwargs):
    # Return path from cache if available.
    path, key = await cache_get(origin)
    if path:
        return path.decode('utf8')

    # Set params and headers without clobbering kwargs.
    kwargs.setdefault('params', {})['preview'] = 'true'
    headers = kwargs.setdefault('headers', {})
    headers['X-Forwarded-Proto'] = 'https'
    headers['Host'] = request.headers.get('host')
    x_forwarded_for = request.headers.get('x-forwarded-for')
    if x_forwarded_for:
        headers['X-Forwarded-For'] = x_forwarded_for

    # Otherwise perform a subrequest to resolve the path to a filesystem path
    async with SESSION.get(url, **kwargs) as res:
        if res.status != 200:
            LOGGER.exception('Backend request failed.')
            raise web.HTTPInternalServerError(
                reason='Backend returned %i' % res.status)

        # Filesystem path returned via X-Accel-Redirect header.
        try:
            path = res.headers['x-accel-redirect']

        except KeyError:
            LOGGER.exception('Could not retrieve X-Accel-Redirect header')
            raise web.HTTPBadRequest(reason='Invalid response')

    # Transform path if a suitable mapping is defined.
    for pair in ROOT:
        if path.startswith(pair[0]):
            path = pathjoin(pair[1], path[len(pair[0]):].lstrip('/'))
            break

    else:
        LOGGER.error('Path does not start with expected path')
        raise web.HTTPBadRequest(reason='Invalid path')

    # Write back to cache if key has been populated.
    if key:
        await CACHE.set(key, path.encode('utf8'))

    return path


@log_duration
async def authenticated(request):
    """
    Receive a request authenticated by a JWT and forward to backend.

    This view verifies the JWT in the request then forwards it to a backend to
    determine the true path of the given URI. Once this is known, it is
    returned so that preview-server can create and store the preview.
    """
    # Extract data from URL pattern.
    version = request.match_info['version']
    uri = urlquote(request.match_info['uri'])

    token = request.cookies.get('sessionid')
    LOGGER.debug('Token: %s', token)
    if not token:
        raise web.HTTPBadRequest(reason='Missing session')

    try:
        user_id = jwt.decode(token, KEY, algorithms=[ALGO])['u']
        assert user_id is not None

    except (DecodeError, KeyError, AssertionError):
        LOGGER.exception('Could not verify JWT')
        raise web.HTTPBadRequest(reason='Invalid session')

    # Build params and get path.
    origin = '/users/%s%s' % (user_id, uri)
    url = '%sapi/%s/path/data%s' % (UPSTREAM, version, uri)
    path = await get_path(request, origin, url, cookies={'sessionid': token})

    # Return tuple as preview-server expects.
    return path, origin


@log_duration
async def anonymous(request):
    """
    Receive an anonymous request and proxy it to the backend.

    The backend provides the file path which is needed for the preview. Here
    instead of including the user_id in the origin, link_id (from the url) is
    used for uniqueness.
    """
    # Extract data from URL pattern.
    link_id = request.match_info['link_id']
    uri = urlquote(request.match_info['uri'])

    # Build params and get path.
    origin = '/link/%s%s' % (link_id, uri)
    url = '%s%s' % (UPSTREAM.rstrip('/'), origin)
    path = await get_path(request, origin, url)

    # Return tuple as preview-server expects.
    return path, origin


# Configure the route for JWT handling.
# /api/2/path/data/path_to_file.pdf?preview=true&width=40&height=50
authenticated.pattern = r'/api/{version:\d+}/path/data{uri:.*}'
authenticated.method = 'get'

# Configure the route for plain proxying.
# /link/keJf1XlM5aY/path_to_file.exe?preview=true
# /keJf1XlM5aY/path_to_file.exe?preview=true
# Pattern is a bit complex as we need link/ to be optional in order to support
# both forms of the url.
anonymous.pattern = r'/{_:link/|}{link_id:[=\-\w]+}{uri:.*}'
anonymous.method = 'get'
