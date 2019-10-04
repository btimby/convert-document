import logging

from tempfile import NamedTemporaryFile

import ghostscript

from preview.backends.base import BaseBackend
from preview.backends.image import ImageBackend
from preview.utils import log_duration
from preview.models import PathModel


LOGGER = logging.getLogger(__name__)


class PdfBackend(BaseBackend):
    name = 'pdf'
    extensions = [
        'pdf', 'eps', 'ps',
    ]
    formats = [
        'image', 'pdf',
    ]

    @log_duration
    def _preview(self, obj):
        # An empty file is apparently a valid file as far as ghostscript is
        # concerned. However, it produces an empty image file, which causes
        # errors download. Detect an empty file and raise here.
        if not obj.src.size:
            raise Exception('Invalid file size 0')

        suffix = '.pdf' if obj.format == 'pdf' else '.png'
        with NamedTemporaryFile(delete=False, suffix=suffix) as t:
            args = [
                b'-dFirstPage=1', b'-dLastPage=1',
                b'-dNOPAUSE', b'-dBATCH', b'-dSAFER', b'-q',
            ]

            if obj.format == 'pdf':
                args.append(b'-sDEVICE=png16m')

            else:
                args.append(b'-sDEVICE=pdfwriter')

            args.extend([
                b'-sOutputFile=%s' % bytes(t.name, 'utf8'),
                bytes(obj.src.path, 'utf8'),
            ])

            # TODO: fix this bullshit lib. You cannot clean up the object with
            # try / except if __init__() raises.
            with ghostscript.Ghostscript(*args):
                pass

            if obj.format == 'pdf':
                obj.dst = PathModel(t.name)
                return

            else:
                obj.src = PathModel(t.name)

        ImageBackend().preview(obj)
