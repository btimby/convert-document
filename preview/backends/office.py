import logging
import subprocess

from tempfile import NamedTemporaryFile
from concurrent.futures import ThreadPoolExecutor

from preview.backends.base import BaseBackend
from preview.backends.pdf import PdfBackend
from preview.utils import log_duration
from preview.config import (
    SOFFICE_ADDR, SOFFICE_PORT, SOFFICE_TIMEOUT, SOFFICE_RETRY, MAX_OFFICE_WORKERS
)
from preview.models import PathModel


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())
TEXT_FORMATS = [
    'log',
]


def convert(obj, retry=SOFFICE_RETRY, pages=(1, 1)):
    cmd = [
        'unoconv', '--server=%s' % SOFFICE_ADDR, '--port=%s' % SOFFICE_PORT,
        '--stdout',
    ]

    if pages != (0, 0):
        cmd.extend(['-e', 'PageRange=%i-%i' % pages])

    file_data = None
    if obj.src.is_shared:
        cmd.append(obj.src.path)

    else:
        format = obj.src.extension
        if format in TEXT_FORMATS:
            format = 'txt'

        cmd.extend(['-I', format, '--stdin'])
        with open(obj.src.path, 'rb') as f:
            file_data = f.read()

    LOGGER.debug('unoconv cmd: %s' % cmd)

    while True:
        try:
            p = subprocess.run(cmd, input=file_data, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=SOFFICE_TIMEOUT,
                               check=True)

            return p.stdout

        except subprocess.CalledProcessError as e:
            LOGGER.warning(e, exc_info=True)
            LOGGER.warning(e.stdout)
            LOGGER.warning(e.stderr)
            if not retry:
                raise
            LOGGER.debug(
                'unoconv failed with (retrying): %i; %s\n%s',
                e.returncode, e.stdout, e.stderr)

        except Exception as e:
            if not retry:
                raise
            LOGGER.debug('unoconv failed, retrying: %s', e, exc_info=True)

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
    executor = ThreadPoolExecutor(max_workers=MAX_OFFICE_WORKERS) \
        if MAX_OFFICE_WORKERS else None

    @log_duration
    def _preview_pdf(self, obj):
        pages = obj.args.get('pages')

        with NamedTemporaryFile(delete=False, suffix='.pdf') as t:
            t.write(convert(obj, pages=pages))
            obj.dst = PathModel(t.name)

    @log_duration
    def _preview_image(self, obj):
        with NamedTemporaryFile(delete=False, suffix='.pdf') as t:
            t.write(convert(obj, pages=(1, 1)))
            obj.src = PathModel(t.name)
        PdfBackend()._preview_image(obj)
