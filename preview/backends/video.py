import logging

from shutil import which
from tempfile import NamedTemporaryFile

import av
from PIL import Image

from preview.backends.base import BaseBackend
from preview.metrics import CONVERSIONS, CONVERSION_ERRORS
from preview.utils import log_duration, get_extension


LOGGER = logging.getLogger(__name__)

FF_START = '00:00'
FF_FRAMES = '5'
FF_FPS = '12'


def grab_frames(path, width, height):
    with NamedTemporaryFile(delete=False, suffix='.gif') as t:
        fg = Image.open('images/film-overlay.png')
        fg.thumbnail((width, height))

        images = []
        in_ = av.open(path)
        stream = in_.streams.video[0]
        duration = stream.duration / stream.time_base.denominator
        fps = stream.frames / duration
        nth = fps // 3

        for i, frame in enumerate(in_.decode(video=0)):
            if i % nth != 0:
                continue
            if len(images) == 15:
                break
            img = frame.to_image().convert("RGBA")
            img = img.resize((fg.width, fg.height))
            images.append(Image.alpha_composite(img, fg))

        frame_duration = duration * 1000 // len(images)
        images[0].save(t.name, save_all=True, append_images=images[1:],
                       duration=frame_duration, loop=0, optimize=True)

        return t.name


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
        extension = get_extension(path)
        try:
            with CONVERSIONS.labels('video', extension).time():
                return grab_frames(path, width, height)

        except Exception:
            CONVERSION_ERRORS.labels('video', extension).inc()
            raise
