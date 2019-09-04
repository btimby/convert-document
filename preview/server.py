import os
import shutil
import logging
import asyncio
import time
import functools
import threading

from os.path import join as pathjoin

from aiohttp import web
from aiohttp.web_middlewares import normalize_path_middleware

from tempfile import NamedTemporaryFile

from gs import preview_pdf
from soffice import preview_doc, FORMATS
from ffmpeg import preview_video
from image import preview_image


logging.basicConfig(level=logging.DEBUG)
logging.getLogger('aiohttp').setLevel(logging.INFO)


# Limits
MEGABYTE = 1024 * 1024
BUFFER_SIZE = 8 * MEGABYTE
MAX_UPLOAD = 800 * MEGABYTE

LOGGER = logging.getLogger(__name__)
VIDEO_EXTENSIONS = (
    '.avi', '.mpg', '.mov',
)

# Configuration
# TODO: Take this from config.
FILE_ROOT = os.environ.get('FILE_ROOT', '/mnt/files')
WIDTH = os.environ.get('WIDTH', 320)
HEIGHT = os.environ.get('HEIGHT', 240)
MAX_WIDTH = os.environ.get('MAX_WIDTH', 800)
MAX_HEIGHT = os.environ.get('MAX_HEIGHT', 600)


def run_in_executor(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, functools.partial(f, *args, **kwargs))
    return inner


async def info(request):
    return web.Response(text="OK")


async def _get_params(request):
    """
    """

    @run_in_executor
    def _upload(upload):
        extension = os.path.splitext(upload.filename)[1]
        with NamedTemporaryFile(delete=False, suffix=extension) as t:
            shutil.copyfileobj(upload.file, t, BUFFER_SIZE)
        return t.name

    if request.method == 'POST':
        data = await request.post()

    else:
        data = request.query

    path, upload = data.get('path'), data.get('file')
    width = int(data.get('width', WIDTH))
    height = int(data.get('height', HEIGHT))
    width, height = min(width, MAX_WIDTH), min(height, MAX_HEIGHT)

    if request.method == 'GET':
        path = pathjoin(FILE_ROOT, path)

    if upload:
        path = await _upload(upload)

    return data, path, width, height


@run_in_executor
def _preview(path, width, height):
    extension = os.path.splitext(path)

    if extension == '.pdf':
        return preview_pdf(path, width, height)

    elif extension[1:] in FORMATS.extensions:
        blob = preview_doc(path, width, height)

    elif extension in VIDEO_EXTENSIONS:
        return preview_video(path, width, height)

    else:
        # Resize image and return.
        return preview_image(path, width, height)


async def preview(request):
    try:
        data, path, width, height = await _get_params(request)
        blob = await _preview(path, width, height)

        response = web.StreamResponse()
        response.content_length = len(blob)
        response.content_type = 'image/png'
        response.headers['Cache-Control'] = 'max-age=300, public'
        await response.prepare(request)
        await response.write(blob)

        return response

    except ConversionFailure as e:
        LOGGER.info("Failed to convert", exc_info=True)
        return web.Response(text=str(e), status=400)

    except Exception as e:
        LOGGER.exception(e)
        CONVERTER.terminate()
        return web.Response(text=str(e), status=500)


def main():
    app = web.Application(
        client_max_size=MAX_UPLOAD, middlewares=[normalize_path_middleware()])
    app.add_routes([web.get('/', info)])
    app.add_routes([web.post('/preview/', preview), web.get('/preview/', preview)])
    web.run_app(app, port=3000)


if __name__ == '__main__':
    main()
