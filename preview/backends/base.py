from abc import ABC, abstractmethod

from preview.metrics import CONVERSIONS, CONVERSION_ERRORS


class BaseBackend(ABC):
    name = None
    extensions = []

    def __init__(self):
        pass

    @abstractmethod
    def _preview(self, obj):
        raise NotImplementedError()

    def preview(self, obj):
        try:
            with CONVERSIONS.labels(self.name, obj.extension).time():
                return self._preview(obj)

        except Exception:
            CONVERSION_ERRORS.labels(self.name, obj.extension).inc()
            raise
