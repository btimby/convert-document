import os
import time
import shutil
import hashlib
import asyncio
import logging

import humanfriendly

from preview.utils import run_in_executor


BASE_PATH = os.environ.get('PREVIEW_STORE')
MAX_STORAGE_SIZE = os.environ.get('PREVIEW_STORE_SIZE')
CLEANUP_INTERVAL = int(os.environ.get('PREVIEW_STORE_CLEANUP_INTERVAL', 0))

if MAX_STORAGE_SIZE is not None:
    MAX_STORAGE_SIZE = humanfriendly.parse_size(MAX_STORAGE_SIZE)

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def make_key(*args):
    key = '|'.join([str(a) for a in args])
    return hashlib.sha256(key.encode('utf8')).hexdigest()


def make_path(key):
    return os.path.join(BASE_PATH, key[:2], key[2:4], key)


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
        # touch the atime (used for LRU cleaning)
        LOGGER.info('Serving from storage')
        os.utime(store_path, (time.time(), store_mtime))
        return key, store_path

    elif os.path.isfile(store_path):
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

    LOGGER.info('Storing file')
    store_path = make_path(key)
    try:
        os.makedirs(os.path.dirname(store_path))

    except FileExistsError:
        pass

    shutil.move(src_path, store_path)

    path_mtime = os.stat(path).st_mtime
    os.utime(store_path, (path_mtime, path_mtime))
    return store_path


def cleanup(loop):
    if ((BASE_PATH is None or MAX_STORAGE_SIZE is None
            or CLEANUP_INTERVAL is None)):
        return

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
    files.sort(key=lambda x: x[0])

    # determine if we are over-size
    total_size = sum(x[1] for x in files)
    file_count = len(files)

    LOGGER.info(
        'cleanup() Found: %i files totaling %i bytes', file_count, total_size)

    if total_size > MAX_STORAGE_SIZE:
        # prune oldest atimes until we are under-size
        while total_size > MAX_STORAGE_SIZE:
            _, size, path = files.pop(0)
            try:
                os.remove(path)

            except FileNotFoundError:
                pass

            total_size -= size
            file_count -= 1
        LOGGER.debug(
            'cleanup() now %i files totaling %i bytes', file_count, total_size)

    sleepy = CLEANUP_INTERVAL * 60
    loop.call_later(sleepy, lambda: cleanup(loop))


def is_temp(path):
    return not path.startswith(BASE_PATH)
