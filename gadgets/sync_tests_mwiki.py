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

# This script depends on pywikibot framework. Install using
# pip install pywikibot --pre

import os

# pywikibot loads 'user-config.py' file in current directory by default
# disable this behavior. We want the same information to be supplied via
# command line.
os.environ['PYWIKIBOT2_NO_USER_CONFIG']='1'

import argparse
import itertools
import shutil
import sys
import urllib

import pywikibot
import pywikibot.config2
import pywikibot.data.api
import pywikibot.pagegenerators

SYNC_DIRECTION_UPLOAD = 1
SYNC_DIRECTION_DOWNLOAD = 2

def get_path_from_title(title):
    title = title.replace(' ', '_')

    pathnames = title.replace(':', '/').split('/')
    pathnames = [ p for p in pathnames if p != '' ]

    return '/'.join(pathnames) + '.mwiki'

def fix_whitespace(text):
    # Trims trailing whitespace on lines
    # Adds trailing newline if not present. MediaWiki strips it and we don't
    # want to fight with editors.

    # Note that splitlines does not return empty line corresponding to the
    # trailing newline character.
    lines = text.splitlines()
    lines = [ l.rstrip() for l in lines ]
    return '\n'.join(lines) + '\n'

def sync_single_page(page, direction, dest_root):
    title = page.title()
    text = page.get(get_redirect=True)

    dest_path = os.path.join(dest_root, get_path_from_title(title))

    if direction == SYNC_DIRECTION_UPLOAD:
        if not os.path.exists(dest_path):
            return
        with open(dest_path, 'r', encoding='utf-8') as file:
            new_text = file.read()
        if fix_whitespace(text) != fix_whitespace(new_text):
            page.put(new_text, 'sync with git')
            print('Uploaded {0}'.format(title))

    elif direction == SYNC_DIRECTION_DOWNLOAD:
        dest_dir = os.path.dirname(dest_path)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        with open(dest_path, 'w', encoding='utf-8') as file:
            file.write(fix_whitespace(text))
        print('Downloaded {0}'.format(dest_path))

def remove_no_longer_existing_pages(pages, dest_root):
    paths = []
    for dir, dirnames, filenames in os.walk(dest_root):
        for filename in filenames:
            rel_path = os.path.join(os.path.relpath(dir, dest_root), filename)
            if rel_path.startswith('./'):
                rel_path = rel_path[2:]
            paths.append(rel_path)

    paths = set(paths)

    existing_paths = set([get_path_from_title(page.title()) for page in pages])
    deleted_paths = paths - existing_paths

    for path in deleted_paths:
        os.remove(os.path.join(dest_root, path))

def perform_sync(url, direction, dest_root, title_filter, user, password,
                 http_user, http_pass):

    if direction == SYNC_DIRECTION_DOWNLOAD:
        if os.path.exists(dest_root):
            shutil.rmtree(dest_root)
        os.makedirs(dest_root)

    # Supply information to config that would otherwise be defined in
    # user-config.py
    pywikibot.config2.family = 'cppreference'
    pywikibot.config2.mylang = 'en'
    pywikibot.config2.family_files['cppreference'] = url
    pywikibot.config2.step = 100
    pywikibot.config2.put_throttle = 0

    if http_user is not None:
        netloc = urllib.parse.urlparse(url).netloc
        pywikibot.config2.authenticate[netloc] = (http_user, http_pass)

    site = pywikibot.Site(user=user, fam='cppreference')

    # pywikibot.login.LoginManager seems to be not fully implemented and broken
    # Comments in the source suggest that data.api module contains full
    # implementation. Use it instead.
    login_manager = pywikibot.data.api.LoginManager(password=password,
                                                    site=site, user=user)
    login_manager.login()

    pages = itertools.chain(
        pywikibot.pagegenerators.AllpagesPageGenerator(namespace=0, site=site),
        pywikibot.pagegenerators.AllpagesPageGenerator(namespace=10, site=site)
    )
    pages = pywikibot.pagegenerators.PreloadingGenerator(pages, groupsize=100)

    pages = list(pages)
    for page in pages:
        if title_filter(page.title()):
            sync_single_page(page, direction, dest_root)

    if direction == SYNC_DIRECTION_DOWNLOAD:
        remove_no_longer_existing_pages(pages, dest_root)

def create_filter_empty():
    def filter_fun(title):
        return True
    return filter_fun

def create_filter_for_titles_beginning_with(filter_paths):
    def filter_fun(title):
        for path in filter_paths:
            if title.startswith(path):
                return True
        return False

    return filter_fun

def main():
    parser = argparse.ArgumentParser(prog='sync_mediawiki')
    parser.add_argument('url', type=str,
                        help='URL to root of a MediaWiki instance')
    parser.add_argument('direction', type=str,
                        help='"upload" or "download"')
    parser.add_argument('destination_root', type=str,
                        help='Destination directory to place results to')
    parser.add_argument('user', type=str,
                        help='Username to perform bot operations under')
    parser.add_argument('password', type=str,
                        help='User password to authenticate with')
    parser.add_argument('--http_user', type=str, default=None,
            help='Username to use for HTTP authentication, if needed')
    parser.add_argument('--http_pass', type=str, default=None,
            help='Password to use for HTTP authentication, if needed')
    args = parser.parse_args()

    direction = None
    if args.direction == 'upload':
        direction = SYNC_DIRECTION_UPLOAD
    elif args.direction == 'download':
        direction = SYNC_DIRECTION_DOWNLOAD
    else:
        print('Incorrect direction option. Expected "upload" or "download"')
        sys.exit(1)

    if args.destination_root == '' or args.destination_root == '.':
        print("The output directory can not be the current directory")
        sys.exit(1)

    title_filter = create_filter_for_titles_beginning_with('test-gadget-stdrev/')
    perform_sync(args.url, direction, args.destination_root, title_filter,
                 args.user, args.password, args.http_user, args.http_pass)

if __name__ == '__main__':
    main()
