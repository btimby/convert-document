import os
import shutil
import logging
import asyncio
import mimetypes
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


async def _doc2pdf(path, timeout):
    extension = os.path.splitext(path)[1]
    mimetype = mimetypes.guess_type(path)
    filters = list(FORMATS.get_filters(extension, mimetype))

    with NamedTemporaryFile(delete=False, suffix=extension) as t:
        t.close()
        CONVERTER.convert_file(path, t.name, filters, timeout=timeout)
        path = t.name

    if os.path.getsize(path) == 0:
        raise ConversionFailure("Could not convert.")

    return path


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

    try:
        # Determine path or upload.
        if upload:
            extension = os.path.splitext(upload.filename)[1]
            with NamedTemporaryFile(delete=False, suffix=extension) as t:
                shutil.copyfileobj(upload.file, t, BUFFER_SIZE)
                path = t.name

        elif path:
            extension = os.path.splitext(path)[1]

        else:
            raise ConversionFailure('No file or path provided')

        # Determine file type (doc or image)
        if extension in FORMATS.extensions:
            # Convert doc to image.
            path = await _doc2pdf(path, timeout)
            asyncio.sleep(0)

        # Resize image and return.
        blob = await _thumbnail(path, width, height)
        asyncio.sleep(0)

        response = web.StreamResponse()
        response.content_length = len(blob)
        response.content_type = 'image/jpeg'
        await response.prepare(request)
        await response.write(blob)

        return response

    except ConversionFailure as exc:
        LOGGER.info("Failed to convert", exc_info=True)
        return web.Response(text=str(exc), status=400)

    except Exception as exc:
        LOGGER.exception(exc)
        CONVERTER.terminate()
        return web.Response(text=str(exc), status=500)


app = web.Application(client_max_size=MAX_UPLOAD)
app.add_routes([web.get('/', info)])
app.add_routes([web.post('/convert', convert)])
web.run_app(app, port=3000)
