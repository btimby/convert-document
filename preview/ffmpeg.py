import logging

from time import time
from tempfile import NamedTemporaryFile
from subprocess import Popen, PIPE


LOGGER = logging.getLogger(__name__)


def preview_video(path, width, height):
    start = time()
    try:
        with NamedTemporaryFile(suffix='.apng') as t:
            filter = \
                '[0:v]scale=%i:%i[bg]; ' \
                '[1:v]scale=%ix%i[ovl];[bg][ovl]overlay=0:0' % (width, height,
                                                                width, height)
            cmd = [
                'ffmpeg', '-y', '-ss', '00:00', '-i', path, '-i',
                'images/film-overlay.png', '-filter_complex', filter,
                '-plays', '0', '-t', '5', '-r', '1', t.name
            ]
            LOGGER.debug(' '.join(cmd))
            process = Popen(cmd, stderr=PIPE)
            _, stderr = process.communicate()
            LOGGER.debug(stderr)
            if b'Output file is empty' in stderr:
                raise Exception('Could not grab frame')

            return t.read()

    finally:
        LOGGER.info('preview_video(%s) took: %ss', path, time() - start)
