#!/usr/bin/env python3

#   Copyright (C) 2012  Povilas Kanapickas <povilas@radix.lt>
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

# This file examines all html files in the output directory and writes
# filename -> title mapping to a xml file.

import fnmatch
import os
import re

from link_map import LinkMap


# returns a dict { title -> filename }.
# directory - either 'output/reference' or 'reference'
def build_link_map(directory):
    # find all html files
    html_files = []
    for root, dirnames, filenames in os.walk(directory):
        for filename in fnmatch.filter(filenames, '*.html'):
            html_files.append(os.path.join(root, filename))

    link_map = LinkMap()

    for fn in sorted(html_files):
        f = open(fn, "r", encoding='utf-8')
        text = f.read()
        f.close()

        m = re.search(r'<script>[^<]*mw\.config\.set([^<]*wgPageName[^<]*)</script>', text)  # noqa
        if not m:
            continue
        text = m.group(1)
        text = re.sub(r'\s*', '', text)
        m = re.search(r'"wgPageName":"((?:\\"|[^"\\])+)"', text)
        if not m:
            continue

        title = m.group(1)
        # unescape quotes in page title
        title = title.replace(r'\"', r'"')

        target = os.path.relpath(os.path.abspath(fn),
                                 os.path.abspath(directory))
        link_map.add_link(title, target)
    return link_map


def main():
    link_map = build_link_map('output/reference')

    # create an xml file containing mapping between page title and actual
    # location
    link_map.write('output/link-map.xml')


if __name__ == "__main__":
    main()
