import logging
import tempfile

from io import BytesIO

import img2pdf

from wand.image import Image, Color

from preview.backends.base import BaseBackend
from preview.utils import log_duration
from preview.models import PathModel


LOGGER = logging.getLogger(__name__)


def resize_image(path, width, height):
    with Image(width=width, height=height) as bg:
        # Resize our input image.
        with Image(filename=path, resolution=300) as s:
            d = Image(s.sequence[0])
            d.background_color = Color("white")
            d.alpha_channel = 'remove'
            d.transform(resize='%ix%i>' % (width, height))
            # Offset input image on top of background.
            left = (bg.width - d.width) // 2
            top = (bg.height - d.height) // 2
            bg.composite(d, left, top, operator='over')
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gif') as t:
            bg.save(filename=t.name)
            return t.name


def convert(path):
    data = BytesIO()
    with Image(filename=path, resolution=300) as img:
        img.background_color = Color("white")
        img.alpha_channel = 'deactivate'
        img.format = 'png'
        img.save(file=data)

    data.seek(0)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as t:
        img2pdf.convert(data, outputstream=t)
        return t.name


class ImageBackend(BaseBackend):
    name = 'image'
    extensions = [
        'bmp', 'dcx', 'gif', 'jpg', 'jpeg', 'png', 'psd', 'tiff', 'tif', 'xbm',
        'xpm'
    ]
    formats = [
        'image', 'pdf',
    ]

    @log_duration
    def _preview(self, obj):
        if obj.format == 'image':
            path = resize_image(obj.src.path, obj.width, obj.height)
            obj.dst = PathModel(path)

        elif obj.format == 'pdf':
            path = convert(obj.src.path)
            obj.dst = PathModel(path)
