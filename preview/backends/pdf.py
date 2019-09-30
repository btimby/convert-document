import shutil
import logging

from threading import Lock
from tempfile import NamedTemporaryFile

import ghostscript

from preview.backends.base import BaseBackend
from preview.backends.image import ImageBackend
from preview.metrics import CONVERSIONS, CONVERSION_ERRORS
from preview.utils import log_duration, get_extension


LOGGER = logging.getLogger(__name__)


class PdfBackend(BaseBackend):
    extensions = [
        'pdf', 'eps', 'ps',
    ]

    @log_duration
    def preview(self, path, width, height):
        extension = get_extension(path)
        try:
            with NamedTemporaryFile(suffix='.png') as t:
                args = [
                    b'-dFirstPage=1', b'-dLastPage=1',
                    b'-dNOPAUSE', b'-dBATCH', b'-dSAFER', b'-sDEVICE=png16m',
                    b'-q', b'-sOutputFile=%s' % bytes(t.name, 'utf8'),
                    bytes(path, 'utf8'),
                ]

                with CONVERSIONS.labels('pdf', extension).time():
                    with ghostscript.Ghostscript(*args):
                        pass

                return ImageBackend().preview(t.name, width, height)

        except:
            CONVERSION_ERRORS.labels('pdf', extension).inc()
            raise
