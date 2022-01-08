import logging

from io import BytesIO
from tempfile import NamedTemporaryFile

import ghostscript

from preview.backends.base import BaseBackend
from preview.backends.image import ImageBackend
from preview.utils import log_duration
from preview.models import PathModel
from preview.errors import InvalidPageError


LOGGER = logging.getLogger(__name__)


def _calc_dpi(width, height):
    "Calculate DPI necessary to produce a clear image of requested resolution"
    # Since we are dealing with documents, I am going to assume a paper size of
    # 8.5 x 11. However, we will use the maximum DPI for either dimension, this
    # minimizes the risk of "stretching" the image in one dimension if the size
    # is something else. We return dpi as a tuple so that this function can
    # calculate the dpi separately for each dimension if desired.
    dpi = max(width / 8.5, height / 11)
    # Round to multiple of 144 and then halve.
    dpi = ((dpi // 144 * 144) + 144) // 2
    return (dpi, dpi)


def _run_ghostscript(obj, device, outfile, pages=(1, 1)):
    # An empty file is apparently a valid file as far as ghostscript is
    # concerned. However, it produces an empty image file, which causes
    # errors downline. Detect an empty file and raise here.
    if not obj.src.size:
        raise Exception('Invalid file size 0')

    args = [
        b'-dNOPAUSE', b'-dBATCH', b'-dSAFER',
        b'-sDEVICE=%s' % bytes(device, 'utf8'),
    ]

    if pages != (0, 0):
        args.extend([
            b'-dFirstPage=%i' % pages[0], b'-dLastPage=%i' % pages[1]])

    # Calculate suitable DPI...
    dpi = _calc_dpi(obj.width, obj.height)
    LOGGER.debug('Converting PDF to image with DPI of %ix%i', *dpi)

    args.extend([
        b'-r%ix%i' % dpi,
        b'-o', bytes(outfile, 'utf8'),
        bytes(obj.src.path, 'utf8'),
    ])

    LOGGER.debug('Ghostscript args: %s', args)

    # TODO: fix this lib. You cannot clean up the object with try / except if
    # __init__() raises.
    output = BytesIO()
    with ghostscript.Ghostscript(stdout=output, stderr=output, *args):
        pass

    # Checkout output for errors that require special handling.
    output = output.getvalue()
    if pages != (0, 0) and (b'FirstPage' in output or b'LastPage' in output):
        raise InvalidPageError(pages)


class PdfBackend(BaseBackend):
    name = 'pdf'
    extensions = [
        # https://www.file-extensions.org/ghostscript-file-extensions
        'pdf', 'eps', 'ps', 'pm',
    ]

    @log_duration
    def _preview_pdf(self, obj, pages=None):
        # NOTE: pages can be overridden since the pdf backend is called by the
        # office backend. In that case pages needs to be overidden.
        if pages is None:
            pages = obj.args.get('pages')

        with NamedTemporaryFile(delete=False, suffix='.pdf') as t:
            _run_ghostscript(
                obj, 'pdfwrite', t.name, pages=pages)
            obj.dst = PathModel(t.name)

    @log_duration
    def _preview_image(self, obj, pages=None):
        # NOTE: pages can be overridden since the pdf backend is called by the
        # office backend. In that case pages needs to be overidden.
        if pages is None:
            pages = obj.args.get('pages')

        # We can only convert one page to an image, choose the first.
        if pages != (1, 1):
            pages = (pages[0], pages[0])

        with NamedTemporaryFile(delete=False, suffix='.png') as t:
            _run_ghostscript(
                obj, 'png16m', t.name, pages=pages)
            obj.src = PathModel(t.name)

        ImageBackend()._preview_image(obj, pages=(1, 1))
