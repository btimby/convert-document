import os
import shutil
import logging
import asyncio
import mimetypes

from subprocess import Popen, PIPE

from aiohttp import web
from tempfile import NamedTemporaryFile
from wand.image import Image, Color

from converter import FORMATS, PdfConverter
from converter import ConversionFailure


logging.basicConfig(level=logging.DEBUG)
logging.getLogger('aiohttp').setLevel(logging.WARNING)


MEGABYTE = 1024 * 1024
BUFFER_SIZE = 8 * MEGABYTE
MAX_UPLOAD = 800 * MEGABYTE
LOGGER = logging.getLogger('convert')
CONVERTER = PdfConverter()
VIDEO_EXTENSIONS = (
    '.avi', '.mpg', '.mov',
)


async def _doc2pdf(doc, timeout):
    extension = os.path.splitext(doc)[1]
    mimetype = mimetypes.guess_type(doc)
    # TODO: filters should be determined by CONVERTER, pass in mimetype
    # instead.
    filters = list(FORMATS.get_filters(extension, mimetype))

    with NamedTemporaryFile(delete=False, suffix=extension) as t:
        CONVERTER.convert_file(doc, t.name, filters, timeout=timeout)
        return t.name


async def _vid2img(path):
    # TODO: ffmpeg can operate on stdin / stdout, so we can do zero-copy.
    # TODO: we could make a motion png.
    with NamedTemporaryFile(delete=False, suffix='.jpg') as t:
        pass

    cmd = ['ffmpeg', '-ss', None, '-i', path, '-frames:v', '1', '-y', t.name]

    # Try to grab a frame at various offsets.
    for offset in ('00:00:20', '00:00:10', '00:00:01'):
        cmd[2] = offset
        process = Popen(cmd, stderr=PIPE)
        stderr = process.communicate()[1]
        LOGGER.info(stderr)
        if b'Output file is empty' not in stderr:
            # Seems like we got a frame.
            break

    else:
        raise ConversionFailure('Could not grab a frame')

    return t.name


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
    data = await request.post()

    path, upload = data.get('path'), data.get('file')
    width = int(data.get('width', 640))
    height = int(data.get('height', 480))
    timeout = int(data.get('timeout', 300))

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
        if extension in FORMATS.extensions:
            # Convert doc to image.
            path = await _doc2pdf(path, timeout)
            cleanup.append(path)

        elif extension in VIDEO_EXTENSIONS:
            LOGGER.info('video')
            path = await _vid2img(path)
            cleanup.append(path)

        await asyncio.sleep(0)

        # Resize image and return.
        blob = await _thumbnail(path, width, height)
        await asyncio.sleep(0)

        response = web.StreamResponse()
        response.content_length = len(blob)
        response.content_type = 'image/jpeg'
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


app = web.Application(client_max_size=MAX_UPLOAD)
app.add_routes([web.get('/', info)])
app.add_routes([web.post('/convert', convert)])
web.run_app(app, port=3000)
