import logging
import tempfile

from io import BytesIO

import img2pdf

from wand.image import Image, Color

from preview.backends.base import BaseBackend
from preview.utils import log_duration
from preview.models import PathModel
from preview.errors import InvalidPageError


LOGGER = logging.getLogger(__name__)


def resize_image(path, width, height):
    with Image(width=width, height=height) as bg:
        # Resize our input image.
        with Image(filename=path, resolution=300) as s:
            d = Image(s.sequence[0])
            d.background_color = Color("white")
            d.alpha_channel = 'remove'
            d.transform(resize='%ix%i>' % (width, height))
            # Offset input image on top of background.
            left = (bg.width - d.width) // 2
            top = (bg.height - d.height) // 2
            bg.composite(d, left, top, operator='over')
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gif') as t:
            bg.save(filename=t.name)
            return t.name


def convert_to_pdf(path):
    data = BytesIO()
    # Remove alpha channel
    with Image(filename=path, resolution=300) as img:
        img.background_color = Color("white")
        img.alpha_channel = 'deactivate'
        img.format = 'png'
        img.save(file=data)
    data.seek(0)

    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as t:
        img2pdf.convert(data, outputstream=t)
        return t.name


class ImageBackend(BaseBackend):
    name = 'image'
    extensions = [
        # https://imagemagick.org/script/formats.php
        'aai', 'art', 'arw', 'avs', 'bpg', 'bmp', 'bmp2', 'bmp3', 'cals',
        'cgm', 'cin', 'cip', 'cmyk', 'cr2', 'crw', 'cube', 'cur', 'cut', 'cut',
        'dcm', 'dcr', 'dcx', 'dds', 'dib', 'djvu', 'dng', 'dpx', 'emf', 'epdf',
        'epi', 'eps', 'eps2', 'eps3', 'epsf', 'epsi', 'ept', 'exr', 'fax',
        'fig', 'fits', 'fpx', 'gif', 'gplt', 'gray', 'graya', 'hdr', 'heic',
        'hpgl', 'hrz', 'ico', 'info', 'jbig', 'jng', 'jp2', 'jpt', 'j2c',
        'j2k', 'jpg', 'jpeg', 'jxr', 'jxl', 'mat', 'miff', 'mono', 'mng',
        'm2v', 'mpc', 'mpr', 'mrw', 'msl', 'mtv', 'mvg', 'nef', 'orf', 'otb',
        'p7', 'palm', 'pam', 'pbm', 'pcd', 'pcds', 'pcl', 'pcx', 'pdb', 'pef',
        'pes', 'pfa', 'pfb', 'pfm', 'pgm', 'picon', 'pict', 'pix', 'png',
        'png8', 'png00', 'png24', 'png32', 'png48', 'png64', 'pnm', 'ppm',
        'psd', 'ptif', 'pwp', 'rad', 'raf', 'rgb', 'rgb565', 'rgba', 'rgf',
        'rla', 'rle', 'sct', 'sfw', 'sgi', 'sun', 'svg', 'tga', 'tiff', 'tif',
        'ttf', 'ubrl', 'ubrl6', 'uil', 'viff', 'wbmp', 'wbmp', 'wdp', 'wmf',
        'wpg', 'x', 'xbm', 'xcf', 'xwd', 'x3f', 'yuv', 'xpm',
    ]

    @log_duration
    def _preview_image(self, obj, pages=None):
        if pages is None:
            pages = obj.args.get('pages')
        if pages != (1, 1):
            raise InvalidPageError(pages)

        path = resize_image(obj.src.path, obj.width, obj.height)
        obj.dst = PathModel(path)

    @log_duration
    def _preview_pdf(self, obj, pages=None):
        if pages is None:
            pages = obj.args.get('pages')
        if pages != (1, 1):
            raise InvalidPageError(pages)

        self._preview_image(obj)
        path = convert_to_pdf(obj.dst.path)
        obj.dst = PathModel(path)
