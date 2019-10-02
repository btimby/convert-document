from abc import ABC, abstractmethod

from preview.utils import get_extension
from preview.metrics import CONVERSIONS, CONVERSION_ERRORS


class BaseBackend(ABC):
    name = None
    extensions = []

    def __init__(self):
        pass

    @abstractmethod
    def _preview(self, path, width, height):
        pass

    def preview(self, path, width, height):
        extension = get_extension(path)
        try:
            with CONVERSIONS.labels(self.name, extension).time():
                return self._preview(path, width, height)

        except Exception:
            CONVERSION_ERRORS.labels(self.name, extension).inc()
            raise
