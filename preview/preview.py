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


def _preview(obj, path, width, height):
    extension = get_extension(path)
    PREVIEW_SIZE_IN.labels(
        obj.name, extension).observe(getsize(path))

    with PREVIEWS.labels(extension, width, height).time():
        path = obj.preview(path, width, height)
        PREVIEW_SIZE_OUT.labels(
            obj.name, extension).observe(getsize(path))

        return path


class Backend(object):
    backends = {
        tuple(obj.extensions): obj
        for obj in [
            OfficeBackend(), ImageBackend(), VideoBackend(), PdfBackend()]
    }

    @staticmethod
    def preview(path, width, height):
        extension = get_extension(path)
        for extensions, obj in Backend.backends.items():
            if extension in extensions:
                return _preview(obj, path, width, height)

        raise UnsupportedTypeError('Unsupported file type: %s' % extension)


def generate(path, format, width, height):
    use_store = path.startswith(FILE_ROOT)
    store_key = storage.make_key(path, format, width, height)
    store_path = storage.get(store_key, path) if use_store else None

    if not store_path:
        store_path = Backend.preview(path, width, height)
        if use_store:
            store_path = storage.put(store_key, path, store_path)

    return pathlib.Path(store_path)
