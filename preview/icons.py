import os
import logging

from os.path import isfile, isdir, dirname
from os.path import join as pathjoin

from functools import lru_cache

from aiohttp import web

from preview.models import PathModel
from preview.preview import Backend
from preview.config import ICON_ROOT, ICON_REDIRECT, ICON_RESIZE


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


@lru_cache(1000)
def _get_best_fit(extension, width, height):
    bestdim = DIMENSIONS[0]
    for dim in DIMENSIONS:
        bestdim = dim
        if dim >= max(width, height):
            break

    LOGGER.debug('Found %d best match for %dx%d', bestdim, width, height)

    return pathjoin(str(bestdim), '%s.png' % extension)


async def get(obj):
    if not DIMENSIONS:
        return

    icon_path = _get_best_fit(obj.extension, obj.width, obj.height)

    if not isfile(pathjoin(ICON_ROOT, icon_path)):
        LOGGER.debug('Could not find file-type icon for %s', obj.extension)
        icon_path = pathjoin(str(bestdim), 'default.png')
        if not isfile(pathjon(ICON_ROOT, icon_path)):
            LOGGER.debug('Could not find default file-type icon.')
            return False

    if ICON_REDIRECT:
        # Redirect browser to icon.
        url = '%s/%s' % (ICON_REDIRECT.rstrip('/'), icon_path)
        raise web.HTTPMovedPermanently(location=url)

    # Convert to full local path.
    icon_path = pathjoin(ICON_ROOT, icon_path)

    LOGGER.debug('Using icon: %s', icon_path)
    obj.src = PathModel(icon_path)

    if ICON_RESIZE:
        # Resize or convert the icon to the desired size / format.
        await Backend.preview(obj)

    return True
