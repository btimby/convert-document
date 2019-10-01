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
RESOLUTIONS = [
    ('800', '600'),
    ('720', '540'),
    ('640', '480'),
    ('480', '360'),
    ('400', '300'),
    ('320', '240'),
    ('280', '210'),
    ('240', '180'),
    ('160', '120'),
]
FILES = [
    { 'url': 'https://www.fujifilmusa.com/products/digital_cameras/x/fujifilm_x20/sample_images/img/index/ff_x20_008.JPG' },
    { 'url': 'http://www.pdf995.com/samples/pdf.pdf' },
    { 'url': 'https://archive.org/download/SampleMpeg4_201307/sample_mpeg4.mp4' },
    { 'url': 'http://homepages.inf.ed.ac.uk/neilb/TestWordDoc.doc'},
]
FILES.extend([
    {'path': path} for path in os.listdir('fixtures')
])

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.WARNING)
LOGGER.addHandler(logging.StreamHandler())


async def run(total, concurrent):
    # create instance of Semaphore
    sem = asyncio.Semaphore(concurrent)
    tasks = []

    async def fetch(i, params):
        kwargs = {}
        # POST the file 1/10th of the time.
        if 'path' in params and random.random() >= 0.9:
            method = session.post
            params['file'] = open('fixtures/%s' % params.pop('path'), 'rb')
            kwargs['data'] = params

        else:
            method = session.get
            kwargs['params'] = params

        async with sem:
            try:
                async with method(URL, **kwargs) as response:
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
            width, height = random.choice(RESOLUTIONS)
            params = {
                'width': width,
                'height': height,
            }
            params.update(random.choice(FILES))
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
