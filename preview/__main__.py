import os
import logging
import functools
import pathlib

from os.path import normpath, isfile
from os.path import join as pathjoin

from tempfile import NamedTemporaryFile

import uvloop
import asyncio
from concurrent.futures import ThreadPoolExecutor
from aiohttp import web, ClientSession
from aiohttp.web_middlewares import normalize_path_middleware

from preview.utils import (
    run_in_executor, log_duration, safe_delete, get_extension, chroot
)
from preview.preview import generate, UnsupportedTypeError
from preview.storage import BASE_PATH
from preview.metrics import (
    metrics_handler, metrics_middleware, TRANSFER_LATENCY,
    TRANSFERS_IN_PROGRESS
)
from preview.config import (
    DEFAULT_FORMAT, DEFAULT_WIDTH, DEFAULT_HEIGHT, MAX_WIDTH, MAX_HEIGHT,
    LOGLEVEL, HTTP_LOGLEVEL, FILE_ROOT, CACHE_CONTROL, UID, GID, X_ACCEL_REDIR,
    PORT, PROFILE_PATH
)
from preview.models import PreviewModel


# Limits
MEGABYTE = 1024 * 1024
BUFFER_SIZE = 8 * MEGABYTE
MAX_UPLOAD = 800 * MEGABYTE

LOGGER = logging.getLogger()
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(LOGLEVEL)
logging.getLogger('aiohttp').setLevel(HTTP_LOGLEVEL)


@log_duration
async def upload(upload):
    extension = get_extension(upload.filename)
    tip = TRANSFERS_IN_PROGRESS.labels('upload')
    tl = TRANSFER_LATENCY.labels('upload')

    with tl.time(), tip.track_inprogress():
        with NamedTemporaryFile(delete=False, suffix='.%s' % extension) as t:
            while True:
                data = await run_in_executor(upload.file.read)(BUFFER_SIZE)
                if not data:
                    break
                await run_in_executor(t.write)(data)
        return t.name


@log_duration
async def download(url):
    extension = get_extension(url)
    tip = TRANSFERS_IN_PROGRESS.labels('download')
    tl = TRANSFER_LATENCY.labels('download')

    with tl.time(), tip.track_inprogress():
        async with ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise web.HTTPBadRequest(
                        reason='Could not download: %s, %s' % (
                            url, resp.reason))

                with NamedTemporaryFile(
                        delete=False, suffix='.%s' % extension) as t:
                    while True:
                        data = await resp.content.read(BUFFER_SIZE)
                        if not data:
                            break
                        await run_in_executor(t.write)(data)
                    return t.name


async def get_params(request):
    """
    """
    if request.method == 'POST':
        data = await request.post()

    else:
        data = request.query

    path = data.get('path')
    file = data.get('file')
    url = data.get('url')
    name = data.get('name')
    content_type = data.get('content_type')

    format = data.get('format', DEFAULT_FORMAT)
    width = int(data.get('width', DEFAULT_WIDTH))
    height = int(data.get('height', DEFAULT_HEIGHT))
    width, height = min(width, MAX_WIDTH), min(height, MAX_HEIGHT)

    if path:
        # TODO: sanitize this path, ensure it is rooted in FILE_ROOT
        origin = path
        path = normpath(path)
        path = pathjoin(FILE_ROOT, path)

    elif file:
        origin = None
        path = await upload(file)

    elif url:
        origin = url
        path = await download(url)

    else:
        raise web.HTTPBadRequest(reason='No path, file or url provided')

    if not isfile(path):
        raise web.HTTPNotFound()

    return PreviewModel(path, width, height, format, origin=origin,
                        name=name, content_type=content_type)


generate = run_in_executor(generate)


async def info(request):
    return web.Response(text="OK")


class PreviewResponse(web.FileResponse):
    def __init__(self, obj, *args, **kwargs):
        self._obj = obj
        super(PreviewResponse, self).__init__(obj.dst.path, *args, **kwargs)
        self.content_type = obj.dst.content_type

    async def prepare(self, *args, **kwargs):
        try:
            return await super(PreviewResponse, self).prepare(
                *args, **kwargs)

        finally:
            await run_in_executor(self._obj.cleanup)()


async def preview(request):
    obj = await get_params(request)
    try:
        try:
            await generate(obj)
            status = 200

        except Exception as e:
            # NOTE: we send 203 to indicate that the content is not exactly
            # what was requested. This helps our tools / tests determine
            # if an error occurred. We also disable caching in the case of
            # an error response.
            LOGGER.exception(e)
            path = 'images/error.png'
            if isinstance(e, UnsupportedTypeError):
                path = 'images/unsupported.png'
            obj.cleanup()
            obj = PreviewModel(path, obj.width, obj.height, obj.format)
            await generate(obj)
            status = 203

        if BASE_PATH is None or obj.dst.is_temp:
            response = PreviewResponse(obj, status=status)

        elif X_ACCEL_REDIR:
            x_accel_path = chroot(obj.dst.path, BASE_PATH, X_ACCEL_REDIR)
            response = web.Response(status=status)
            response.headers['X-Accel-Redirect'] = x_accel_path
            response.content_type = obj.dst.content_type

        else:
            response = PreviewResponse(obj, status=status)

        # Don't cache error responses.
        if status == 200 and CACHE_CONTROL:
            max_age = 60 * int(CACHE_CONTROL)
            response.headers['Cache-Control'] = \
                'max-age=%i, public' % max_age

    except Exception as e:
        LOGGER.exception(e)
        raise web.HTTPInternalServerError(reason='Unrecoverable error')

    return response


def main():
    if GID:
        os.setgid(int(GID))
    if UID:
        os.setuid(int(UID))

    app = web.Application(
        client_max_size=MAX_UPLOAD, middlewares=[
            normalize_path_middleware(), metrics_middleware()
            ])

    app.add_routes([web.get('/', info)])
    app.add_routes([
        web.post('/preview/', preview),
        web.get('/preview/', preview)])
    app.add_routes([web.get('/metrics/', metrics_handler)])

    loop = uvloop.new_event_loop()
    # Conversion backends are blocking and run in the following executor.
    loop.set_default_executor(ThreadPoolExecutor(max_workers=40))
    asyncio.set_event_loop(loop)

    # TODO: figure out how to wait for pending requests before exiting.
    web.run_app(app, port=PORT)


if PROFILE_PATH:
    # To profile this application.
    #
    # - Map a volume in via docker: -v /tmp:/mnt/profile
    # - Set PVS_PROFILE_PATH=/mnt/profile
    # - Run the application, ensure it is NOT killed with TERM but INT, for
    #   example:
    #
    # docker-compose kill -s SIGINT
    #
    import yappi
    yappi.start()

    LOGGER.warning('Running under profiler.')
    try:
        main()

    finally:
        LOGGER.warning('Saving profile data to: %s.', PROFILE_PATH)
        yappi.stop()

        fstats = yappi.get_func_stats()
        tstats = yappi.get_thread_stats()

        for stat_type in ['pstat', 'callgrind', 'ystat']:
            path = pathjoin(PROFILE_PATH, 'preview.%s' % stat_type)
            fstats.save(path, type=stat_type)

        path = pathjoin(PROFILE_PATH, 'preview.func_stats')
        with open(path, 'w') as fh:
            fstats.print_all(out=fh)

        path = pathjoin(PROFILE_PATH, 'preview.thread_stats')
        with open(path, 'w') as fh:
            tstats.print_all(out=fh)

else:
    main()
