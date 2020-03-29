import os
import logging

from os.path import isfile, isdir, dirname
from os.path import join as pathjoin

from preview.models import PathModel
from preview.backends.image import ImageBackend


ICON_ROOT = 'images/file-types'
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def _dimensions():
    dims = []
    for d in os.listdir(ICON_ROOT):
        if not isdir(pathjoin(ICON_ROOT, d)):
            continue

        try:
            dims.append(int(d))

        except ValueError as e:
            LOGGER.debug('Ignoring: %s', e, exc_info=True)

    return sorted(dims)


DIMENSIONS = _dimensions()


def get(obj):
    if not DIMENSIONS:
        return

    bestdim = DIMENSIONS[0]
    for dim in DIMENSIONS:
        bestdim = dim
        if dim >= max(obj.width, obj.height):
            break

    icon_path = pathjoin(ICON_ROOT, str(bestdim), '%s.png' % obj.src.extension)

    if isfile(icon_path):
        obj.src = PathModel(icon_path)
        return True
