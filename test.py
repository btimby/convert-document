import os
import sys
import random
import asyncio
import logging

from aiohttp import ClientSession

from preview.utils import log_duration


URL = os.environ.get('URL', 'http://localhost:3000/preview/')
TOTAL = 10000
CONCURRENT = 20
PATHS = [
    'agreement.docx', 'candea.pptx', 'sample.doc', 'sample.odt', 'bg.png',
    'Quicktime_Video.mov', 'sample.docx', 'sample.pdf',
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
            async with session.get(URL, params=params) as response:
                res = await response.read()
                print(i, response.status, len(res), res[:20])
                return response.status

    # Create client session that will ensure we dont open new connection
    # per each request.
    async with ClientSession() as session:
        for i in range(total):
            params = {
                'path': random.choice(PATHS),
            }
            task = asyncio.ensure_future(fetch(i, params))
            tasks.append(task)

        statuses = asyncio.gather(*tasks)
        await statuses

    return statuses


@log_duration
def main(count, concurrent):
    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(run(count, concurrent))
    statuses = loop.run_until_complete(future)

    assert all(200 == x for x in statuses), 'Some requests failed'


if __name__ == '__main__':
    total = int(sys.argv[1]) if len(sys.argv) > 1 else TOTAL
    concurrent = int(sys.argv[2]) if len(sys.argv) > 2 else CONCURRENT
    main(total, concurrent)
