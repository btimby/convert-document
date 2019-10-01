import logging

from tempfile import NamedTemporaryFile

import av
from PIL import Image

from preview.backends.base import BaseBackend
from preview.metrics import CONVERSIONS, CONVERSION_ERRORS
from preview.utils import log_duration, get_extension


LOGGER = logging.getLogger(__name__)


def grab_frames(path, width, height):
    # Load and resize our foreground image.
    fg = Image.open('images/film-overlay.png')
    fg.thumbnail((width, height))

    # Open our video file and determine it's duration and fps.
    in_ = av.open(path)
    stream = in_.streams.video[0]
    duration = stream.duration / stream.time_base.denominator
    fps = stream.frames / duration
    # We want to grab 3 frames per second.
    nth = fps // 3

    images = []
    for i, frame in enumerate(in_.decode(video=0)):
        # Grab every nth frame.
        if i % nth != 0:
            continue
        # Grab 15 frames (5 seconds)
        if len(images) == 15:
            break
        img = frame.to_image().convert("RGBA")
        img = img.resize((fg.width, fg.height))
        images.append(Image.alpha_composite(img, fg))

    with NamedTemporaryFile(delete=False, suffix='.gif') as t:
        # save our animated gif, each frame should display for 1/3rd of a
        # second.
        images[0].save(t.name, save_all=True, append_images=images[1:],
                       duration=333, loop=0, optimize=True)

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
