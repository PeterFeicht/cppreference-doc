#!/usr/bin/env python3
'''
    Copyright (C) 2016-2017  Povilas Kanapickas <povilas@radix.lt>

    This file is part of cppreference.com

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.
'''

import argparse
import fnmatch
import os
import re
import sys


def get_html_files(root):
    files = []
    for dir, dirnames, filenames in os.walk(root):
        for filename in fnmatch.filter(filenames, '*.html'):
            files.append(os.path.join(dir, filename))
    return files

def main():
    parser = argparse.ArgumentParser(prog='replace_tests_base')
    parser.add_argument('root', type=str, help='Root directory')
    parser.add_argument('url', type=str, help='Base Selenium URL')
    args = parser.parse_args()

    if not os.path.isdir(args.root):
        print('Root directory {0} does not exist'.format(args.root))
        sys.exit(1)

    paths = get_html_files(args.root)

    for path in paths:
        print('Processing {0}'.format(path))
        with open(path, 'r', encoding='utf-8') as file:
            text = file.read()

        # TODO user proper XML parser, not this hack
        text = re.sub('<link rel="selenium.base" href="(.*)" />',
                      '<link rel="selenium.base" href="' + args.url + '" />', text)

        with open(path, 'w', encoding='utf-8') as file:
            file.write(text)

if __name__ == '__main__':
    main()
