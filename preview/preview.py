import logging
import pathlib

from os.path import getsize

from preview.utils import get_extension, run_in_executor
from preview.backends.office import OfficeBackend
from preview.backends.image import ImageBackend
from preview.backends.video import VideoBackend
from preview.backends.pdf import PdfBackend
from preview.metrics import PREVIEWS, PREVIEW_SIZE_IN, PREVIEW_SIZE_OUT
from preview.config import FILE_ROOT
from preview.errors import InvalidPageError
from preview import storage, icons


LOGGER = logging.getLogger()
LOGGER.addHandler(logging.NullHandler())


class UnsupportedTypeError(Exception):
    pass


def _preview(be, obj):
    PREVIEW_SIZE_IN.labels(
        be.name, obj.extension, obj.format).observe(obj.src.size)

    with PREVIEWS.labels(obj.extension, obj.format).time():
        be.preview(obj)
        PREVIEW_SIZE_OUT.labels(
            be.name, obj.extension, obj.format).observe(obj.src.size)


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

        raise UnsupportedTypeError('No backend for %s', obj.extension)


@run_in_executor
def generate(obj):
    store, key = storage.get(obj)
    # If the file was fetched from the store, it will have been loaded into
    # obj. We can return to continue with the response.
    if store:
        return

    # Otherwise, we need to generate a new preview.
    Backend.preview(obj)

    # If a key and preview was generated, store the preview for reuse.
    if key:
        storage.put(key, obj)
