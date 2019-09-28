import os
import logging
import functools

from os.path import normpath, splitext, isfile
from os.path import join as pathjoin

from tempfile import NamedTemporaryFile

import uvloop
import asyncio
from aiohttp import web, ClientSession
from aiohttp.web_middlewares import normalize_path_middleware
from aiohttp_prometheus import setup_metrics
from async_generator import asynccontextmanager

from preview.preview import Backend
from preview.utils import run_in_executor, log_duration, safe_delete
from preview.preview import generate, UnsupportedTypeError
from preview.storage import cleanup, is_temp


# Limits
MEGABYTE = 1024 * 1024
BUFFER_SIZE = 8 * MEGABYTE
MAX_UPLOAD = 800 * MEGABYTE

# Configuration
FILE_ROOT = os.environ.get('PREVIEW_FILES', '/mnt/files')
WIDTH = os.environ.get('PREVIEW_WIDTH', 320)
HEIGHT = os.environ.get('PREVIEW_HEIGHT', 240)
MAX_WIDTH = os.environ.get('PREVIEW_MAX_WIDTH', 800)
MAX_HEIGHT = os.environ.get('PREVIEW_MAX_HEIGHT', 600)
DEFAULT_FORMAT = os.environ.get('PREVIEW_DEFAULT_FORMAT', 'image')
LOGLEVEL = getattr(logging, os.environ.get('PREVIEW_LOGLEVEL', 'WARNING'))
HTTP_LOGLEVEL = getattr(
    logging, os.environ.get('PREVIEW_HTTP_LOGLEVEL', 'INFO'))

LOGGER = logging.getLogger()
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(LOGLEVEL)
logging.getLogger('aiohttp').setLevel(HTTP_LOGLEVEL)


@log_duration
async def upload(upload):
    extension = splitext(upload.filename)[1]
    with NamedTemporaryFile(delete=False, suffix=extension) as t:
        while True:
            data = await run_in_executor(upload.file.read)(BUFFER_SIZE)
            if not data:
                break
            await run_in_executor(t.write)(data)
    return t.name


@log_duration
async def download(url):
    extension = splitext(url)[1]
    async with ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise web.HTTPBadRequest(
                    reason='Could not download: %s, %s' % (
                        url, resp.reason))

            with NamedTemporaryFile(
                    delete=False, suffix=extension) as t:
                await run_in_executor(t.write)(await resp.read())
                return t.name


@asynccontextmanager
async def get_params(request):
    """
    """
    if request.method == 'POST':
        data = await request.post()

    else:
        data = request.query

    path, file, url = data.get('path'), data.get('file'), data.get('url')
    format = data.get('format', DEFAULT_FORMAT)
    width = int(data.get('width', WIDTH))
    height = int(data.get('height', HEIGHT))
    width, height = min(width, MAX_WIDTH), min(height, MAX_HEIGHT)
    cleanup = []

    try:
        if path:
            # TODO: sanitize this path, ensure it is rooted in FILE_ROOT
            path = normpath(path)
            path = pathjoin(FILE_ROOT, path)

        elif file:
            path = await upload(file)
            cleanup.append(path)

        elif url:
            path = await download(url)
            cleanup.append(path)

        else:
            raise web.HTTPBadRequest(reason='No path, file or url provided')

        if not isfile(path):
            raise web.HTTPNotFound()

        yield (data, path, format, width, height)

    finally:
        for path in cleanup:
            await run_in_executor(safe_delete)(path)


generate = run_in_executor(generate)


async def info(request):
    checks = [
        backend.check() for backend in Backend.backends.values()
    ]
    if not all(checks):
        raise web.HTTPServiceUnavailable()

    return web.Response(text="OK")


class DeleteFileResponse(web.FileResponse):
    async def prepare(self, *args, **kwargs):
        try:
            return await super(DeleteFileResponse, self).prepare(
                *args, **kwargs)

        finally:
            if is_temp(str(self._path)):
                await run_in_executor(safe_delete)(self._path)


async def preview(request):
    async with get_params(request) as params:
        data, path, format, width, height = params

        try:
            try:
                path = await generate(path, format, width, height)
                response = DeleteFileResponse(path, status=200)
                response.headers['Cache-Control'] = 'max-age=600, public'

            except Exception as e:
                # NOTE: we send 203 to indicate that the content is not exactly
                # what was requested. This helps our tools / tests determine
                # if an error occurred. We also disable caching in the case of
                # an error response.
                LOGGER.exception(e)
                path = 'images/error.png'
                if isinstance(e, UnsupportedTypeError):
                    path = 'images/unsupported.png'
                path = await generate(path, format, width, height)
                response = DeleteFileResponse(path, status=203)

        except Exception as e:
            LOGGER.exception(e)
            raise web.HTTPInternalServerError(reason='Unrecoverable error')

        response.content_type = 'image/png'

        return response


def main():
    app = web.Application(
        client_max_size=MAX_UPLOAD, middlewares=[normalize_path_middleware()])
    setup_metrics(app, 'preview-server')
    app.add_routes([web.get('/', info)])
    app.add_routes(
        [web.post('/preview/', preview), web.get('/preview/', preview)])

    loop = uvloop.new_event_loop()
    asyncio.set_event_loop(loop)

    # TODO: probably a better way...
    loop.call_soon(run_in_executor(functools.partial(cleanup, loop)))

    # TODO: figure out how to wait for pending requests before exiting.
    # TODO: port from command line.
    web.run_app(app, port=3000, handle_signals=True)


main()
