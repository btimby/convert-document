import os
import shutil
import hashlib
import logging

from os import stat
from time import time

from os.path import isfile, dirname
from os.path import join as pathjoin

from preview.utils import safe_delete, safe_makedirs
from preview.metrics import STORAGE
from preview.config import BASE_PATH
from preview.models import PathModel


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def make_key(*args):
    key = '|'.join([str(a) for a in args])
    return hashlib.sha256(key.encode('utf8')).hexdigest()


def make_path(key):
    return pathjoin(BASE_PATH, key[:1], key[1:2], key)


def _is_newer(left, right):
    if not isfile(right):
        return True

    return stat(left).st_mtime > stat(right).st_mtime


def get(key, obj):
    if BASE_PATH is None:
        # Storage is disabled.
        return

    store_path = make_path(key)

    if not isfile(store_path):
        return

    elif _is_newer(obj.src.path, store_path):
        LOGGER.info('Removing stale file from storage')
        STORAGE.labels('del').inc()
        safe_delete(store_path)

    else:
        LOGGER.info('Serving from storage')
        STORAGE.labels('get').inc()
        # update atime, not mtime, possible LRU...
        os.utime(store_path, (time(), stat(store_path).st_mtime))
        obj.dst = PathModel(store_path)

        return True


def put(key, obj):
    if BASE_PATH is None:
        # Storage is disabled.
        return

    STORAGE.labels('put').inc()
    LOGGER.info('Storing file')

    store_path = make_path(key)
    safe_makedirs(dirname(store_path))
    shutil.move(obj.dst.path, store_path)

    src_mtime = stat(obj.src.path).st_mtime
    os.utime(store_path, (src_mtime, src_mtime))
    obj.dst = PathModel(store_path)
