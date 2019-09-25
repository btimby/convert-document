import functools
import asyncio
import logging

from time import time


LOGGER = logging.getLogger()
LOGGER.addHandler(logging.NullHandler())


def run_in_executor(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, functools.partial(f, *args, **kwargs))
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
            level = logging.DEBUG if duration <= 5 else logging.WARNING
            LOGGER.log(
                level, '%s took %fs', fstr(f, args, kwargs), duration)

    return inner
