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

from aiohttp import web, ClientSession
from aiomcache_multi import Client as Memcache


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def _configure_cache(caches):
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

# Address to proxy request to.
UPSTREAM = os.environ.get('PROXY_UPSTREAM', None)
# Cache server addresses.
CACHE = _configure_cache(os.environ.get('PROXY_CACHE_ADDRESS', ''))
# This configuration option contains a mapping from a URI to a disk path. It
# mirrors an alias configured in nginx that is used to download files. For
# example this configuration option might be: /downloads:/path/to/files. When
# the backend returns a path such as: /downloads/a/file.txt, the true path of
# the file is /path/to/files/a/file.txt.
ROOT = _parse_root(os.environ.get('PROXY_BASE_PATH'))


async def handler(request):
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

    origin = '/users/%d%s' % (user_id, uri)

    if CACHE:
        # Hash origin
        key = 'preview:%s' % hashlib.md5(origin.encode('utf8')).hexdigest()

        # Look up path in cache using hashed origin as cache key
        path = CACHE.get(key)

        # If cache hit, return path
        if path:
            return path, origin

    # Otherwise, perform subrequest, add path to cache, return it.
    async with ClientSession(cookies={'sessionid': token}) as s:
        async with s.get('%sapi/%s/path/data%s' % (UPSTREAM, version, uri)) as r:
            LOGGER.debug(await r.text())

            # SmartFile returns the filesystem path in X-Accel-Redirect header.
            try:
                path = r.headers['x-accel-redirect']

            except KeyError:
                LOGGER.exception('Could not retrieve X-Accel-Redirect header')
                raise web.HTTPBadRequest(reason='Invalid response')

    if not path.startswith(ROOT[0]):
        LOGGER.error('Path does not start with expected path')
        raise web.HTTPBadRequest(reason='Invalid path')

    # Transform path
    path = pathjoin(ROOT[1], path[len(ROOT[0]):].lstrip('/'))

    if CACHE:
        CACHE.set(key, path)

    # Return tuple as preview-server expects.
    return path, origin


# Let preview-server know how to configure our route.
handler.pattern = r'/api/{version:\d+}/path/data{uri:.*}'
handler.method = 'get'
