# derived from https://gist.github.com/six519/28802627584b21ba1f6a
# unlicensed
import os
import uno
import ctypes
import logging
import subprocess
import time
import mimetypes

import threading
from tempfile import NamedTemporaryFile

from lxml import etree
from collections import defaultdict, OrderedDict
from pantomime import normalize_mimetype, normalize_extension

from com.sun.star.beans import PropertyValue
from com.sun.star.connection import NoConnectException

from gs import preview_pdf


NS = {'oor': 'http://openoffice.org/2001/registry'}
NAME = '{%s}name' % NS['oor']
CONNECTION_STRING = "socket,host=localhost,port=2002,tcpNoDelay=1;urp;StarOffice.ComponentContext"  # noqa
RESOLVER_CLASS = 'com.sun.star.bridge.UnoUrlResolver'
DESKTOP_CLASS = 'com.sun.star.frame.Desktop'
DEFAULT_PORT = 2002
LIBREOFFICE_EVENT = threading.Event()
LIBREOFFICE_EVENT.set()
RESTART_COMMAND = ["supervisorctl", "restart", "libreoffice"]

LOGGER = logging.getLogger(__name__)


def restart_libreoffice():
    '''Ask supervisord to restart LibreOffice.'''
    LIBREOFFICE_EVENT.clear()
    try:
        cmd = RESTART_COMMAND
        subprocess.call(cmd)

    finally:
        LIBREOFFICE_EVENT.set()


class Formats(object):
    FILES = [
        '/usr/lib/libreoffice/share/registry/writer.xcd',
        '/usr/lib/libreoffice/share/registry/impress.xcd',
        '/usr/lib/libreoffice/share/registry/draw.xcd',
        # '/usr/lib/libreoffice/share/registry/calc.xcd',
    ]

    def __init__(self):
        self.media_types = defaultdict(list)
        self.extensions = defaultdict(list)
        for xcd_file in self.FILES:
            doc = etree.parse(xcd_file)
            path = './*[@oor:package="org.openoffice.TypeDetection"]/node/node'
            for tnode in doc.xpath(path, namespaces=NS):
                node = {}
                for prop in tnode.findall('./prop'):
                    name = prop.get(NAME)
                    for value in prop.findall('./value'):
                        node[name] = value.text

                name = node.get('PreferredFilter', tnode.get(NAME))
                media_type = normalize_mimetype(node.get('MediaType'),
                                                default=None)
                if media_type is not None:
                    self.media_types[media_type].append(name)

                for ext in self.parse_extensions(node.get('Extensions')):
                    self.extensions[ext].append(name)

    def parse_extensions(self, extensions):
        if extensions is not None:
            for ext in extensions.split(' '):
                if ext == '*':
                    continue
                ext = normalize_extension(ext)
                if ext is not None:
                    yield ext

    def get_filters(self, extension, media_type):
        filters = OrderedDict()
        for filter_name in self.media_types.get(media_type, []):
            filters[filter_name] = None
        for filter_name in self.extensions.get(extension, []):
            filters[filter_name] = None
        return filters.keys()


FORMATS = Formats()


class ConversionFailure(Exception):
    pass


class ConversionTimeout(ConversionFailure):
    pass


class PdfConverter(object):
    """Launch a background instance of LibreOffice and convert documents
    to PDF using it's filters.
    """

    PDF_FILTERS = (
        ("com.sun.star.text.GenericTextDocument", "writer_pdf_Export"),
        ("com.sun.star.text.WebDocument", "writer_web_pdf_Export"),
        ("com.sun.star.sheet.SpreadsheetDocument", "calc_pdf_Export"),
        ("com.sun.star.presentation.PresentationDocument",
         "impress_pdf_Export"),
        ("com.sun.star.drawing.DrawingDocument", "draw_pdf_Export"),
    )

    def __init__(self, host=None):
        context = uno.getComponentContext()
        self.resolver = \
            context.ServiceManager.createInstanceWithContext(
                RESOLVER_CLASS, context)
        self.connect()

    def connect(self):
        for i in range(2):
            # If LibreOffice is being restarted, wait for that to complete.
            LIBREOFFICE_EVENT.wait()

            try:
                context = self.resolver.resolve("uno:%s" % CONNECTION_STRING)
                return context.ServiceManager.createInstanceWithContext(
                    DESKTOP_CLASS, context)

            except NoConnectException:
                # TODO: if we have problems connecting, kill soffice and
                # supervisord will restart it.
                restart_libreoffice()

        raise ConversionFailure('Could not connect to LibreOffice')

    def convert_file(self, file_name, out_file, timeout=300):
        extension = os.path.splitext(file_name)[1]
        mimetype = mimetypes.guess_type(file_name)
        thread_id = threading.get_ident()

        # TODO: filters should be determined by CONVERTER, pass in mimetype
        # instead.
        filters = list(FORMATS.get_filters(extension[1:], mimetype))
        LOGGER.debug(filters)

        def terminate():
            '''Closure to terminate thread from timer.'''
            LOGGER.info('Terminating conversion thread due to timeout')
            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                thread_id, ctypes.py_object(ConversionTimeout))
            if res > 1:
                ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
                raise Exception('Failed to terminate thread')

        timer = threading.Timer(timeout, terminate)
        timer.start()
        try:
            desktop = self.connect()
            if desktop is None:
                raise ConversionFailure("Cannot connect to LibreOffice.")
            file_name = os.path.abspath(file_name)
            input_url = uno.systemPathToFileUrl(file_name)
            for filter_name in filters:
                props = self.get_input_properties(filter_name)
                doc = desktop.loadComponentFromURL(
                    input_url, '_blank', 0, props)
                if doc is None:
                    continue
                if hasattr(doc, 'refresh'):
                    doc.refresh()
                output_url = uno.systemPathToFileUrl(out_file)
                prop = self.get_output_properties(doc)
                doc.storeToURL(output_url, prop)
                doc.dispose()
                doc.close(True)
                del doc

        finally:
            timer.cancel()

    def get_input_properties(self, filter_name):
        return self.property_tuple({
            "Hidden": True,
            "MacroExecutionMode": 0,
            "ReadOnly": True,
            "FilterName": filter_name
        })

    def get_output_properties(self, doc):
        for (service, pdf) in self.PDF_FILTERS:
            if doc.supportsService(service):
                pageone = PropertyValue()
                pageone.Name = "PageRange"
                pageone.Value = "1"
                return self.property_tuple({
                    "FilterName": pdf,
                    "MaxImageResolution": 300,
                    "SelectPdfVersion": 1,
                    "FilterData": (pageone, ),
                })
        raise ConversionFailure("PDF export not supported.")

    def property_tuple(self, propDict):
        properties = []
        for k, v in propDict.items():
            property = PropertyValue()
            property.Name = k
            property.Value = v
            properties.append(property)
        return tuple(properties)


def preview_doc(path, width, height):
    start = time.time()
    converter = PdfConverter()
    with NamedTemporaryFile(suffix='.pdf') as t:
        try:
            converter.convert_file(path, t.name, timeout=30)

        finally:
            LOGGER.info('preview_doc(%s) took: %ss', path, time.time() - start)

        return preview_pdf(t.name, width, height)
