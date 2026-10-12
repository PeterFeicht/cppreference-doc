#!/usr/bin/env python3
'''
    Copyright (C) 2017  Povilas Kanapickas <povilas@radix.lt>

    This file is part of cppreference-doc

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.
'''

import argparse
import json
import urllib.parse
import urllib.request

# the site turns away the user agent urllib introduces itself with
USER_AGENT = 'cppreference-doc (+https://github.com/PeterFeicht/cppreference-doc)'  # noqa


def install_user_agent():
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-Agent', USER_AGENT)]
    urllib.request.install_opener(opener)


def retrieve_page_names(root, ns_index):

    begin = None
    pages = []

    while True:
        params = {
            'action': 'query',
            'list': 'allpages',
            'apnamespace': ns_index,
            'aplimit': 500,
            'format': 'json'
        }
        if begin is not None:
            params['apcontinue'] = begin

        url = "{0}/api.php?{1}".format(root, urllib.parse.urlencode(params))

        with urllib.request.urlopen(url) as f:
            data = json.loads(f.read().decode('utf-8'))
            pages += [p['title'] for p in data['query']['allpages']]

            # MediaWiki 1.26 and later answer with 'continue'; the older
            # 'query-continue' is only sent when asked for
            if 'continue' in data and 'apcontinue' in data['continue']:
                begin = data['continue']['apcontinue']
            elif ('query-continue' in data and
                    'allpages' in data['query-continue'] and
                    'apcontinue' in data['query-continue']['allpages']):
                begin = data['query-continue']['allpages']['apcontinue']
            else:
                return pages


def export_pages(root, pages, output_path):
    params = {
        'wpDownload': '',
        'curonly': 1,
        'pages': '\n'.join(pages)
    }

    data = urllib.parse.urlencode(params)
    data = data.encode('ascii')
    url = "{0}/index.php?title=Special:Export&action=submit".format(root)

    urllib.request.urlretrieve(url, output_path, data=data)


def main():
    parser = argparse.ArgumentParser(prog='export.py')
    parser.add_argument('--url', type=str,
                        help='The URL to the root of the MediaWiki '
                             'installation')
    parser.add_argument('output_path', type=str,
                        help='The path to the XML file to save output to')
    parser.add_argument('ns_index', type=str, nargs='+',
                        help='The indices of the namespaces to retrieve')
    args = parser.parse_args()

    install_user_agent()

    pages = []
    for ns_index in args.ns_index:
        new_pages = retrieve_page_names(args.url, ns_index)
        print("Retrieved {0} pages for namespace {1}".format(len(new_pages),
                                                             ns_index))
        pages += new_pages

    pages = sorted(pages)
    export_pages(args.url, pages, args.output_path)


if __name__ == "__main__":
    main()
