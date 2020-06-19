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

import jwt
from jwt.exceptions import DecodeError

from aiohttp import web, ClientSession, CookieJar
from aiomcache_multi import Client as Memcache


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())
# Cache aiohttp ClientSession instance. ClientSession should be reused if
# possible as it provides connection pooling. CookieJar is set to usafe to
# allow cookies to be used even with backend servers defined by IP address.
SESSION = ClientSession(cookie_jar=CookieJar(unsafe=True))


def _configure_cache(caches):
    if caches is None:
        return

    client, backends = None, []

    for server in caches.split(';'):
        try:
            host, port = server.split(':')

        except ValueError:
            continue

        port = int(port)
        backends.append((host, port))

    if not backends:
        LOGGER.warn('No memcache backends defined, using only in-memory cache')

    else:
        client = Memcache(backends)

    return client


def _parse_key(key):
    if key is None:
        return

    if pathexists(key):
        key = open(key, 'rb').read()

    return key


def _parse_root(mapping):
    if not mapping:
        return

    try:
        fr, to = mapping.split(':')

    except ValueError:
        raise ValueError('Root mapping (JWT_ROOT) should be in form: /path1:path2')

    return fr, to


# JWT verification key and algorithm.
KEY = _parse_key(os.environ.get('PROXY_JWT_KEY', None))
ALGO = os.environ.get('PROXY_JWT_ALGO', 'HS256')

# Address to proxy plain requests to.
ANON_UPSTREAM = os.environ.get('PROXY_ANON_UPSTREAM', None)
# Address to proxy JWT requests to.
AUTH_UPSTREAM = os.environ.get('PROXY_AUTH_UPSTREAM', None)
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


async def get_path(origin, url, **kwargs):
    # Return path from cache if available.
    path, key = await cache_get(origin)
    if path:
        return path

    # Otherwise perform a subrequest to resolve the path to a filesystem path
    async with SESSION.get(
        url, params={'preview': 'true'}, **kwargs) as res:
        LOGGER.debug(await res.text())

        # Filesystem path returned via X-Accel-Redirect header.
        try:
            path = res.headers['x-accel-redirect']

        except KeyError:
            LOGGER.exception('Could not retrieve X-Accel-Redirect header')
            raise web.HTTPBadRequest(reason='Invalid response')

    if not path.startswith(ROOT[0]):
        LOGGER.error('Path does not start with expected path')
        raise web.HTTPBadRequest(reason='Invalid path')

    # Transform path
    path = pathjoin(ROOT[1], path[len(ROOT[0]):].lstrip('/'))

    # Write back to cache if key has been populated.
    if key:
        await CACHE.set(key, path)

    return path


async def authenticated(request):
    """
    Receive a request authenticated by a JWT and forward to backend.

    This view verifies the JWT in the request then forwards it to a backend to
    determine the true path of the given URI. Once this is known, it is
    returned so that preview-server can create and store the preview.
    """
    # Extract data from URL pattern.
    version = request.match_info['version']
    uri = request.match_info['uri']

    token = request.cookies.get('sessionid')
    LOGGER.debug('Token: %s', token)
    if not token:
        raise web.HTTPBadRequest(reason='Missing session')

    try:
        user_id = jwt.decode(token, KEY, algorithms=[ALGO])['uid']

    except (DecodeError, KeyError):
        LOGGER.exception('Could not verify JWT')
        raise web.HTTPBadRequest(reason='Invalid session')

    # Build params and get path.
    origin = '/users/%s%s' % (user_id, uri)
    url = '%sapi/%s/path/data%s' % (AUTH_UPSTREAM, version, uri)
    path = await get_path(origin, url, cookies={'sessionid': token})

    # Return tuple as preview-server expects.
    return path, origin


async def anonymous(request):
    """
    Receive an anonymous request and proxy it to the backend.

    The backend provides the file path which is needed for the preview. Here
    instead of including the user_id in the origin, link_id (from the url) is
    used for uniqueness.
    """
    # Extract data from URL pattern.
    link_id = request.match_info['link_id']
    uri = request.match_info['uri']

    # Build params and get path.
    origin = '/links/%s%s' % (link_id, uri)
    url = '%s%s%s' % (ANON_UPSTREAM, link_id, uri)
    path = await get_path(origin, url)

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
anonymous.pattern = r'/{_:link/|}{link_id:[\w\d]+}{uri:.*}'
anonymous.method = 'get'
