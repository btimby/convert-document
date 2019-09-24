import logging

from os.path import splitext

from preview.backends.office import OfficeBackend
from preview.backends.image import ImageBackend
from preview.backends.video import VideoBackend
from preview.backends.pdf import PdfBackend


LOGGER = logging.getLogger()
LOGGER.addHandler(logging.NullHandler())


class Backends(object):
    def __init__(self):
        self.backends = {}
        for backend in [OfficeBackend, ImageBackend, VideoBackend, PdfBackend]:
            obj = backend()
            self.backends[tuple(obj.extensions)] = obj

    def get(self, extension):
        for extensions, obj in self.backends.items():
            if extension in extensions:
                return obj

        raise Exception('Unsupported file type')

    def __iter__(self):
        return iter(self.backends.values())


BACKENDS = Backends()


def generate(path, format, width, height):
    extension = splitext(path)[1].lower()[1:]
    return BACKENDS.get(extension).preview(path, width, height)
