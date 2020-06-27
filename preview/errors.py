class BaseError(Exception):
    pass


class InvalidFormatError(BaseError):
    pass


class InvalidPluginError(BaseError):
    pass


class InvalidPageError(BaseError):
    def __init__(self, pages):
        super().__init__('Invalid page range: %i-%i' % pages)
