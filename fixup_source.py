#!/usr/bin/env python3

#   Copyright (C) 2026  Cristian Adam
#
#   This file is part of cppreference-doc
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see http://www.gnu.org/licenses/.

'''Downloads the files the website points at the wrong place.

The 2026 upgrade moved the wiki out of /w/ and the uploaded images and skin
files out of /mwiki/, but the pages and the site style sheet were not updated
along with it: they still link to the /mwiki/ locations, which now answer 404.
wget never gets those files, so fetch them here from where they live now and
store them under the path the links use.  The rest of the pipeline then sees
the layout it has always seen.
'''

import argparse
import os
import re
import urllib.error
import urllib.request

# <img src="https://upload.cppreference.com/mwiki/images/0/06/foo.svg">
UPLOAD_REF = re.compile(r'upload\.cppreference\.com/mwiki/images/'
                        r'([^\s"\'()<>]+)')

# background-image:url(//en.cppreference.com/mwiki/skins/cppreference2/images/navbar-tab.png)  # noqa
SKIN_REF = re.compile(r'en\.cppreference\.com/mwiki/'
                      r'(skins/[^\s"\'()<>]*/images/([^\s"\'()<>]+))')

UPLOAD_URL = 'https://upload.cppreference.com/images/{}'
SKIN_URL = ('https://en.cppreference.com/skins/Cppreference2/resources/'
            'images/{}')

# the site turns away the user agent urllib introduces itself with
USER_AGENT = 'cppreference-doc (+https://github.com/PeterFeicht/cppreference-doc)'  # noqa


def find_source_files(root):
    # the style sheets are named after the loader URL that produced them
    for dir, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith(('.html', '.css')) or fn.startswith('load.php'):
                yield os.path.join(dir, fn)


def find_references(root):
    # Returns a map from the path to store the file at to the URL to get it
    # from, for every file referenced from a downloaded page or style sheet
    # that wget could not have downloaded itself.
    result = dict()

    for fn in find_source_files(root):
        with open(fn, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()

        # both are stored where the site serves them now, next to the files
        # that wget did get, rather than where the references point
        for match in UPLOAD_REF.finditer(text):
            path = os.path.join(root, 'upload.cppreference.com', 'images',
                                *match.group(1).split('/'))
            result[path] = UPLOAD_URL.format(match.group(1))

        for match in SKIN_REF.finditer(text):
            path = os.path.join(root, 'en.cppreference.com', 'skins',
                                'Cppreference2', 'resources', 'images',
                                match.group(2))
            result[path] = SKIN_URL.format(match.group(2))

    return result


def already_downloaded(path):
    # The loader stamps a version onto the files it serves, and wget keeps
    # that as part of the file name, so a file that is already there can
    # carry a query string the reference does not have.
    directory, name = os.path.split(path)
    if not os.path.isdir(directory):
        return False

    return any(fn == name or fn.startswith(name + '?') or
               fn.startswith(name + '@') for fn in os.listdir(directory))


def download(path, url):
    if already_downloaded(path):
        return True

    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request) as response:
            data = response.read()
    except urllib.error.HTTPError as err:
        print('FAILED {0}: {1}'.format(url, err))
        return False

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as a_file:
        a_file.write(data)

    print('{0} -> {1}'.format(url, path))
    return True


def main():
    parser = argparse.ArgumentParser(prog='fixup_source.py')
    parser.add_argument(
        '--src', type=str, default='reference',
        help='Directory the raw website copy was downloaded to')
    args = parser.parse_args()

    references = find_references(args.src)
    failed = [url for path, url in sorted(references.items())
              if not download(path, url)]

    print('{0} of {1} files downloaded'.format(
        len(references) - len(failed), len(references)))
    if failed:
        raise Exception('Could not download {0}'.format(', '.join(failed)))


if __name__ == '__main__':
    main()
