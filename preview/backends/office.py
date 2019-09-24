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

from preview.backends.base import BaseBackend
from preview.backends.pdf import PdfBackend
from preview.utils import log_duration


OOR = 'http://openoffice.org/2001/registry'
NAME = '{%s}name' % OOR

LOGGER = logging.getLogger(__name__)


class ConversionFailure(Exception):
    pass


class ConversionTimeout(ConversionFailure):
    pass


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
            for tnode in doc.xpath(path, namespaces={'oor': OOR }):
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


class OfficeConverter(object):
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
        self.formats = Formats()

    def connect(self):
        def _connect():
            context = uno.getComponentContext()
            resolver = \
                context.ServiceManager.createInstanceWithContext(
                    'com.sun.star.bridge.UnoUrlResolver', context)
            context = resolver.resolve(
                "uno:socket,host=localhost,port=2002,tcpNoDelay=1;urp;"
                "StarOffice.ComponentContext")
            return context.ServiceManager.createInstanceWithContext(
                'com.sun.star.frame.Desktop', context)

        for _ in range(2):
            try:
                return _connect()
            
            except:
                time.sleep(0.2)

    def convert_file(self, file_name, out_file, timeout=300):
        extension = os.path.splitext(file_name)[1]
        mimetype = mimetypes.guess_type(file_name)
        thread_id = threading.get_ident()

        # TODO: filters should be determined by CONVERTER, pass in mimetype
        # instead.
        filters = list(self.formats.get_filters(extension[1:], mimetype))
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


class OfficeBackend(BaseBackend):
    extensions = [
        'dot', 'docm', 'dotx', 'dotm', 'psw', 'doc', 'xls', 'ppt', 'wpd',
        'wps', 'csv', 'sdw', 'sgl', 'vor', 'docx', 'xlsx', 'pptx', 'xlsm',
        'xltx', 'xltm', 'xlt', 'xlw', 'dif', 'rtf', 'pxl', 'pps', 'ppsx',
        'odt', 'ods', 'odp'
    ]

    def __init__(self):
        self.office = OfficeConverter()

    @log_duration
    def preview(self, path, width, height):
        with NamedTemporaryFile(suffix='.pdf') as t:
            self.office.convert_file(path, t.name, timeout=30)
            return PdfBackend().preview(t.name, width, height)

    def check(self):
        try:
            self.office.connect()
            return True

        except Exception as e:
            LOGGER.exception(e)
            return False
