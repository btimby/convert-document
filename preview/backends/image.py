import logging
import tempfile

from wand.image import Image, Color

from preview.backends.base import BaseBackend
from preview.utils import log_duration, get_extension
from preview.metrics import CONVERSIONS, CONVERSION_ERRORS


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
            with tempfile.NamedTemporaryFile(delete=False,
                                             suffix='.png') as t:
                bg.save(filename=t.name)
                return t.name


class ImageBackend(BaseBackend):
    extensions = [
        'bmp', 'dcx', 'gif', 'jpg', 'jpeg', 'png', 'psd', 'tiff', 'tif', 'xbm',
        'xpm'
    ]

    @log_duration
    def preview(self, path, width, height):
        extension = get_extension(path)
        try:
            with CONVERSIONS.labels('image', extension).time():
                # Create a transparent background image of the requested size.
                return resize_image(path, width, height)

        except:
            CONVERSION_ERRORS.labels('image', extension).inc()
            raise
