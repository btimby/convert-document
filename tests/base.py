from aiohttp.test_utils import AioHTTPTestCase

from preview import get_app


class PreviewTestCase(AioHTTPTestCase):
    async def get_application(self):
        return get_app()
