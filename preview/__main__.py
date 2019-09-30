import os
import logging
import functools
import pathlib

from os.path import normpath, splitext, isfile
from os.path import join as pathjoin

from tempfile import NamedTemporaryFile

import uvloop
import asyncio
from aiohttp import web, ClientSession
from aiohttp.web_middlewares import normalize_path_middleware
from async_generator import asynccontextmanager

from preview.preview import Backend
from preview.utils import run_in_executor, log_duration, safe_delete
from preview.preview import generate, UnsupportedTypeError
from preview.storage import is_temp, BASE_PATH
from preview.metrics import metrics_handler, metrics_middleware


# Limits
MEGABYTE = 1024 * 1024
BUFFER_SIZE = 8 * MEGABYTE
MAX_UPLOAD = 800 * MEGABYTE

# Configuration
CACHE_CONTROL = os.environ.get('PVS_CACHE_CONTROL')
FILE_ROOT = os.environ.get('PVS_FILES', '/mnt/files')
WIDTH = os.environ.get('PVS_WIDTH', 320)
HEIGHT = os.environ.get('PVS_HEIGHT', 240)
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
    return web.Response(text="OK")


class DeleteFileResponse(web.FileResponse):
    async def prepare(self, *args, **kwargs):
        try:
            return await super(DeleteFileResponse, self).prepare(
                *args, **kwargs)

        finally:
            await run_in_executor(safe_delete)(self._path)


async def preview(request):
    async with get_params(request) as params:
        data, path, format, width, height = params

        status = 200
        try:
            try:
                path = await generate(path, format, width, height)

            except Exception as e:
                # NOTE: we send 203 to indicate that the content is not exactly
                # what was requested. This helps our tools / tests determine
                # if an error occurred. We also disable caching in the case of
                # an error response.
                LOGGER.exception(e)
                path = 'images/error.png'
                if isinstance(e, UnsupportedTypeError):
                    path = 'images/unsupported.png'
                status, path = 203, await generate(path, format, width, height)

            # nginx can't serve our temp files.
            if is_temp(str(path)):
                response = DeleteFileResponse(path, status=status)

            # it can serve stored files.
            elif X_ACCEL_REDIR:
                response = web.Response()
                response.headers['X-Accel-Redirect'] = str(pathlib.Path(
                    X_ACCEL_REDIR).joinpath(path.relative_to(BASE_PATH)))

            else:
                response = web.FileResponse(path, status=200)

            # Don't cache error responses.
            if status == 200 and CACHE_CONTROL:
                max_age = 60 * int(CACHE_CONTROL)
                response.headers['Cache-Control'] = \
                    'max-age=%i, public' % max_age

        except Exception as e:
            LOGGER.exception(e)
            raise web.HTTPInternalServerError(reason='Unrecoverable error')

        response.content_type = 'image/png'
        return response


def main():
    if GID:
        os.setgid(int(GID))
    if UID:
        os.setuid(int(UID))

    app = web.Application(
        client_max_size=MAX_UPLOAD, middlewares=[
            normalize_path_middleware(), metrics_middleware()
            ])

    app.add_routes([web.get('/', info)])
    app.add_routes([
        web.post('/preview/', preview),
        web.get('/preview/', preview)])
    app.add_routes([web.get('/metrics/', metrics_handler)])

    loop = uvloop.new_event_loop()
    asyncio.set_event_loop(loop)

    # TODO: figure out how to wait for pending requests before exiting.
    web.run_app(app, port=PORT)


main()
