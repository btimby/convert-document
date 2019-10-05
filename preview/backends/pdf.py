import logging

from tempfile import NamedTemporaryFile

import ghostscript

from preview.backends.base import BaseBackend
from preview.backends.image import ImageBackend
from preview.utils import log_duration
from preview.models import PathModel


LOGGER = logging.getLogger(__name__)


def _run_ghostscript(obj, device, outfile):
    # An empty file is apparently a valid file as far as ghostscript is
    # concerned. However, it produces an empty image file, which causes
    # errors download. Detect an empty file and raise here.
    if not obj.src.size:
        raise Exception('Invalid file size 0')

    args = [
        b'-dFirstPage=1', b'-dLastPage=1',
        b'-dNOPAUSE', b'-dBATCH', b'-dSAFER', b'-q',
        b'-sDEVICE=%s' % device.encode('utf8'),
        b'-sOutputFile=%s' % outfile.encode('utf8'),
        obj.src.path.encode('utf8'),
    ]

    # TODO: fix this bullshit lib. You cannot clean up the object with
    # try / except if __init__() raises.
    with ghostscript.Ghostscript(*args):
        pass


class PdfBackend(BaseBackend):
    name = 'pdf'
    extensions = [
        'pdf', 'eps', 'ps',
    ]

    @log_duration
    def _preview_pdf(self, obj):
        with NamedTemporaryFile(delete=False, suffix='.pdf') as t:
            _run_ghostscript(obj, 'pdfwriter', t.name)
            obj.dst = PathModel(t.name)

    @log_duration
    def _preview_image(self, obj):
        with NamedTemporaryFile(delete=False, suffix='.png') as t:
            _run_ghostscript(obj, 'png16m', t.name)
            obj.src = PathModel(t.name)

        ImageBackend()._preview_image(obj)
