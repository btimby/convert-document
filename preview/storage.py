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
    safe_remove, safe_makedirs, run_in_executor, log_duration
)
from preview.metrics import STORAGE, STORAGE_FILES, STORAGE_BYTES
from preview.config import BASE_PATH, CLEANUP_MAX_SIZE, CLEANUP_INTERVAL
from preview.models import PathModel
from preview.backends.image import cleanup


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def make_key(*args):
    key = '|'.join([str(a) for a in args])
    return hashlib.sha256(key.encode('utf8')).hexdigest()


def make_path(key):
    return pathjoin(BASE_PATH, key[:1], key[1:2], key)


def get(obj):
    if BASE_PATH is None:
        # Storage is disabled.
        LOGGER.debug('Storage is disabled, BASE_PATH is not configured')
        return False, None

    # Caller opted out of storage.
    if obj.args['store'] is False:
        LOGGER.debug('Storage is disabled for this request')
        return False, None

    if obj.origin is None:
        LOGGER.debug('Storage is disabled, no origin')
        return False, None

    key = make_key(
        obj.origin, obj.format, obj.width, obj.height, obj.args.get('pages'))
    store_path = make_path(key)

    if not isfile(store_path):
        LOGGER.debug('Preview for %s not found at %s', obj.origin, store_path)
        return False, key

    mtime = stat(store_path).st_mtime
    if stat(obj.src.path).st_mtime > mtime:
        LOGGER.info('Removing preview for %s at %s', obj.origin, store_path)
        STORAGE.labels('del').inc()
        safe_remove(store_path)
        return False, key

    LOGGER.debug('Serving preview for %s from %s', obj.origin, store_path)
    STORAGE.labels('get').inc()
    # update atime, but leave mtime untouched.
    os.utime(store_path, (time(), mtime))
    obj.dst = PathModel(store_path)

    return True, key


def put(key, obj):
    STORAGE.labels('put').inc()

    store_path = make_path(key)
    LOGGER.debug('Storing preview for %s at %s', obj.origin, store_path)

    try:
        safe_makedirs(dirname(store_path))
        shutil.move(obj.dst.path, store_path)

    except IOError as e:
        if e.errno != errno.ENOSPC:
            raise
        # If disk is full, return. The dst path has not yet been modified. The
        # passed in path will be served.
        return

    # Change mtime of stored preview to match source path. If source path
    # changes later, this preview will be regenerated.
    src_mtime = stat(obj.src.path).st_mtime
    os.utime(store_path, (src_mtime, src_mtime))

    # Update dst path, this is the preview sent in the response.
    obj.dst = PathModel(store_path)


class Cleanup(object):
    def __init__(self, loop, base_path=BASE_PATH,
                 max_size=CLEANUP_MAX_SIZE, interval=CLEANUP_INTERVAL):
        self.loop = loop
        self.base_path = base_path
        self.max_size = max_size
        self.interval = interval
        self.last = 0
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

        # sort by atime desc
        files.sort(key=lambda x: -x[0])

        # determine if we are over-size
        size = sum(x[1] for x in files)

        return size, files

    def should_remove(self):
        if self.base_path is None or self.max_size is None:
            return False

        if time() - self.last >= self.interval:
            self.last = time()
            return True

    @log_duration
    def cleanup(self):
        try:
            # Try to clean up magickwand temp files.
            cleanup()

        except:
            LOGGER.exception(e)

        try:
            # Get totals for metrics.
            size, files = self.scan()
            count = len(files)

            LOGGER.info('Storage: %i files, totaling %i bytes',
                        count, size)
            STORAGE_FILES.set(count)
            STORAGE_BYTES.set(size)

            if not self.should_remove():
                return

            LOGGER.debug('Performing cleanup')

            # Prune files older than max_storage_age
            ifiles = iter(files)
            while size >= self.max_size:
                try:
                    atime, file_size, path = ifiles.__next__()

                except StopIteration:
                    break

                size -= file_size
                safe_remove(path)

        finally:
            self.loop.call_later(60, run_in_executor(self.cleanup))
