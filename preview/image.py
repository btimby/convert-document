import logging

from time import time

from wand.image import Image, Color


LOGGER = logging.getLogger(__name__)


def preview_image(path, width, height):
    start = time()
    try:
        with Image(filename=path, resolution=300) as s:
            d = Image(s.sequence[0])
            d.background_color = Color("white")
            d.alpha_channel = 'remove'
            d.transform(resize='%ix%i>' % (width, height))
            return d.make_blob('png')

    finally:
        LOGGER.info('preview_image(%s) took: %ss', path, time() - start)
