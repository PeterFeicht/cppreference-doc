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

# Fits a page of the website for the Qt Help (.qch) rendition.
#
# This pass used to flatten the site stylesheet into `style` attributes and
# rewrite the layout as nested tables, because the only help viewer then was
# Qt Assistant's, which is QTextBrowser and understands a small corner of
# CSS.  Both viewers that read the archive now render with litehtml -- Qt
# Assistant since Qt 6.2, Qt Creator since 4.11 -- which follows a stylesheet
# link, so the pages keep their markup and their classes and are handed the
# site stylesheet whole; `commands/qch_css.py` builds it.
#
# What is left here is the handful of things a stylesheet cannot do.

import functools
import os
import shutil

from lxml import etree
from lxml.etree import strip_elements

from commands import qch_css


def preprocess_html_file(src_path, dst_path, stylesheet_href):
    with open(src_path, 'r', encoding='utf-8') as a_file:
        root = etree.fromstring(a_file.read().strip(), etree.HTMLParser())

    if root is None:
        # Nothing to fit: the parser hands back no element at all -- rather
        # than raising -- for a document with no content in it, which is what
        # a page that came down truncated looks like.  Carry it through as it
        # is, so that one bad file does not take the whole run with it.
        print('Not an HTML page: {}'.format(src_path))
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.copyfile(src_path, dst_path)
        return set(), (), set()

    page_css = lift_style_blocks(root)
    strip_scripts(root)
    drop_navbar_menus(root)
    link_stylesheet(root, stylesheet_href)
    clamp_rowspans(root)
    unstack_vertical_headers(root)
    rewrite_inline_styles(root)
    # last, so that it sees the `style` attributes the passes above leave
    color_classes = add_color_classes(root)
    images = referenced_images(root, src_path)

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with open(dst_path, 'wb') as a_file:
        root.getroottree().write(a_file, pretty_print=True, method='html',
                                 encoding='utf-8')

    return color_classes, page_css, images


def lift_style_blocks(root_el):
    # The pages carry a <style> block or two of their own, after the link to
    # the site stylesheet: what MediaWiki had to say about this page, and the
    # syntax highlighting of whichever language its code samples are in.
    # There turn out to be seven distinct ones across the whole site, so lift
    # them into the shared stylesheet rather than repeat them six thousand
    # times -- and so that the dark scheme can reach the colors in them.
    blocks = []

    for el in root_el.iter('style'):
        text = (el.text or '').strip()
        if text and text not in blocks:
            blocks.append(text)

    # `with_tail=False`: the text after a <style> belongs to the page
    strip_elements(root_el, 'style', with_tail=False)
    return tuple(blocks)


def drop_navbar_menus(root_el):
    # Every page carries the whole of the site's navigation twice over: once
    # as the bar of links across the top, and once as the menus that drop out
    # of it, which the stylesheet hides until the pointer is over them.
    # litehtml does have `:hover`, so the menus would work -- but a help pane
    # is a poor place to reach for one, and both viewers put a Contents and
    # an Index beside the page already.  They are a third of every page, so
    # leave them out; the bar itself stays.
    for el in root_el.xpath('//div[contains(@class, "t-navbar-menu")]'):
        remove_keeping_tail(el)


def remove_keeping_tail(el):
    # The text after the element belongs to the page, exactly as it does for
    # the <style> and <script> blocks stripped above; lxml would throw it out
    # with the element.
    parent = el.getparent()

    if el.tail:
        previous = el.getprevious()
        if previous is None:
            parent.text = (parent.text or '') + el.tail
        else:
            previous.tail = (previous.tail or '') + el.tail

    parent.remove(el)


def strip_scripts(root_el):
    # No help viewer runs these, and they are the bulk of every page's head:
    # the MediaWiki bootstrap, the user preferences it was serialised with,
    # and the analytics tag the site serves to a browser.  One of them sits
    # in the middle of the content, so keep what follows it.
    strip_elements(root_el, 'script', with_tail=False)


def link_stylesheet(root_el, href):
    # One link in place of the site's, named so that the help viewers find
    # the dark counterpart beside it; see `commands/qch_css.py`.
    head_el = root_el.find('head')
    if head_el is None:
        return

    for el in head_el.findall('link'):
        if el.get('rel') == 'stylesheet':
            head_el.remove(el)

    link = etree.SubElement(head_el, 'link')
    link.set('rel', 'stylesheet')
    link.set('type', 'text/css')
    link.set('href', href)


def get_table_row_groups(table_el):
    # A rowspan reaches no further than its own row group.  Rows that are not
    # in a `tbody` and friends make up a group of their own.
    loose_rows = []

    for el in table_el.iterchildren(['th', 'tr', 'thead', 'tbody', 'tfoot']):
        if el.tag in ['thead', 'tbody', 'tfoot']:
            if loose_rows:
                yield loose_rows
                loose_rows = []
            yield list(el.iterchildren(['th', 'tr']))
        else:
            loose_rows.append(el)

    if loose_rows:
        yield loose_rows


def clamp_rowspans(root_el):
    # A MediaWiki template asks a cell to span more rows than it can, as a way
    # of saying "all of them": the declaration tables carry a `rowspan` of 142
    # over a group of six rows.  HTML stops a rowspan at the end of the row
    # group, so a browser lines the overload markers up with the declarations
    # they number.  litehtml lays a table out as a flat run of rows with no
    # groups in it (`table_grid::add_cell`), and the marker ends up centred on
    # the whole table instead.  Say what we mean, so that both arrive at the
    # same place.
    for table_el in root_el.iter('table'):
        for rows in get_table_row_groups(table_el):
            for index, row_el in enumerate(rows):
                remaining = len(rows) - index

                for cell_el in row_el.iterchildren(['td', 'th']):
                    rowspan = cell_el.get('rowspan')
                    if rowspan is None:
                        continue

                    try:
                        too_many = int(rowspan) > remaining
                    except ValueError:
                        continue

                    if too_many:
                        cell_el.set('rowspan', str(remaining))


def style_declarations(style):
    for declaration in (style or '').split(';'):
        name, separator, value = declaration.partition(':')
        if separator:
            yield name.strip().lower(), value.strip()


def remove_style_property(el, name):
    kept = ['%s: %s' % declaration
            for declaration in style_declarations(el.get('style'))
            if declaration[0] != name]

    if kept:
        el.set('style', '; '.join(kept))
    else:
        el.attrib.pop('style', None)


def unstack_vertical_headers(root_el):
    # The compiler support tables stand their column headings on end, so that
    # a column need be no wider than the version number under it, and give
    # the row they stand in the height to do it in.  litehtml has no
    # `writing-mode`, so the headings come out lying across one another;
    # `qch-viewer.css` lays them out across and lets them wrap instead, after
    # which the row no longer needs the height.  A stylesheet cannot reach
    # from the heading to the row that holds it, so that part is done here.
    for el in root_el.xpath('//*[contains(@class, "t-vertical")]'
                            '/ancestor::tr[1]'):
        remove_style_property(el, 'height')


@functools.lru_cache(maxsize=None)
def clean_inline_style(style):
    return qch_css.clean_inline_style(style)


def rewrite_inline_styles(root_el):
    # The fonts and the type sizes the stylesheet pass settles are settled
    # here too, for the `style` attributes the wiki templates write: a rule
    # cannot reach into one.  Nearly every page carries a handful, and the
    # type scale depends on their being compressed along with the rest; see
    # `qch_css.clean_inline_style`.
    for el in root_el.xpath('//*[@style]'):
        style = el.get('style')
        cleaned = clean_inline_style(style)
        if cleaned != style:
            el.set('style', cleaned)


@functools.lru_cache(maxsize=None)
def color_classes_for_style(style):
    names = []

    for declaration in style.split(';'):
        name, separator, value = declaration.partition(':')
        if not separator:
            continue

        class_name = qch_css.class_for_declaration(name.strip().lower(),
                                                   value.strip())
        if class_name is not None and class_name not in names:
            names.append(class_name)

    return tuple(names)


def add_color_classes(root_el):
    # A stylesheet rule cannot outrank a `style` attribute on specificity, and
    # the wiki templates write a good deal of color into one: the green and
    # red of the compiler-support tables, the tints behind the revision
    # markers.  Name each of those colors with a class, so that the dark
    # stylesheet has something to hang an `!important` rule on.  Returns the
    # set of class names used.
    used = set()

    for el in root_el.xpath('//*[@style]'):
        names = color_classes_for_style(el.get('style'))
        if not names:
            continue

        existing = el.get('class')
        el.set('class', ' '.join(([existing] if existing else []) +
                                 list(names)))
        used.update(names)

    return used


# The page icon is the one <link> besides the stylesheet that survives the
# earlier passes, and it names a file of the site like any other image.
ICON_RELS = frozenset(['icon', 'shortcut icon', 'apple-touch-icon'])


def referenced_images(root_el, src_path):
    # The images a page asks for, as paths relative to the website root, so
    # that the archive can carry those and leave the rest of the site's
    # furniture behind.
    directory = os.path.dirname(src_path)
    images = set()

    for el in root_el.xpath('//img[@src]'):
        add_image(images, directory, el.get('src'))

    for el in root_el.xpath('//link[@href]'):
        if (el.get('rel') or '').strip().lower() in ICON_RELS:
            add_image(images, directory, el.get('href'))

    return images


def add_image(images, directory, url):
    url = url.split('?')[0].split('#')[0]
    if not url or '://' in url:
        return
    images.add(os.path.normpath(os.path.join(directory, url)))
