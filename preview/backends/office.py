import imp
import sys
import shutil
import logging
import threading

from tempfile import NamedTemporaryFile

from preview.backends.base import BaseBackend
from preview.backends.pdf import PdfBackend
from preview.utils import log_duration


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def convert(inpath, outpath=None):
    # We use a unique identifier for this module. We want concurrency and each
    # time we import it needs to be "private" to the caller. If the identifier
    # is static, Python import will return the same module each time (cache).
    module_id = 'unoconv-%i' % threading.get_ident()
    unoconv = imp.load_source(module_id, shutil.which('unoconv'))

    import uno, unohelper

    unoconv.uno, unoconv.unohelper = uno, unohelper

    from com.sun.star.beans import PropertyValue
    from com.sun.star.connection import NoConnectException
    from com.sun.star.document.UpdateDocMode import NO_UPDATE, QUIET_UPDATE
    from com.sun.star.lang import DisposedException, IllegalArgumentException
    from com.sun.star.io import IOException, XOutputStream
    from com.sun.star.script import CannotConvertException
    from com.sun.star.uno import Exception as UnoException
    from com.sun.star.uno import RuntimeException

    unoconv.PropertyValue = PropertyValue
    unoconv.NoConnectException = NoConnectException
    unoconv.NO_UPDATE = NO_UPDATE
    unoconv.QUIET_UPDATE = QUIET_UPDATE
    unoconv.DisposedException = DisposedException
    unoconv.IllegalArgumentException = IllegalArgumentException
    unoconv.IOException = IOException
    unoconv.XOutputStream = XOutputStream
    unoconv.CannotConvertException = CannotConvertException
    unoconv.UnoException = UnoException
    unoconv.RuntimeException = RuntimeException

    def UnoProps(**args):
        props = []
        for key in args:
            prop = PropertyValue()
            prop.Name = key
            prop.Value = args[key]
            props.append(prop)
        return tuple(props)

    unoconv.UnoProps = UnoProps

    class OutputStream(unohelper.Base, XOutputStream):
        def __init__(self):
            self.closed = 0

        def closeOutput(self):
            self.closed = 1

        def writeBytes(self, seq):
            try:
                sys.stdout.buffer.write(seq.value)
            except AttributeError:
                sys.stdout.write(seq.value)

        def flush(self):
            pass

    unoconv.OutputStream = OutputStream

    # NOTE: this is a shortcut since I have only one office on my system.
    unoconv.office = unoconv.find_offices()[0]

    args = ['-e', 'PageRange=1-1', inpath]
    if outpath:
        args.insert(0, '--output=%s' % outpath)
    unoconv.op = unoconv.Options(args)

    try:
        try:
            convertor = unoconv.Convertor()

        except SystemExit:
            raise Exception('Could not initialize unoconv')

        if outpath:
            convertor.convert(inpath)

    finally:
        # Don't leak modules.
        del sys.modules[module_id]


class OfficeBackend(BaseBackend):
    extensions = [
        'dot', 'docm', 'dotx', 'dotm', 'psw', 'doc', 'xls', 'ppt', 'wpd',
        'wps', 'csv', 'sdw', 'sgl', 'vor', 'docx', 'xlsx', 'pptx', 'xlsm',
        'xltx', 'xltm', 'xlt', 'xlw', 'dif', 'rtf', 'pxl', 'pps', 'ppsx',
        'odt', 'ods', 'odp'
    ]

    def __init__(self):
        pass

    @log_duration
    def preview(self, path, width, height):
        with NamedTemporaryFile(suffix='.pdf') as t:
            convert(path, t.name)
            return PdfBackend().preview(t.name, width, height)

    def check(self):
        try:
            convert('fixtures/sample.docx')
            return True

        except Exception as e:
            LOGGER.exception(e)
            return False
