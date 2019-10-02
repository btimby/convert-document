import logging
import pathlib

from os.path import getsize

from preview.utils import get_extension
from preview.backends.office import OfficeBackend
from preview.backends.image import ImageBackend
from preview.backends.video import VideoBackend
from preview.backends.pdf import PdfBackend
from preview.metrics import PREVIEWS, PREVIEW_SIZE_IN, PREVIEW_SIZE_OUT
from preview import storage


LOGGER = logging.getLogger()
LOGGER.addHandler(logging.NullHandler())


class UnsupportedTypeError(Exception):
    pass


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
                PREVIEW_SIZE_IN.labels(
                    obj.name, extension).observe(getsize(path))

                with PREVIEWS.labels(extension, width, height).time():
                    path = obj.preview(path, width, height)
                    PREVIEW_SIZE_OUT.labels(
                        obj.name, extension).observe(getsize(path))
                    return path

        raise UnsupportedTypeError('Unsupported file type: %s' % extension)


def generate(path, format, width, height):
    store_key, store_path = storage.get(path, format, width, height)

    if store_path is None:
        store_path = Backend.preview(path, width, height)
        store_path = storage.put(store_key, path, store_path)

    return pathlib.Path(store_path)
