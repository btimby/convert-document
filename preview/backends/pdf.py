import logging

from tempfile import NamedTemporaryFile

import ghostscript

from preview.backends.base import BaseBackend
from preview.backends.image import ImageBackend
from preview.utils import log_duration
from preview.models import PathModel


LOGGER = logging.getLogger(__name__)


def _run_ghostscript(obj, device, outfile, pages=(1, 1)):
    # An empty file is apparently a valid file as far as ghostscript is
    # concerned. However, it produces an empty image file, which causes
    # errors download. Detect an empty file and raise here.
    if not obj.src.size:
        raise Exception('Invalid file size 0')

    args = []
    if pages != (0, 0):
        args.extend([
            b'-dFirstPage=%i' % pages[0], b'-dLastPage=%i' % pages[1]])

    args.extend([
        b'-dNOPAUSE', b'-dBATCH', b'-dSAFER', b'-q',
        b'-sDEVICE=%s' % bytes(device, 'utf8'),
        b'-sOutputFile=%s' % bytes(outfile, 'utf8'),
        bytes(obj.src.path, 'utf8'),
    ])

    LOGGER.debug('Ghostscript args: %s', args)

    # TODO: fix this lib. You cannot clean up the object with try / except if
    # __init__() raises.
    with ghostscript.Ghostscript(*args):
        pass


class PdfBackend(BaseBackend):
    name = 'pdf'
    extensions = [
        'pdf', 'eps', 'ps',
    ]

    @log_duration
    def _preview_pdf(self, obj):
        pages = obj.args.get('pages')

        with NamedTemporaryFile(delete=False, suffix='.pdf') as t:
            _run_ghostscript(obj, 'pdfwrite', t.name, pages=pages)
            obj.dst = PathModel(t.name)

    @log_duration
    def _preview_image(self, obj):
        with NamedTemporaryFile(delete=False, suffix='.png') as t:
            _run_ghostscript(obj, 'png16m', t.name)
            obj.src = PathModel(t.name)

        ImageBackend()._preview_image(obj)
