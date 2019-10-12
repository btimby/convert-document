import os
import shutil
import hashlib
import logging
import errno

from os import stat
from time import time

from os.path import isfile, dirname
from os.path import join as pathjoin

from preview.utils import (
    safe_delete, safe_makedirs, run_in_executor, log_duration
)
from preview.metrics import STORAGE, STORAGE_FILES, STORAGE_BYTES
from preview.config import BASE_PATH, MAX_STORAGE_AGE
from preview.models import PathModel


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())
EIGHT_HOURS = 3600 * 8


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

    # Caller opted out of storage.
    if obj.args['store'] is False:
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

    # Caller opted out of storage.
    if obj.args['store'] is False:
        return

    STORAGE.labels('put').inc()
    LOGGER.info('Storing file')

    store_path = make_path(key)
    try:
        safe_makedirs(dirname(store_path))
        shutil.move(obj.dst.path, store_path)

    except IOError as e:
        if e.errno != errno.ENOSPC:
            raise
        # If disk is full, return. The dst path has not yet been modified. The
        # passed in path will be served.
        return

    src_mtime = stat(obj.src.path).st_mtime
    os.utime(store_path, (src_mtime, src_mtime))
    obj.dst = PathModel(store_path)


class Cleanup(object):
    def __init__(self, loop, base_path=BASE_PATH,
                 max_storage_age=MAX_STORAGE_AGE):
        self.loop = loop
        self.base_path = base_path
        self.max_storage_age = max_storage_age
        self.remove_interval = max(900, max_storage_age or 0 / 2)
        self.remove_time = 0
        self.loop.call_soon(run_in_executor(self.cleanup))

    def scan(self):
        # walk storage location
        files = []
        for dir, _, filenames in os.walk(BASE_PATH):
            # enumerate files
            for fn in filenames:
                path = pathjoin(BASE_PATH, dir, fn)
                atime = os.stat(path).st_atime
                size = os.path.getsize(path)
                files.append((atime, size, path))

        # sort by atime
        files.sort(key=lambda x: -x[0])

        # determine if we are over-size
        size = sum(x[1] for x in files)

        return size, files

    def should_remove(self):
        if self.base_path is None or self.max_storage_age is None:
            return

        if time() - self.remove_time >= self.remove_interval:
            self.remove_time = time()
            return True

    @log_duration
    def cleanup(self):
        try:
            size, files = self.scan()
            count = len(files)

            if self.should_remove():
                LOGGER.debug('Performing removal')
                # Prune files older than max_storage_age
                for atime, file_size, path in files:
                    if time() - atime > self.max_storage_age:
                        size, count = size - file_size, count - 1
                        safe_delete(path)

            LOGGER.info('Storage: %i files, totaling %i bytes',
                        count, size)
            STORAGE_FILES.set(count)
            STORAGE_BYTES.set(size)

        finally:
            self.loop.call_later(60, run_in_executor(self.cleanup))
