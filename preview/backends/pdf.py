import shutil
import logging

from threading import Lock
from tempfile import NamedTemporaryFile

import ghostscript

from preview.backends.base import BaseBackend
from preview.backends.image import ImageBackend
from preview.utils import log_duration


GS_LOCK = Lock()
LOGGER = logging.getLogger(__name__)


class PdfBackend(BaseBackend):
    extensions = [
        'pdf', 'eps', 'ps',
    ]

    @log_duration
    def preview(self, path, width, height):
        with NamedTemporaryFile(suffix='.png') as t:
            args = [
                b'-dFirstPage=1', b'-dLastPage=1',
                b'-dNOPAUSE', b'-dBATCH', b'-dSAFER', b'-sDEVICE=png16m',
                b'-q', b'-sOutputFile=%s' % bytes(t.name, 'utf8'),
                bytes(path, 'utf8'),
            ]

            # TODO: gs can be configured with GS_THREADSAFE defined.
            #
            # https://www.ghostscript.com/doc/current/API.htm
            #
            # If our version of gs has this flag, then we _should_ be able to
            # do away with the lock. This is a source of contention as it is
            # used for PDF files as well as office documents.
            with GS_LOCK:
                try:
                    gs = ghostscript.Ghostscript(*args)

                finally:
                    gs.exit()

            return ImageBackend().preview(t.name, width, height)
