import os
import sys
import random
import asyncio
import logging

from os.path import join as pathjoin
from time import time

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectorError, \
    ServerDisconnectedError


URL = os.environ.get('URL', 'http://preview:8080/preview/')
TOTAL = 10000
CONCURRENT = 20
PATHS = os.listdir('fixtures')
RESOLUTIONS = [
    (800, 600),
    (720, 540),
    (640, 480),
    (480, 360),
    (400, 300),
    (320, 240),
    (280, 210),
    (240, 180),
    (160, 120),
]

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.WARNING)
LOGGER.addHandler(logging.StreamHandler())


async def run(total, concurrent):
    # create instance of Semaphore
    sem = asyncio.Semaphore(concurrent)
    tasks = []

    async def fetch(i, params):
        # Getter function with semaphore.
        async with sem:
            try:
                async with session.get(URL, params=params) as response:
                    res = await response.read()
                    print('\033[K', i, response.status, len(res), res[:20],
                          end='\r')
                    if response.status != 200:
                        print('\n', end='')
                    return response.status

            except (ClientConnectorError, ServerDisconnectedError) as e:
                print(e)

    # Create client session that will ensure we dont open new connection
    # per each request.
    async with ClientSession() as session:
        for i in range(total):
            path = random.choice(PATHS)
            # "touch" a file 10% of the time.
            if random.random() > 0.9:
                os.utime(pathjoin('fixtures', path))
            width, height = random.choice(RESOLUTIONS)
            params = {
                'path': path,
                'width': width,
                'height': height,
                #'width': random.randint(100, 800),
                #'height': random.randint(100, 800),
            }
            task = asyncio.ensure_future(fetch(i, params))
            tasks.append(task)

        start = time()
        statuses = asyncio.gather(*tasks)
        await statuses

    return statuses, time() - start


def main(total, concurrent):
    print('Testing: %s with %i requests, max concurrency of %i' % (URL, total,
                                                                   concurrent))
    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(run(total, concurrent))
    statuses, duration = loop.run_until_complete(future)

    failures = len([x for x in statuses.result() if x != 200])
    successes = len([x for x in statuses.result() if x == 200])

    print('\n', end='')
    print('Total duration: %f, RPS: %f' % (duration, total / duration))
    print('Failures: %i, Successes: %i' % (failures, successes))

    if failures:
        sys.exit(1)


if __name__ == '__main__':
    total = int(sys.argv[1]) if len(sys.argv) > 1 else TOTAL
    concurrent = int(sys.argv[2]) if len(sys.argv) > 2 else CONCURRENT
    main(total, concurrent)
