import logging

from wand.image import Image, Color

from preview.backends.base import BaseBackend
from preview.utils import log_duration


LOGGER = logging.getLogger(__name__)


class ImageBackend(BaseBackend):
    extensions = [
        'bmp', 'dcx', 'gif', 'jpg', 'jpeg', 'png', 'psd', 'tiff', 'tif', 'xbm',
        'xpm'
    ]

    @log_duration
    def preview(self, path, width, height):
        with Image(filename=path, resolution=300) as s:
            d = Image(s.sequence[0])
            d.background_color = Color("white")
            d.alpha_channel = 'remove'
            d.transform(resize='%ix%i>' % (width, height))
            return d.make_blob('png')
