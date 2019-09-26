import os
import logging

from os.path import normpath, splitext, isfile
from os.path import join as pathjoin

import uvloop
from aiohttp import web, ClientSession
from aiohttp.web_middlewares import normalize_path_middleware
from aiohttp_prometheus import setup_metrics

from tempfile import NamedTemporaryFile

from preview.preview import BACKENDS
from preview.utils import run_in_executor, log_duration
from preview.preview import generate


# Limits
MEGABYTE = 1024 * 1024
BUFFER_SIZE = 8 * MEGABYTE
MAX_UPLOAD = 800 * MEGABYTE

# Configuration
FILE_ROOT = os.environ.get('FILE_ROOT', '/mnt/files')
WIDTH = os.environ.get('WIDTH', 320)
HEIGHT = os.environ.get('HEIGHT', 240)
MAX_WIDTH = os.environ.get('MAX_WIDTH', 800)
MAX_HEIGHT = os.environ.get('MAX_HEIGHT', 600)
DEFAULT_FORMAT = os.environ.get('DEFAULT_FORMAT', 'image')
LOGLEVEL = getattr(logging, os.environ.get('LOGLEVEL', 'WARNING'))
HTTP_LOGLEVEL = getattr(logging, os.environ.get('HTTP_LOGLEVEL', 'INFO'))

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

    if path:
        # TODO: sanitize this path, ensure it is rooted in FILE_ROOT
        path = normpath(path)
        path = pathjoin(FILE_ROOT, path)

    elif file:
        path = await upload(file)

    elif url:
        path = await download(url)

    else:
        raise web.HTTPBadRequest(reason='No path, file or url provided')

    if not isfile(path):
        raise web.HTTPNotFound()

    return data, path, format, width, height


generate = run_in_executor(generate)


async def info(request):
    checks = []
    for backend in BACKENDS:
        checks.append(backend.check())

    if not all(checks):
        raise web.HTTPServiceUnavailable()

    return web.Response(text="OK")


async def preview(request):
    try:
        data, path, format, width, height = await get_params(request)
        blob = await generate(path, format, width, height)

        response = web.StreamResponse()
        response.content_length = len(blob)
        response.content_type = 'image/png'
        response.headers['Cache-Control'] = 'max-age=600, public'
        await response.prepare(request)
        await response.write(blob)

        return response

    except Exception as e:
        LOGGER.exception(e)
        raise web.HTTPInternalServerError()


def main():
    app = web.Application(
        client_max_size=MAX_UPLOAD, middlewares=[normalize_path_middleware()])
    setup_metrics(app, 'preview-server')
    app.add_routes([web.get('/', info)])
    app.add_routes(
        [web.post('/preview/', preview), web.get('/preview/', preview)])

    # TODO: port from command line.
    # TODO: figure out how to wait for pending requests before exiting.
    asyncio.set_event_loop(uvloop.new_event_loop())
    web.run_app(app, port=3000, handle_signals=True)


main()
