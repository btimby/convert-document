import os
import logging
import functools
import pathlib

from io import StringIO
from os.path import normpath, isfile, getsize, dirname
from os.path import join as pathjoin

from tempfile import NamedTemporaryFile

import uvloop
import asyncio
from concurrent.futures import ThreadPoolExecutor
from aiohttp import web, ClientSession
from aiohttp.web_middlewares import normalize_path_middleware

from preview import icons
from preview.utils import (
    run_in_executor, log_duration, get_extension, chroot
)
from preview.preview import generate, UnsupportedTypeError, Backend
from preview.storage import BASE_PATH, Cleanup
from preview.metrics import (
    metrics_handler, metrics_middleware, TRANSFER_LATENCY,
    TRANSFERS_IN_PROGRESS
)
from preview.config import (
    boolean, DEFAULT_FORMAT, DEFAULT_WIDTH, DEFAULT_HEIGHT, MAX_WIDTH,
    MAX_HEIGHT, LOGLEVEL, HTTP_LOGLEVEL, FILE_ROOT, CACHE_CONTROL, UID, GID,
    X_ACCEL_REDIR, PORT, PROFILE_PATH, MAX_FILE_SIZE, MAX_PAGES, PLUGINS,
)
from preview.models import PreviewModel


# Limits
MEGABYTE = 1024 * 1024
BUFFER_SIZE = 8 * MEGABYTE
MAX_UPLOAD = 800 * MEGABYTE
ROOT = dirname(__file__)

LOGGER = logging.getLogger()
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(LOGLEVEL)
logging.getLogger('aiohttp').setLevel(HTTP_LOGLEVEL)


def check_size(size):
    if MAX_FILE_SIZE and size > MAX_FILE_SIZE:
        raise web.HTTPBadRequest(reason='File larger than configured maximum')


@log_duration
async def upload(upload):
    extension = get_extension(upload.filename)
    tip = TRANSFERS_IN_PROGRESS.labels('upload')
    tl = TRANSFER_LATENCY.labels('upload')

    with tl.time(), tip.track_inprogress():
        with NamedTemporaryFile(delete=False, suffix='.%s' % extension) as t:
            size = 0
            while True:
                data = await run_in_executor(upload.file.read)(BUFFER_SIZE)
                if not data:
                    break
                size += len(data)
                check_size(size)
                await run_in_executor(t.write)(data)
        return t.name


@log_duration
async def download(url):
    extension = get_extension(url)
    tip = TRANSFERS_IN_PROGRESS.labels('download')
    tl = TRANSFER_LATENCY.labels('download')

    with tl.time(), tip.track_inprogress():
        async with ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise web.HTTPBadRequest(
                        reason='Could not download: %s, %s' % (
                            url, resp.reason))

                size = 0
                with NamedTemporaryFile(
                        delete=False, suffix='.%s' % extension) as t:
                    while True:
                        data = await resp.content.read(BUFFER_SIZE)
                        if not data:
                            break
                        size += len(data)
                        check_size(size)
                        await run_in_executor(t.write)(data)
                    return t.name


def parse_pages(pages):
    if not pages:
        return (1, 1)

    elif pages == 'all':
        return (0, MAX_PAGES)

    else:
        try:
            first, last = map(int, pages.split('-'))

            # MAX_PAGES == 0 == unlimited, we can let them choose.
            if MAX_PAGES != 0:
                # Otherwise limit to MAX_PAGES.
                last = min(last, first + MAX_PAGES)

            return first, last

        except ValueError as e:
            LOGGER.debug('Ignoring: %s', e, exc_info=True)
            raise web.HTTPBadRequest(
                reason='Pages must be a range n-n or "all"')


class PreviewResponse(web.FileResponse):
    def __init__(self, obj, *args, **kwargs):
        self._obj = obj
        super(PreviewResponse, self).__init__(obj.dst.path, *args, **kwargs)
        self.content_type = obj.content_type

    async def prepare(self, *args, **kwargs):
        try:
            return await super(PreviewResponse, self).prepare(
                *args, **kwargs)

        finally:
            await run_in_executor(self._obj.cleanup)()


async def get_path(request):
    if request.method == 'POST':
        data = {}
        data.update(request.query)
        data.update(await request.post())

    else:
        data = request.query

    path = data.get('path')
    file = data.get('file')
    url = data.get('url')

    if path:
        # TODO: sanitize this path, ensure it is rooted in FILE_ROOT
        origin = path
        path = normpath(path)
        path = pathjoin(FILE_ROOT, path)
        if not isfile(path):
            raise web.HTTPBadRequest(reason='Invalid path')

        check_size(getsize(path))

    elif file:
        origin = None
        path = await upload(file)

    elif url:
        origin = url
        path = await download(url)

    else:
        raise web.HTTPBadRequest(reason='No path, file or url provided')

    if not isfile(path):
        raise web.HTTPNotFound()

    return path, origin


async def get_params(request):
    """
    Retrieve preview parameters (omitting path / file).
    """
    if request.method == 'POST':
        data = {}
        data.update(request.query)
        data.update(await request.post())

    else:
        data = request.query

    name = data.get('name')

    format = data.get('format', DEFAULT_FORMAT)
    width = int(data.get('width', DEFAULT_WIDTH))
    height = int(data.get('height', DEFAULT_HEIGHT))
    width, height = min(width, MAX_WIDTH), min(height, MAX_HEIGHT)
    pages = parse_pages(data.get('pages'))

    store = None
    if 'pvs-store-disabled' in request.headers:
        store = boolean(request.headers['pvs-store-disabled'])

    args = {
        'pages': pages,
        'store': store,
    }

    return width, height, format, name, args


async def preview(obj):
    try:
        try:
            await generate(obj)
            status = 200

        except Exception as e:
            # NOTE: we send 203 to indicate that the content is not exactly
            # what was requested. This helps our tools / tests determine
            # if an error occurred. We also disable caching in the case of
            # an error response.
            LOGGER.exception(e)
            obj.cleanup()
            if not icons.get(obj):
                raise web.HTTPInternalServerError()

            await generate(obj)
            status = 203

        if BASE_PATH is None or obj.dst.is_temp:
            response = PreviewResponse(obj, status=status)

        elif X_ACCEL_REDIR:
            x_accel_path = chroot(obj.dst.path, BASE_PATH, X_ACCEL_REDIR)
            response = web.Response(status=status)
            response.headers['X-Accel-Redirect'] = x_accel_path
            response.content_type = obj.content_type

        else:
            response = PreviewResponse(obj, status=status)

        # Don't cache error responses.
        if CACHE_CONTROL and status == 200:
            max_age = 60 * int(CACHE_CONTROL)
            response.headers['Cache-Control'] = \
                'max-age=%i, public' % max_age

    except Exception as e:
        LOGGER.exception(e)
        raise web.HTTPInternalServerError(reason='Unrecoverable error')

    return response


def make_handler(f):
    # Sets up an HTTP handler, uses f to extract parameters. f() is expected
    # to return a tuple of (path, origin).
    async def handler(request):
        path, origin = await f(request)
        width, height, format, name, args = await get_params(request)
        obj = PreviewModel(path, width, height, format, origin=origin,
                           name=name, args=args)

        return await preview(obj)

    return handler


async def extension_list():
    ext_list = StringIO()
    ext_list.write('extensions = [')
    for extensions, obj in Backend.backends.items():
        ext_list.write('\r\n    # %s backend extensions' % obj.name.title())
        before, after, llen = '', '', 0
        for extension in extensions:
            ext_str = "'%s'," % extension

            if llen == 0 or llen + len(ext_str) + 1 >= 80:
                llen = 0
                before, after = '\r\n    ', ''

            else:
                before, after = ' ', ''

            llen += len(before) + len(ext_str) + len(after)

            ext_list.write(before)
            ext_list.write(ext_str)
            ext_list.write(after)

        ext_list.write('\r\n')
    ext_list.write(']\r\n')

    return ext_list.getvalue()


async def info(request):
    return web.Response(text=await extension_list())


async def test(request):
    return web.FileResponse(pathjoin(ROOT, 'html/test.html'))


def main():
    if GID:
        os.setgid(int(GID))
    if UID:
        os.setuid(int(UID))

    app = web.Application(
        client_max_size=MAX_UPLOAD, middlewares=[
            normalize_path_middleware(), metrics_middleware()
            ])

    # Register handler for default preview routes.
    default_handler = make_handler(get_path)
    app.add_routes([
        web.post('/preview/', default_handler),
        web.get('/preview/', default_handler)])
    # Some views not related to generating previews.
    app.add_routes([web.get('/', info)])
    app.add_routes([web.get('/test/', test)])
    app.add_routes([web.get('/metrics/', metrics_handler)])

    # Load and register any plugins.
    for plugin in PLUGINS:
        # We don't need to do much checking here as the config module validates
        # the given plugins.
        method = getattr(web, plugin.method.lower())
        app.add_routes([method(plugin.pattern, make_handler(plugin))])

    loop = uvloop.new_event_loop()
    # Set up a default executor for conversion backends.
    loop.set_default_executor(ThreadPoolExecutor(max_workers=40))
    asyncio.set_event_loop(loop)

    # TODO: probably a better way...
    Cleanup(loop)

    # TODO: figure out how to wait for pending requests before exiting.
    web.run_app(app, port=PORT)


if PROFILE_PATH:
    # To profile this application.
    #
    # - Map a volume in via docker: -v /tmp:/mnt/profile
    # - Set PVS_PROFILE_PATH=/mnt/profile
    # - Run the application, ensure it is NOT killed with TERM but INT, for
    #   example:
    #
    # docker-compose kill -s SIGINT
    #
    import yappi
    yappi.start()

    LOGGER.warning('Running under profiler.')
    try:
        main()

    finally:
        LOGGER.warning('Saving profile data to: %s.', PROFILE_PATH)
        yappi.stop()

        fstats = yappi.get_func_stats()
        tstats = yappi.get_thread_stats()

        for stat_type in ['pstat', 'callgrind', 'ystat']:
            path = pathjoin(PROFILE_PATH, 'preview.%s' % stat_type)
            fstats.save(path, type=stat_type)

        path = pathjoin(PROFILE_PATH, 'preview.func_stats')
        with open(path, 'w') as fh:
            fstats.print_all(out=fh)

        path = pathjoin(PROFILE_PATH, 'preview.thread_stats')
        with open(path, 'w') as fh:
            tstats.print_all(out=fh)

else:
    main()
