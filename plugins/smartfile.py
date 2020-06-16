"""
An adapter from SmartFile to preview-server.

This module implements a plugin for preview-server that allows preview-server
to proxy requests to the SmartFile API.

Requests are received by preview-server, the route pattern allows it to respond
to a preview request. Such requests are routed to preview-server rather than
the SmartFile API. The handler in this module is invoked in order to convert
the provided uri to a filesystem path. The filesystem path is what
preview-server requires in order to generate a preview.

This module also takes care to include the user_id into the origin (origin is
used by preview-server to store generated previews). This means that generated
previews will only be returned from cache for the same user. In other words,
the API is always asked to convert a uri to a path for each user. Otherwise
authentication would be completely bypassed for previews.


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
KEY = _parse_key(os.environ.get('JWT_KEY', None))
ALGO = os.environ.get('JWT_ALGO', 'HS256')

# Address to proxy request to.
UPSTREAM = os.environ.get('JWT_UPSTREAM', None)
# Cache server addresses.
CACHE = _configure_cache(os.environ.get('JWT_CACHE_ADDRESS', ''))
ROOT = _parse_root(
    os.environ.get(
        'JWT_BASE_PATH',
        '/internal/downloads:/mnt/mfs00/scratch00/temp/downloads/'))


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
        raise web.HTTPBadRequest('Invalid path')

    # Transform path
    path = pathjoin(ROOT[1], path[len(ROOT[0]:)])

    if CACHE:
        CACHE.set(key, path)

    # Return tuple as preview-server expects.
    return path, origin


# Let preview-server know how to configure our route.
handler.pattern = r'/api/{version:\d+}/path/data{uri:.*}'
handler.method = 'get'
