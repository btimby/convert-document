import os
import shutil
import hashlib
import logging

from time import time

import humanfriendly

from preview.utils import safe_delete, safe_makedirs, run_in_executor
from preview.metrics import STORAGE, STORAGE_BYTES, STORAGE_FILES


BASE_PATH = os.environ.get('PVS_STORE')
MAX_STORAGE_SIZE = os.environ.get('PVS_STORE_MAX_SIZE')

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


class Cleanup(object):
    def __init__(self, loop, base_path=BASE_PATH,
                 max_storage_size=MAX_STORAGE_SIZE):
        self.loop = loop
        self.base_path = base_path
        self.max_storage_size = None
        if max_storage_size:
            self.max_storage_size = humanfriendly.parse_size(max_storage_size)
        self.loop.call_soon(run_in_executor(self.cleanup))

    def scan(self):
        # walk storage location
        files = []
        for dir, _, filenames in os.walk(BASE_PATH):
            # enumerate files
            for fn in filenames:
                path = os.path.join(BASE_PATH, dir, fn)
                atime = os.stat(path).st_atime
                size = os.path.getsize(path)
                files.append((atime, size, path))

        # sort by atime
        files.sort(key=lambda x: -x[0])

        # determine if we are over-size
        size = sum(x[1] for x in files)

        LOGGER.debug('Found: %i files, totaling %i bytes', len(files), size)

        STORAGE_FILES.set(len(files))
        STORAGE_BYTES.set(size)

        return size, files

    def cleanup(self):
        if self.base_path is None or self.max_storage_size is None:
            return

        size, files = self.scan()

        # prune oldest atimes until we are under-size
        removed, removed_size = 0, 0
        while size > self.max_storage_size:
            try:
                _, path_size, path = files.pop(0)

            except IndexError:
                break

            safe_delete(path)
            STORAGE.labels('del').inc()

            removed += 1
            size -= path_size
            removed_size += path_size

            if removed >= 100:
                break

        LOGGER.debug('Removed: %i files, totaling %i bytes',
                    removed, removed_size)

        self.loop.call_later(15, self.cleanup)


def is_temp(path):
    return not path.startswith(BASE_PATH)
