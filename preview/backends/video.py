import logging

from shutil import which
from tempfile import NamedTemporaryFile
from subprocess import Popen, PIPE

from preview.backends.base import BaseBackend
from preview.utils import log_duration


LOGGER = logging.getLogger(__name__)

FF_START = '00:00'
FF_FRAMES = '5'
FF_FPS = '12'


class VideoBackend(BaseBackend):
    extensions = [
        '3g2', '3gp', '4xm', 'a64', 'aac', 'ac3', 'act', 'adf', 'adts', 'adx',
        'aea', 'afc', 'aiff', 'alaw', 'alsa', 'amr', 'anm', 'apc', 'ape',
        'aqtitle', 'asf', 'ast', 'au', 'avi', 'avm2', 'avr', 'avs', 'bfi',
        'bink', 'bit', 'bmv', 'boa', 'brstm', 'c93', 'caf', 'cdg', 'cdxl',
        'daud', 'dfa', 'dirac', 'divx', 'dnxhd', 'dsicin', 'dts', 'dtshd',
        'dvd', 'dxa', 'ea', 'ea_cdata', 'eac3', 'epaf', 'f32be', 'f32le',
        'f4v', 'film_cpk', 'filmstrip', 'fli', 'flic', 'flc', 'flv', 'frm',
        'g722', 'g723_1', 'g729', 'gxf', 'h261', 'h263', 'h264', 'hds', 'hevc',
        'hls', 'hls', 'idf', 'iff', 'ismv', 'iss', 'iv8', 'ivf', 'jv', 'latm',
        'lavfi', 'lmlm4', 'loas', 'lvf', 'lxf', 'm4v', 'mgsts', 'microdvd',
        'mjpeg', 'mkv', 'mlp', 'mm', 'mmf', 'mov', 'mov', 'mp4', 'm4a', '3gp',
        '3g2', 'mj2', 'mp2', 'mp4', 'mpeg', 'mpegts', 'mpg', 'mpjpeg', 'mpl2',
        'mpsub', 'mtv', 'mv', 'mvi', 'mxf', 'mxg', 'nsv', 'null', 'nut', 'nuv',
        'ogg', 'ogv', 'oma', 'opus', 'oss', 'paf', 'pjs', 'pmp', 'psp',
        'psxstr', 'pva', 'pvf', 'qcp', 'r3d', 'rl2', 'rm', 'roq', 'rpl', 'rsd',
        'rso', 'rtp', 'rtsp', 's16be', 's16le', 's24be', 's24le', 's32be',
        's32le', 's8', 'sami', 'sap', 'sbg', 'sdl', 'sdp', 'sdr2', 'segment',
        'shn', 'siff', 'smjpeg', 'smk', 'smush', 'sol', 'sox', 'svcd', 'swf',
        'tak', 'tee', 'thp', 'tmv', 'truehd', 'vc1', 'vcd', 'v4l2', 'vivo',
        'vmd', 'vob', 'voc', 'vplayer', 'vqf', 'w64', 'wc3movie', 'webm',
        'webvtt', 'wmv', 'wsaud', 'wsvqa', 'wtv', 'wv', 'xa', 'xbin', 'xmv',
        'xwma', 'yop'
    ]

    @log_duration
    def preview(self, path, width, height):
        with NamedTemporaryFile(suffix='.apng') as t:
            filter = \
                '[0:v]scale=%i:%i[bg]; ' \
                '[1:v]scale=%ix%i[ovl];[bg][ovl]overlay=0:0' % (width, height,
                                                                width, height)
            cmd = [
                'ffmpeg', '-y', '-ss', FF_START, '-i', path, '-i',
                'images/film-overlay.png', '-filter_complex', filter,
                '-plays', '0', '-t', FF_FRAMES, '-r', FF_FPS, t.name
            ]
            LOGGER.debug(' '.join(cmd))
            process = Popen(cmd, stderr=PIPE)
            _, stderr = process.communicate()
            LOGGER.debug(stderr)
            if b'Output file is empty' in stderr:
                raise Exception('Could not grab frame')

            return t.read()

    def check(self):
        return which('ffmpeg') is not None
