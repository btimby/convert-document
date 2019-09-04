import logging

from threading import Lock
from tempfile import NamedTemporaryFile

import ghostscript


GS_LOCK = Lock()
LOGGER = logging.getLogger(__name__)


def preview_pdf(path, width, height):
    with NamedTemporaryFile(suffix='.png') as t:
        args = [
            b'-dFirstPage=1', b'-dLastPage=1',
            b'-dNOPAUSE', b'-dBATCH', b'-sDEVICE=png16m',
            b'-sOutputFile=%s' % bytes(t.name, 'utf8'), bytes(path, 'utf8'),
        ]
        with GS_LOCK:
            ghostscript.Ghostscript(*args)

        return t.read()
