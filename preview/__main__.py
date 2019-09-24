import os
import shutil
import logging

from os.path import normpath, splitext, isfile
from os.path import join as pathjoin

import aiofiles
from aiofiles.threadpool import wrap as aiofiles_wrap
from aiohttp import web, ClientSession
from aiohttp.web_middlewares import normalize_path_middleware

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
LOGLEVEL = getattr(logging, os.environ.get('LOGLEVEL', 'INFO'))
HTTP_LOGLEVEL = getattr(logging, os.environ.get('HTTP_LOGLEVEL', 'INFO'))

LOGGER = logging.getLogger()
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(LOGLEVEL)
logging.getLogger('aiohttp').setLevel(HTTP_LOGLEVEL)


@log_duration
async def upload(upload):
    extension = splitext(upload.filename)[1]
    with NamedTemporaryFile(delete=False, suffix=extension) as t:
        t = aiofiles.open(t.name)
        f = aiofiles_wrap(upload.file)
        while True:
            data = await f.read(BUFFER_SIZE)
            if not data:
                break
            await t.write(data)
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
                f = await aiofiles.open(t.name, mode='wb')
                await f.write(await resp.read())
                await f.close()
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
    # Find the office backend and perform a health check. This is used by
    # Circus to determine if LibreOffice should be restarted.
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
        response.headers['Cache-Control'] = 'max-age=300, public'
        await response.prepare(request)
        await response.write(blob)

        return response

    except Exception as e:
        LOGGER.exception(e)
        raise web.HTTPInternalServerError()


def main():
    app = web.Application(
        client_max_size=MAX_UPLOAD, middlewares=[normalize_path_middleware()])
    app.add_routes([web.get('/', info)])
    app.add_routes(
        [web.post('/preview/', preview), web.get('/preview/', preview)])

    # TODO: port from command line.
    web.run_app(app, port=3000)


main()
