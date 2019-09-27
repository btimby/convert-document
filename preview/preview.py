import logging

from os.path import splitext

from preview.backends.office import OfficeBackend
from preview.backends.image import ImageBackend
from preview.backends.video import VideoBackend
from preview.backends.pdf import PdfBackend
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
    def get(path):
        extension = splitext(path)[1].lower()[1:]

        for extensions, obj in Backend.backends.items():
            if extension in extensions:
                return obj

        raise UnsupportedTypeError('Unsupported file type: %s' % extension)


def generate(path, format, width, height):
    store_key, store_path = storage.get(path, format, width, height)

    if store_path is None:
        store_path = Backend.get(path).preview(path, width, height)
        store_path = storage.put(store_key, path, store_path)

    return store_path
