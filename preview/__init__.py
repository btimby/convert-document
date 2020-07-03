import os
import logging
import functools
import pathlib
import uvloop

import asyncio
from concurrent.futures import ThreadPoolExecutor

from io import StringIO
from os.path import normpath, isfile, getsize, dirname
from os.path import join as pathjoin

from tempfile import NamedTemporaryFile

from aiohttp import web, ClientSession
from aiohttp.web_middlewares import normalize_path_middleware
from aiohttp_sentry import SentryMiddleware


# Use uvloop, set it up early so other modules can access the correct event
# loop during import.
LOOP = uvloop.new_event_loop()
# Set up a default executor for conversion backends.
LOOP.set_default_executor(ThreadPoolExecutor(max_workers=40))
asyncio.set_event_loop(LOOP)


from preview import icons
from preview.utils import (
    run_in_executor, log_duration, get_extension, chroot
)
from preview.preview import generate, UnsupportedTypeError, Backend
from preview.storage import BASE_PATH
from preview.metrics import (
    metrics_handler, metrics_middleware, TRANSFER_LATENCY,
    TRANSFERS_IN_PROGRESS
)
from preview.config import (
    boolean, DEFAULT_FORMAT, DEFAULT_WIDTH, DEFAULT_HEIGHT, MAX_WIDTH,
    MAX_HEIGHT, LOGLEVEL, HTTP_LOGLEVEL, FILE_ROOT, CACHE_CONTROL,
    X_ACCEL_REDIR, MAX_FILE_SIZE, MAX_PAGES, PLUGINS,
)
from preview.models import PreviewModel
from preview.errors import InvalidPageError


# Limits
MEGABYTE = 1024 * 1024
BUFFER_SIZE = 8 * MEGABYTE
MAX_UPLOAD = 800 * MEGABYTE
ROOT = dirname(__file__)
SENTRY_DSN = os.environ.get('SENTRY_DSN', None)

# For source code formatting.
# (variable_declaration, comment, line_ending)
FORMATS = {
    'py': ('', '# ', ''),
    'js': ('var ', '// ', ';'),
}

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

    if pages == 'all':
        return (1, MAX_PAGES)

    if pages.isdigit():
        return(int(pages), int(pages))

    try:
        first, last = map(int, pages.split('-'))

        # MAX_PAGES == 0 == unlimited, we can let them choose.
        if MAX_PAGES != 0:
            # Otherwise limit to MAX_PAGES (inclusive).
            last = min(last, first + MAX_PAGES - 1)

        return first, last

    except ValueError as e:
        LOGGER.exception('Could not parse page range %s', pages)
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
        origin = path = await upload(file)

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


def make_handler(f):
    # Sets up an HTTP handler, uses f to extract parameters. f() is expected
    # to return a tuple of (path, origin).
    async def handler(request):
        try:
            path, origin = await f(request)
            width, height, format, name, args = await get_params(request)
            obj = PreviewModel(path, width, height, format, origin=origin,
                            name=name, args=args)

            await generate(obj)

        except web.HTTPException:
            raise

        except InvalidPageError:
            raise web.HTTPBadRequest(reason='Invalid page requested')

        except Exception as e:
            if not isinstance(e, UnsupportedTypeError):
                LOGGER.exception(e)

            # Attempt to get a file type icon.
            if not await icons.get(obj):
                # If no icon could be located, raise the exception.
                raise web.HTTPInternalServerError(reason='Unrecoverable error')

        if BASE_PATH is None or obj.dst.is_temp:
            response = PreviewResponse(obj)

        elif X_ACCEL_REDIR:
            x_accel_path = chroot(obj.dst.path, BASE_PATH, X_ACCEL_REDIR)
            response = web.Response()
            response.headers['X-Accel-Redirect'] = x_accel_path
            response.content_type = obj.content_type

        else:
            response = PreviewResponse(obj)

        # Don't cache error responses.
        if CACHE_CONTROL:
            max_age = 60 * int(CACHE_CONTROL)
            response.headers['Cache-Control'] = \
                'max-age=%i, public' % max_age

        return response

    return handler


async def info(request):
    format = request.query.get('format', 'py')
    try:
        decl, comment, lend = FORMATS[format]

    except KeyError:
        raise web.HTTPBadRequest(reason='Invalid format %s' % format)

    code = StringIO()
    code.write('%sextensions = [' % decl)
    pre, llen = '', 0

    for extensions, backend in Backend.backends.items():
        code.write(pre)
        code.write('\r\n    %s%s supported formats\r\n    ' % (
            comment, backend.name.title()))
        pre, llen = '', 0
        for extension in extensions:
            atom = "'%s'" % extension

            if llen + len(pre) + len(atom) >= 75:
                pre = ',\r\n    '
                llen = 0

            code.write(pre)
            code.write(atom)
            llen += len(pre) + len(atom)
            pre = ', '
        pre = ',\r\n'

    code.write('\r\n]%s' % lend)

    return web.Response(text=code.getvalue())


async def test(request):
    return web.FileResponse(pathjoin(ROOT, 'html/test.html'))


def get_app():
    middlewares = [
        normalize_path_middleware(),
        metrics_middleware(),
    ]
    if SENTRY_DSN:
        middlewares.append(
            SentryMiddleware(
                patch_logging=True, sentry_log_level=logging.ERROR))
    app = web.Application(
        client_max_size=MAX_UPLOAD, middlewares=middlewares)

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

    return app
