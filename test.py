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


URL = os.environ.get('URL', 'http://preview:3000/preview/')
TOTAL = int(os.environ.get('TOTAL', '10000'))
CONCURRENT = int(os.environ.get('CONCURRENT', '20'))
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
    {'url': 'https://www.fujifilmusa.com/products/digital_cameras/x/fujifilm_x20/sample_images/img/index/ff_x20_008.JPG'},
    {'url': 'http://www.pdf995.com/samples/pdf.pdf'},
    {'url': 'https://archive.org/download/SampleMpeg4_201307/sample_mpeg4.mp4'},
    {'url': 'http://homepages.inf.ed.ac.uk/neilb/TestWordDoc.doc'},
]
FORMATS = [
    'pdf',
    'image',
]
FILES.extend([
    {'path': path} for path in os.listdir('fixtures')
])

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.WARNING)
LOGGER.addHandler(logging.StreamHandler())


class TaskPool(object):
    def __init__(self, limit):
        self._semaphore = asyncio.Semaphore(limit)
        self._tasks = set()
        self._results = list()

    async def put(self, coro):
        await self._semaphore.acquire()
        task = asyncio.ensure_future(coro)
        task.add_done_callback(self._on_task_done)
        self._tasks.add(task)

    def _on_task_done(self, task):
        self._tasks.remove(task)
        self._results.append(task.result())
        self._semaphore.release()

    @property
    def results(self):
        return self._results

    async def join(self):
        await asyncio.gather(*self._tasks)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.join()


async def do_response(i, response):
    res = await response.read()
    if response.status == 200:
        print('\033[K', i, response.status, len(res), res[:20],
              end='\r')

    else:
        print('\033[K', i, response.status, len(res), res[:60])
    return response.status


async def do_get(i, data, session):
    async with session.get(URL, params=data) as r:
        return await do_response(i, r)


async def do_post(i, data, session):
    with open('fixtures/%s' % data.pop('path'), 'rb') as f:
        data['file'] = f
        async with session.post(URL, data=data) as r:
            return await do_response(i, r)


async def do_request(i, session):
    # width, height = random.choice(RESOLUTIONS)
    width = str(random.randint(100, 400))
    height = str(random.randint(100, 400))
    data = {
        'width': width,
        'height': height,
    }
    # data['format'] = 'image'
    data['format'] = random.choice(FORMATS)
    data.update(random.choice(FILES))

    if 'path' in data and random.random() >= 0.9:
        # Touch 10% of the files (simulate modified input file).
        os.utime('fixtures/%s' % data['path'], (time(), time()))
        return await do_get(i, data, session)

    elif 'path' in data and random.random() >= 0.9:
        # POST 10% of files to server.
        return await do_post(i, data, session)

    else:
        # Just do a regular GET request (with path or url).
        return await do_get(i, data, session)


async def amain(total, concurrent):
    async with ClientSession() as session, TaskPool(concurrent) as tasks:
        for i in range(total):
            await tasks.put(do_request(i, session))
    return tasks.results


def main(total, concurrent):
    print('Testing: %s with %i requests, max concurrency of %i' % (URL, total,
                                                                   concurrent))
    loop = asyncio.get_event_loop()
    start = time()
    statuses = loop.run_until_complete(amain(total, concurrent))
    duration = time() - start

    failures = len([x for x in statuses if x != 200])
    successes = len([x for x in statuses if x == 200])

    print('\n', end='')
    print('Total duration: %f, RPS: %f' % (duration, total / duration))
    print('Failures: %i, Successes: %i' % (failures, successes))

    if failures:
        sys.exit(1)


if __name__ == '__main__':
    total = int(sys.argv[1]) if len(sys.argv) > 1 else TOTAL
    concurrent = int(sys.argv[2]) if len(sys.argv) > 2 else CONCURRENT
    main(total, concurrent)
