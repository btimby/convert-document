import os
import shutil
import logging
import asyncio
import mimetypes
import time
import functools
import threading

from os.path import join as pathjoin
from subprocess import Popen, PIPE

from aiohttp import web
from aiohttp.web_middlewares import normalize_path_middleware

from tempfile import NamedTemporaryFile
from wand.image import Image, Color
import ghostscript

from converter import FORMATS, PdfConverter
from converter import ConversionFailure


logging.basicConfig(level=logging.DEBUG)
logging.getLogger('aiohttp').setLevel(logging.INFO)


MEGABYTE = 1024 * 1024
BUFFER_SIZE = 8 * MEGABYTE
MAX_UPLOAD = 800 * MEGABYTE
LOGGER = logging.getLogger('convert')
CONVERTER = PdfConverter()
VIDEO_EXTENSIONS = (
    '.avi', '.mpg', '.mov',
)
# TODO: Take this from config.
FILE_ROOT = os.environ.get('FILE_ROOT', '/mnt/files')
GS_LOCK = threading.Lock()


def run_in_executor(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, functools.partial(f, *args, **kwargs))
    return inner


@run_in_executor
def _doc2pdf(doc, timeout):
    extension = os.path.splitext(doc)[1]
    mimetype = mimetypes.guess_type(doc)

    # TODO: filters should be determined by CONVERTER, pass in mimetype
    # instead.
    filters = list(FORMATS.get_filters(extension[1:], mimetype))
    LOGGER.debug(filters)

    with NamedTemporaryFile(delete=False, suffix='.pdf') as t:
        CONVERTER.convert_file(doc, t.name, filters, timeout=timeout)
        return t.name


@run_in_executor
def _pdf2img(path):
    with NamedTemporaryFile(suffix='.png') as t:
        args = [
            b'-dFirstPage=1', b'-dLastPage=1',
            b'-dNOPAUSE', b'-dBATCH', b'-sDEVICE=png16m',
            b'-sOutputFile=%s' % bytes(t.name, 'utf8'), bytes(path, 'utf8'),
        ]
        with GS_LOCK:
            ghostscript.Ghostscript(*args)
        return t.read()


@run_in_executor
def _vid2img(path):
    # TODO: ffmpeg can operate on stdin / stdout, so we can do zero-copy.
    # TODO: we could make a motion png.
    with NamedTemporaryFile(suffix='.apng') as t:
        cmd = [
            'ffmpeg', '-y', '-ss', '00:00', '-i', path, '-i',
            'images/film-overlay.png', '-filter_complex',
            '[0:v]scale=320:240[bg]; [1:v]scale=320x240[ovl];[bg][ovl]overlay'
            '=0:0', '-plays', '0', '-t', '5', '-r', '1', t.name
        ]
        LOGGER.debug(' '.join(cmd))
        process = Popen(cmd, stderr=PIPE)
        _, stderr = process.communicate()
        LOGGER.info(stderr)
        if b'Output file is empty' in stderr:
            # Seems like we got a frame.
            raise Exception()
        return t.read()


async def _thumbnail(path, width, height):
    with Image(filename=path, resolution=300) as s:
        d = Image(s.sequence[0])
        d.background_color = Color("white")
        d.alpha_channel = 'remove'
        d.transform(resize='%ix%i>' % (width, height))
        return d.make_blob('jpeg')


async def info(request):
    return web.Response(text="OK")


async def convert(request):
    LOGGER.info('method: %s', request.method)

    if request.method == 'POST':
        data = await request.post()

    else:
        data = request.query

    path, upload = data.get('path'), data.get('file')
    width = int(data.get('width', 640))
    height = int(data.get('height', 480))
    timeout = int(data.get('timeout', 300))

    if request.method == 'GET':
        path = pathjoin(FILE_ROOT, path)
        LOGGER.info('Ajusted path: %s', path)

    # NOTE: Everything in this list will be deleted. It is important not to
    # place given path in here, only our temporary files.
    cleanup = []

    try:
        # Determine path or upload.
        if upload:
            extension = os.path.splitext(upload.filename)[1]
            with NamedTemporaryFile(delete=False, suffix=extension) as t:
                shutil.copyfileobj(upload.file, t, BUFFER_SIZE)
            path = t.name
            cleanup.append(path)

            await asyncio.sleep(0)

        elif path:
            extension = os.path.splitext(path)[1]

        else:
            raise ConversionFailure('No file or path provided')

        LOGGER.info('extension: %s', extension)

        # Determine file type (doc or image)
        start = time.time()
        # TODO: file type sniffing is b0rk3d. For example, extension .docx is
        # not in FORMATS.extensions, nor VIDEO_EXTENSIONS, so it is handled by
        # Wand, this surprisingly calls out to uno (so it works). But it
        # invokes soffice for each request is ~4s. Using a daemon is much
        # faster at ~100-1000ms.
        if extension == '.pdf':
            LOGGER.info('pdf')
            blob = await _pdf2img(path)

        elif extension[1:] in FORMATS.extensions:
            LOGGER.info('doc')
            try:
                path = await _doc2pdf(path, timeout)
                LOGGER.debug('PDF is %i bytes' % os.path.getsize(path))
                blob = await _pdf2img(path)

            finally:
                LOGGER.debug('Conversion took: %ss', time.time() - start)
                LOGGER.debug('Doc converted to: %s', path)

            cleanup.append(path)

        elif extension in VIDEO_EXTENSIONS:
            LOGGER.info('video')
            try:
                blob = await _vid2img(path)

            finally:
                LOGGER.debug('Framegrab took: %ss', time.time() - start)
                LOGGER.debug('Video converted to: %s', path)
                LOGGER.debug('Frame %i bytes', len(blob))

        else:
            # Resize image and return.
            start = time.time()
            try:
                blob = await _thumbnail(path, width, height)

            finally:
                LOGGER.debug('Thumbnail took: %ss', time.time() - start)

        await asyncio.sleep(0)

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

    finally:
        for path in cleanup:
            try:
                os.remove(path)
            except OSError as e:
                LOGGER.exception(e)


app = web.Application(client_max_size=MAX_UPLOAD, middlewares=[normalize_path_middleware()])
app.add_routes([web.get('/', info)])
app.add_routes([web.post('/convert/', convert), web.get('/convert/', convert)])
web.run_app(app, port=3000)
