import os

from time import time

from aiohttp import web

from prometheus_client import Counter, Gauge, generate_latest, \
                              CONTENT_TYPE_LATEST, Summary


METRICS = os.environ.get('PVS_METRICS')

REQUEST_TOTAL = Counter('aiohttp_request_total', 'Total requests', [
    'endpoint', 'method', 'status',
    ])
REQUEST_IN_PROGRESS = Gauge(
    'aiohttp_request_in_progress', 'Requests in progress', [
        'endpoint', 'method',
    ])
REQUEST_LATENCY = Summary(
    'aiohttp_request_latency', 'Request latency', ['endpoint'])
PREVIEWS = Summary(
    'pvs_preview', 'Total previews requested', [
        'format', 'width', 'height',
    ])
CONVERSIONS = Summary(
    'pvs_conversion', 'Total conversions', [
        'backend', 'format',
    ])
CONVERSION_ERRORS = Counter(
    'pvs_conversion_errors', 'Total errors during format conversion', [
        'backend', 'format'])
STORAGE = Counter(
    'pvs_storage_operations', 'Storage operations', ['operation'])
STORAGE_BYTES = Gauge('pvs_storage_bytes_total', 'Total bytes in store')
STORAGE_FILES = Gauge('pvs_storage_files_total', 'Total files in store')


def metrics_middleware():
    @web.middleware
    async def middleware_handler(request, handler):
        REQUEST_IN_PROGRESS.labels(request.path, request.method).inc()
        try:
            with REQUEST_LATENCY.labels(request.path).time():
                response = await handler(request)

            REQUEST_TOTAL.labels(
                request.path, request.method, response.status).inc()

            return response

        finally:
            REQUEST_IN_PROGRESS.labels(request.path, request.method).dec()

    return middleware_handler


async def metrics_handler(request):
    if not METRICS:
        raise web.HTTPNotFound()

    resp = web.Response(body=generate_latest())
    resp.content_type = CONTENT_TYPE_LATEST
    return resp
