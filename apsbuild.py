#!/usr/bin/env python2
import os
from xml.dom import minidom
from fnmatch import fnmatch
from hashlib import sha256
from zipfile import ZipFile
from datetime import datetime
import argparse

def version_compare(v1, v2):
    if v1 == v2:
        return 0
    elif v2 > v1:
        return 1
    elif v2 < v1:
        return -1

class ApsPackageBuilder:
    APP_META_FILE = 'APP-META.xml'
    APP_LIST_FILE = 'APP-LIST.xml'
    PACKAGE_POSTFIX = '.app.zip'

    ignore_path = [
        APP_META_FILE,
        APP_LIST_FILE,
        '*' + PACKAGE_POSTFIX,
    ]

    package_dir = None
    output_dir = None

    _package_meta_dom = None

    def __init__(self, package_dir, output_dir):
        self.package_dir = package_dir
        self.output_dir = output_dir

    def build(self):
        package_meta = self._load_package_meta()
        package_list = self._get_package_list()
        package_filename = '-'.join([
            package_meta['name'], package_meta['version'], package_meta['release']
        ]) + self.PACKAGE_POSTFIX

        zip = ZipFile(os.path.join(self.output_dir, package_filename), 'w')

        for item in package_list:
            zip.write(item['path'], arcname=item['name'])

        app_meta = self._generate_app_meta_file()
        zip.writestr(self.APP_META_FILE, app_meta)

        if version_compare('1.2', package_meta['aps_version']) > -1:
            applist = self._generate_app_list_file(package_list, app_meta)
            zip.writestr(self.APP_LIST_FILE, applist)

        zip.close()

    def _get_package_list(self):
        base_dir = self.package_dir
        package_list = []

        def is_ignore(path, *args, **kwargs):
             for ipath in self.ignore_path:
                 if fnmatch(path, ipath):
                      return True
             return False

        for root, folders, files in os.walk(base_dir):
            for folder in folders:
                folder_path = os.path.join(root, folder)
                folder_name = os.path.relpath(folder_path, base_dir)

                if is_ignore(folder_name, base_dir):
                    continue

                package_list.append({
                    'path': folder_path,
                    'name': folder_name
                })

            for file in files:
                file_path = os.path.join(root, file)
                file_name = os.path.relpath(file_path, base_dir)

                if is_ignore(file_name, self.ignore_path):
                    continue

                package_list.append({
                    'path': file_path,
                    'name': file_name,
                    'sha256': self._sha256_file(file_path),
                    'size': os.path.getsize(file_path)
                })

        return package_list

    def _load_package_meta(self):
        app_meta_file = os.path.join(self.package_dir, self.APP_META_FILE)
        package_meta = { 'aps_version': None, 'name': None, 'version': None, 'release': None }

        dom = minidom.parse(app_meta_file)
        package_meta['aps_version'] = dom.documentElement.getAttribute('version')
        for element in dom.documentElement.childNodes:
            if element.nodeName in ['name', 'version', 'release']:
                if element.childNodes:
                    package_meta[element.nodeName] = element.childNodes[0].data
        assert all(map(lambda x: x, package_meta.values()))

        self._package_meta_dom = dom

        return package_meta

    def _sha256_file(self, file):
        return sha256(open(file, 'rb').read()).hexdigest()

    def _generate_app_list_file(self, package_list, app_meta=None):
        doc = minidom.Document()
        root = doc.createElement('files')
        root.setAttribute('xmlns', 'http://apstandard.com/ns/1')
        root.setAttribute('xmlns:ns2', 'http://www.w3.org/2000/09/xmldsig#')

        for item in package_list:
            if 'sha256' not in item:
                continue

            element = doc.createElement('file')
            element.setAttribute("sha256", item['sha256'])
            element.setAttribute("name", item['name'])
            element.setAttribute("size", str(item['size']))
            root.appendChild(element)

        if(app_meta is not None):
            element = doc.createElement('file')
            element.setAttribute("sha256", sha256(app_meta).hexdigest())
            element.setAttribute('name', self.APP_META_FILE)
            element.setAttribute('size', str(len(app_meta)))
            root.appendChild(element)

        doc.appendChild(root)

        return doc.toxml().encode('utf-8')

    def _generate_app_meta_file(self):
        dom = self._package_meta_dom
        dom.documentElement.setAttribute('packaged', datetime.utcnow().replace(microsecond=0).isoformat(sep='T'))
        return dom.toxml().encode('utf-8')

def main():
    current_dir = os.getcwd()
    input_dir = None
    output_dir = None

    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', default=current_dir)
    parser.add_argument('-i', '--input', default=current_dir)
    parser.add_argument('-v', '--validate')
    args = parser.parse_args();

    input_dir = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output)

    builder = ApsPackageBuilder(input_dir, output_dir)
    builder.build()

if __name__ == '__main__':
    main()
