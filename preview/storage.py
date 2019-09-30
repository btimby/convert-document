import os
import shutil
import hashlib
import logging

from time import time

from preview.utils import safe_delete, safe_makedirs, run_in_executor
from preview.metrics import STORAGE, STORAGE_BYTES, STORAGE_FILES


BASE_PATH = os.environ.get('PVS_STORE')

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def make_key(*args):
    key = '|'.join([str(a) for a in args])
    return hashlib.sha256(key.encode('utf8')).hexdigest()


def make_path(key):
    return os.path.join(BASE_PATH, key[:1], key[1:2], key)


def get(path, format, width, height):
    if BASE_PATH is None:
        # Storage is disabled.
        return None, None

    key = make_key(path, format, width, height)
    store_path = make_path(key)

    path_mtime = os.stat(path).st_mtime
    if os.path.isfile(store_path):
        store_mtime = os.stat(path).st_mtime

    else:
        store_mtime = None

    if path_mtime == store_mtime:
        STORAGE.labels('get').inc()
        # touch the atime (used for LRU cleaning)
        LOGGER.info('Serving from storage')
        os.utime(store_path, (time(), store_mtime))
        return key, store_path

    elif os.path.isfile(store_path):
        STORAGE.labels('del').inc()
        LOGGER.info('Removing stale file from storage')
        try:
            os.remove(store_path)

        except FileNotFoundError:
            pass

    return key, None


def put(key, path, src_path):
    if BASE_PATH is None:
        # Storage is disabled.
        return path

    STORAGE.labels('put').inc()
    LOGGER.info('Storing file')
    store_path = make_path(key)
    safe_makedirs(os.path.dirname(store_path))
    shutil.move(src_path, store_path)

    path_mtime = os.stat(path).st_mtime
    os.utime(store_path, (path_mtime, path_mtime))
    return store_path


def is_temp(path):
    return not path.startswith(BASE_PATH)
