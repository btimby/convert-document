import os
import functools
import asyncio
import logging

from os.path import splitext
from os.path import join as pathjoin

from time import time


LOGGER = logging.getLogger()
LOGGER.addHandler(logging.NullHandler())


def run_in_executor(f, executor=None):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(executor, functools.partial(f, *args, **kwargs))
    return inner


def quote(obj):
    if type(obj) is str:
        return '"%s"' % obj
    return str(obj)


def fstr(f, args, kwargs=None):
    fname = f.__name__
    try:
        obj = args[0]

    except IndexError:
        pass

    else:
        if callable(getattr(obj, fname, None)):
            fname = obj.__class__.__name__ + '.' + fname
            args = args[1:]

    astr = str(args).strip('(,)')
    if kwargs:
        astr += ', '
        astr += ', '.join(['%s=%s' % (k, quote(v)) for k, v in kwargs.items()])
    return '%s(%s)' % (fname, astr)


def log_duration(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        start = time()
        try:
            return f(*args, **kwargs)

        finally:
            duration = time() - start

            if duration <= 5:
                level = logging.DEBUG
            elif duration <= 10:
                level = logging.INFO
            else:
                level = logging.WARNING

            LOGGER.log(
                level, '%s took %fs', fstr(f, args, kwargs), duration)

    return inner


def safe_remove(path):
    try:
        os.remove(path)

    except FileNotFoundError as e:
        LOGGER.debug('Ignoring: %s' % e, exc_info=True)


def safe_makedirs(path):
    try:
        os.makedirs(path)

    except FileExistsError as e:
        LOGGER.debug('Ignoring: %s' % e, exc_info=True)


def get_extension(path):
    return splitext(path)[1].lower()[1:]


def chroot(path, fr, to):
    'Changes the root (parent) from one directory to another.'
    assert path.startswith(fr), \
        'Path %s not rooted in %s' % (path, fr)
    return pathjoin(to, path[len(fr):].lstrip('/'))
