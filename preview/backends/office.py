import logging
import subprocess

from tempfile import NamedTemporaryFile

from preview.backends.base import BaseBackend
from preview.backends.pdf import PdfBackend
from preview.utils import log_duration, get_extension
from preview.config import FILE_ROOT, SOFFICE_ADDR, SOFFICE_PORT, \
                           SOFFICE_TIMEOUT, SOFFICE_RETRY


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def convert(path, retry=SOFFICE_RETRY):
    cmd = [
        'unoconv', '--server=%s' % SOFFICE_ADDR, '--port=%s' % SOFFICE_PORT,
        '--stdout'
    ]

    file_data = None
    if not path.startswith(FILE_ROOT):
        # Only FILE_ROOT is shared with soffice. Any paths outside that
        # directory need to be streamed to soffice.
        extension = get_extension(path)
        cmd.extend(['-I', extension, '--stdin'])
        with open(path, 'rb') as f:
            file_data = f.read()

    else:
        cmd.append(path)

    while True:
        try:
            p = subprocess.run(cmd, input=file_data, capture_output=True,
                               timeout=SOFFICE_TIMEOUT, check=True)

            return p.stdout

        except Exception as e:
            if not retry:
                raise
            LOGGER.debug('unoconv failed, retrying: %s' % e, exc_info=True)

        finally:
            retry -= 1


class OfficeBackend(BaseBackend):
    name = 'office'
    extensions = [
        'dot', 'docm', 'dotx', 'dotm', 'psw', 'doc', 'xls', 'ppt', 'wpd',
        'wps', 'csv', 'sdw', 'sgl', 'vor', 'docx', 'xlsx', 'pptx', 'xlsm',
        'xltx', 'xltm', 'xlt', 'xlw', 'dif', 'rtf', 'pxl', 'pps', 'ppsx',
        'odt', 'ods', 'odp'
    ]

    @log_duration
    def _preview(self, path, width, height):
        with NamedTemporaryFile(suffix='.pdf') as t:
            data = convert(path)
            t.write(data)
            t.flush()
            return PdfBackend().preview(t.name, width, height)
