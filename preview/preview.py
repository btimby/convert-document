import logging
import pathlib

from os.path import getsize

from preview.utils import get_extension
from preview.backends.office import OfficeBackend
from preview.backends.image import ImageBackend
from preview.backends.video import VideoBackend
from preview.backends.pdf import PdfBackend
from preview.metrics import PREVIEWS, PREVIEW_SIZE_IN, PREVIEW_SIZE_OUT
from preview.config import FILE_ROOT
from preview import storage


LOGGER = logging.getLogger()
LOGGER.addHandler(logging.NullHandler())


class UnsupportedTypeError(Exception):
    pass


def _preview(be, obj):
    PREVIEW_SIZE_IN.labels(
        be.name, obj.extension).observe(obj.src.size)

    with PREVIEWS.labels(obj.extension, obj.width, obj.height).time():
        be.preview(obj)
        PREVIEW_SIZE_OUT.labels(
            be.name, obj.extension).observe(obj.src.size)


class Backend(object):
    backends = {
        tuple(obj.extensions): obj
        for obj in [
            OfficeBackend(), ImageBackend(), VideoBackend(), PdfBackend()]
    }

    @staticmethod
    def preview(obj):
        for extensions, be in Backend.backends.items():
            if obj.extension in extensions:
                return _preview(be, obj)

        raise UnsupportedTypeError('Unsupported file type: %s' % obj.extension)


def generate(obj):
    use_store = not obj.src.is_temp
    store_key = storage.make_key(obj)

    if use_store and storage.get(store_key, obj):
        return

    Backend.preview(obj)

    if use_store:
        storage.put(store_key, obj)
