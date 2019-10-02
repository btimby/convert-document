import logging

from os.path import getsize
from tempfile import NamedTemporaryFile

import ghostscript

from preview.backends.base import BaseBackend
from preview.backends.image import ImageBackend
from preview.utils import log_duration


LOGGER = logging.getLogger(__name__)


class PdfBackend(BaseBackend):
    name = 'pdf'
    extensions = [
        'pdf', 'eps', 'ps',
    ]

    @log_duration
    def _preview(self, path, width, height):
        # An empty file is apparently a valid file as far as ghostscript is
        # concerned. However, it produces an empty image file, which causes
        # errors download. Detect an empty file and raise here.
        if getsize(path) == 0:
            raise Exception('Invalid file size 0')

        with NamedTemporaryFile(suffix='.png') as t:
            args = [
                b'-dFirstPage=1', b'-dLastPage=1',
                b'-dNOPAUSE', b'-dBATCH', b'-dSAFER', b'-sDEVICE=png16m',
                b'-q', b'-sOutputFile=%s' % bytes(t.name, 'utf8'),
                bytes(path, 'utf8'),
            ]

            with ghostscript.Ghostscript(*args):
                pass

            return ImageBackend().preview(t.name, width, height)
