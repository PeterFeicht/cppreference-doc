#!/usr/bin/env python3

#   Copyright (C) 2018  Monika Kairaityte <monika@kibit.lt>
#   Copyright (C) 2026  Cristian Adam <cristian.adam@gmail.com>
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

import argparse
import concurrent.futures
import os
import shutil

from commands import preprocess_qch_html
from commands import qch_css
from commands import qch_svg


def copy_images(source_root, dest_root, images):
    # Only the HTML of the site used to be carried into the .qch, so every
    # figure the pages draw on -- the diagrams of what `begin` and `end`
    # point at, the inheritance charts of the exception types -- arrived as a
    # broken image.  Take the ones that are asked for, which the HTML pass
    # and the stylesheet between them have just told us.
    copied = 0

    for src_path in sorted(images):
        rel_path = os.path.relpath(src_path, source_root)
        if rel_path.startswith(os.pardir):
            # a page reaching outside the copy of the website
            print('Image outside the archive: {}'.format(src_path))
            continue

        if not os.path.isfile(src_path):
            print('Missing image: {}'.format(src_path))
            continue

        dst_path = os.path.join(dest_root, rel_path)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        copy_image(src_path, dst_path)
        copied += 1

    return copied


def copy_image(src_path, dst_path):
    # A drawing is handed a dark scheme of its own on the way, and the pixels
    # to be drawn sharply; see `commands/qch_svg.py`.  Everything else travels
    # as it is.
    if not src_path.lower().endswith('.svg'):
        shutil.copyfile(src_path, dst_path)
        return

    with open(src_path, 'rb') as a_file:
        data = qch_svg.fit_for_the_viewer(a_file.read())

    with open(dst_path, 'wb') as a_file:
        a_file.write(data)


def main():
    parser = argparse.ArgumentParser(prog='preprocess_qch.py')
    parser.add_argument(
        '--src', required=True, type=str,
        help='Source directory where the preprocessed archive resides')

    parser.add_argument(
        '--dst', required=True, type=str,
        help='Destination folder to put the Qt Help archive to')

    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    source_root = args.src
    dest_root = args.dst
    verbose = args.verbose

    # Start from nothing.  The Makefile hands whatever is left in here to the
    # help project as a list of files, so anything a previous run wrote and
    # this one does not would be shipped inside the .qch -- and a run that
    # failed half way would leave a directory that make takes for finished
    # work.
    if os.path.isdir(dest_root):
        shutil.rmtree(dest_root)

    paths_list = []

    for root, _, files in os.walk(source_root):
        for file in files:
            if file.endswith('.html'):
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, source_root)
                dst_path = os.path.join(dest_root, rel_path)
                paths_list.append((src_path, dst_path))

    css_dir = os.path.join(dest_root, qch_css.CSS_DIR)
    color_classes = set()
    page_css = []
    images = set()

    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(preprocess_qch_html.preprocess_html_file,
                            src_path, dst_path,
                            qch_css.stylesheet_href(css_dir, dst_path))
            for src_path, dst_path in paths_list
        ]

        for i, future in enumerate(futures):
            if verbose:
                print('Processing file: {}/{}: {}'.format(
                        i + 1, len(paths_list), paths_list[i][1]))

            classes, styles, page_images = future.result()
            color_classes |= classes
            images |= page_images
            for style in styles:
                if style not in page_css:
                    page_css.append(style)

    print('Processed {} pages'.format(len(paths_list)))

    # the pages link these; see `commands/qch_css.py`
    site_css = qch_css.read_site_css(source_root)
    qch_css.write_stylesheets(css_dir, site_css, page_css, color_classes)
    print('Wrote {} stylesheets, naming {} colors carried inline'.format(
            len(qch_css.LIGHT_CSS_NAMES) + 1, len(color_classes)))

    images |= qch_css.referenced_images(site_css, source_root)
    print('Copied {} images'.format(
            copy_images(source_root, dest_root, images)))


if __name__ == "__main__":
    main()
