from preview.metrics import CONVERSIONS, CONVERSION_ERRORS


class BaseBackend(object):
    name = None
    extensions = []
    executor = None

    def __init__(self):
        pass

    def preview(self, obj):
        method = getattr(self, '_preview_%s' % obj.format)

        if not callable(method):
            raise Exception('Unsupported output format: %s' % obj.format)

        try:
            with CONVERSIONS.labels(self.name, obj.extension, obj.format).time():
                return method(obj)

        except Exception:
            CONVERSION_ERRORS.labels(self.name, obj.extension, obj.format).inc()
            raise
