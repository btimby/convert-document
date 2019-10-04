import logging
import subprocess

from tempfile import NamedTemporaryFile

from preview.backends.base import BaseBackend
from preview.backends.pdf import PdfBackend
from preview.utils import log_duration
from preview.config import (
    SOFFICE_ADDR, SOFFICE_PORT, SOFFICE_TIMEOUT, SOFFICE_RETRY
)
from preview.models import PathModel


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def convert(obj, retry=SOFFICE_RETRY):
    cmd = [
        'unoconv', '--server=%s' % SOFFICE_ADDR, '--port=%s' % SOFFICE_PORT,
        '--stdout', '-e', 'PageRange=1-1',
    ]

    file_data = None
    if obj.src.is_shared:
        cmd.append(obj.src.path)

    else:
        cmd.extend(['-I', obj.src.extension, '--stdin'])
        with open(obj.src.path, 'rb') as f:
            file_data = f.read()

    while True:
        try:
            p = subprocess.run(cmd, input=file_data, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=SOFFICE_TIMEOUT,
                               check=True)

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
        'odt', 'ods', 'odp', 'log', 'txt',
    ]
    formats = [
        'image', 'pdf',
    ]

    @log_duration
    def _preview(self, obj):
        with NamedTemporaryFile(delete=False, suffix='.pdf') as t:
            t.write(convert(obj))

            if obj.format == 'pdf':
                # If the user requested a pdf, send them one.
                obj.dst = PathModel(t.name)
                return

            # Otherwise, use the PDF as input for the next step.
            obj.src = PathModel(t.name)

        PdfBackend().preview(obj)
