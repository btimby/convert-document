import os

from time import time

from aiohttp import web

from prometheus_client import Counter, Gauge, generate_latest, \
                              CONTENT_TYPE_LATEST, Summary

from preview.config import METRICS


REQUEST_TOTAL = Counter('aiohttp_request_total', 'Total requests', [
    'endpoint', 'method', 'status',
    ])
REQUEST_IN_PROGRESS = Gauge(
    'aiohttp_request_in_progress', 'Requests in progress', [
        'endpoint', 'method',
    ])
REQUEST_LATENCY = Summary(
    'aiohttp_request_latency_secs', 'Request latency', ['endpoint'])
PREVIEWS = Summary(
    'pvs_preview_time_secs', 'Preview generation time', [
        'extension', 'format'
    ])
PREVIEW_SIZE_IN = Summary(
    'pvs_preview_in_bytes', 'Size previewed files', [
        'backend', 'extension', 'format'
    ])
PREVIEW_SIZE_OUT = Summary(
    'pvs_preview_out_bytes', 'Size of preview image', [
        'backend', 'extension', 'format'
    ])
CONVERSIONS = Summary(
    'pvs_conversion_time_secs', 'Backend conversion time', [
        'backend', 'extension', 'format',
    ])
CONVERSION_ERRORS = Counter(
    'pvs_conversion_errors_total', 'Total errors during format conversion', [
        'backend', 'extension', 'format'])
STORAGE = Counter(
    'pvs_storage_operations_total', 'Storage operations', ['operation'])
STORAGE_BYTES = Gauge('pvs_storage_bytes_total', 'Total bytes in store')
STORAGE_FILES = Gauge('pvs_storage_files_total', 'Total files in store')
TRANSFER_LATENCY = Summary(
    'pvs_transfer_latency_secs', 'Uploads or downloads of files', [
    'operation'])
TRANSFERS_IN_PROGRESS = Gauge(
    'pvs_transfers_in_progress', 'Concurrent uploads / downloads', [
        'operation'])


def metrics_middleware():
    @web.middleware
    async def middleware_handler(request, handler):
        rip = REQUEST_IN_PROGRESS.labels(request.path, request.method)
        rl = REQUEST_LATENCY.labels(request.path)
        with rip.track_inprogress(), rl.time():
            response = await handler(request)

        REQUEST_TOTAL.labels(
            request.path, request.method, response.status).inc()

        return response

    return middleware_handler


async def metrics_handler(request):
    if not METRICS:
        raise web.HTTPNotFound()

    resp = web.Response(body=generate_latest())
    resp.content_type = CONTENT_TYPE_LATEST
    return resp
