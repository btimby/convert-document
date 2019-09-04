import logging

from time import time
from threading import Lock
from tempfile import NamedTemporaryFile

import ghostscript

from image import preview_image


GS_LOCK = Lock()
LOGGER = logging.getLogger(__name__)


def preview_pdf(path, width, height):
    start = time()
    with NamedTemporaryFile(suffix='.png') as t:
        args = [
            b'-dFirstPage=1', b'-dLastPage=1',
            b'-dNOPAUSE', b'-dBATCH', b'-sDEVICE=png16m',
            b'-sOutputFile=%s' % bytes(t.name, 'utf8'), bytes(path, 'utf8'),
        ]

        try:
            with GS_LOCK:
                ghostscript.Ghostscript(*args)

        finally:
            LOGGER.info('preview_pdf(%s) took %ss', path, time() - start)

        return preview_image(t.name, width, height)
