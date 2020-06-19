import uvloop

import asyncio
from concurrent.futures import ThreadPoolExecutor
from aiohttp import web


# Use uvloop, set it up early so other modules can access the correct event
# loop during import.
LOOP = uvloop.new_event_loop()
# Set up a default executor for conversion backends.
LOOP.set_default_executor(ThreadPoolExecutor(max_workers=40))
asyncio.set_event_loop(LOOP)


from preview import get_app
from preview.storage import Cleanup
from preview.config import PROFILE_PATH, GID, UID, PORT


def main():
    if GID:
        os.setgid(int(GID))
    if UID:
        os.setuid(int(UID))

    app = get_app()

    # TODO: probably a better way...
    Cleanup(LOOP)

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
