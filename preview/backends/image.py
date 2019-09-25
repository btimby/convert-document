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
        with Image(width=width, height=height) as bg:
            with Image(filename=path, resolution=300) as s:
                d = Image(s.sequence[0])
                d.background_color = Color("white")
                d.alpha_channel = 'remove'
                d.transform(resize='%ix%i>' % (width, height))
                left = (bg.width - d.width) // 2
                top = (bg.height - d.height) // 2
                bg.composite(d, left, top, operator='over')
                return bg.make_blob('png')
