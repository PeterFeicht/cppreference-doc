#!/usr/bin/env python3

#   Copyright (C) 2011, 2012  Povilas Kanapickas <povilas@radix.lt>
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

from datetime import datetime
import fnmatch
import io
import os
import re
import shutil
import urllib.parse

from lxml import etree


def rmtree_if_exists(dir):
    if os.path.isdir(dir):
        shutil.rmtree(dir)


def move_dir_contents_to_dir(srcdir, dstdir):
    for fn in os.listdir(srcdir):
        shutil.move(os.path.join(srcdir, fn),
                    os.path.join(dstdir, fn))


def rearrange_archive(root):
    # rearrange the archive. {root} here is output/reference

    # before
    # {root}/en.cppreference.com/w/ : html
    # {root}/en.cppreference.com/mwiki/ : data
    # {root}/en.cppreference.com/ : data
    # ... (other languages)
    # {root}/upload.cppreference.com/mwiki/ : data

    # after
    # {root}/common/ : all common data
    # {root}/en/ : html for en
    # ... (other languages)

    data_path = os.path.join(root, 'common')
    rmtree_if_exists(data_path)
    shutil.move(os.path.join(root, 'upload.cppreference.com/mwiki'), data_path)
    shutil.rmtree(os.path.join(root, 'upload.cppreference.com'))

    for lang in ["en"]:
        path = os.path.join(root, lang + ".cppreference.com/")
        src_html_path = path + "w/"
        src_data_path = path + "mwiki/"
        html_path = os.path.join(root, lang)

        if os.path.isdir(src_html_path):
            shutil.move(src_html_path, html_path)

        if os.path.isdir(src_data_path):
            # the skin files should be the same for all languages thus we
            # can merge everything
            move_dir_contents_to_dir(src_data_path, data_path)

        # also copy the custom fonts
        shutil.copy(os.path.join(path, 'DejaVuSansMonoCondensed60.ttf'),
                    data_path)
        shutil.copy(os.path.join(path, 'DejaVuSansMonoCondensed75.ttf'),
                    data_path)
        # and the favicon
        shutil.copy(os.path.join(path, 'favicon.ico'), data_path)

        # remove what's left
        shutil.rmtree(path)

    # remove the XML source file
    for fn in fnmatch.filter(os.listdir(root), 'cppreference-export*.xml'):
        os.remove(os.path.join(root, fn))


def convert_loader_name(fn):
    # Converts complex URL to resources supplied by MediaWiki loader to a
    # simplified name
    if "modules=site&only=scripts" in fn:
        return "site_scripts.js"
    if "modules=site&only=styles" in fn:
        return "site_modules.css"
    if "modules=startup&only=scripts" in fn:
        return "startup_scripts.js"
    if re.search("modules=skins.*&only=scripts", fn):
        return "skin_scripts.js"
    if re.search("modules=.*ext.*&only=styles", fn):
        return "ext.css"
    msg = 'Loader file {0} does not match any known files'.format(fn)
    raise Exception(msg)


def build_rename_map(root):
    # Returns a rename map: a map from old to new file name
    loader = re.compile(r'load\.php\?.*')
    query = re.compile(r'\?.*')
    result = dict()

    # find files with invalid names -> rename all occurrences
    for fn in set(fn for _, _, filenames in os.walk(root) for fn in filenames):
        if loader.match(fn):
            result[fn] = convert_loader_name(fn)

        elif any((c in fn) for c in '?*"'):
            new_fn = query.sub('', fn)
            new_fn = new_fn.replace('"', '_q_')
            new_fn = new_fn.replace('*', '_star_')
            result[fn] = new_fn

    # find files that conflict on case-insensitive filesystems
    for dir, _, filenames in os.walk(root):
        seen = dict()
        for fn in (result.get(s, s) for s in filenames):
            low = fn.lower()
            num = seen.setdefault(low, 0)
            if num > 0:
                name, ext = os.path.splitext(fn)
                # add file with its path -> only rename that occurrence
                result[os.path.join(dir, fn)] = \
                    "{}.{}{}".format(name, num + 1, ext)
            seen[low] += 1

    return result


def rename_files(root, rename_map):
    for dir, old_fn in ((dir, fn)
                        for dir, _, filenames in os.walk(root)
                        for fn in filenames):
        src_path = os.path.join(dir, old_fn)

        new_fn = rename_map.get(old_fn)
        if new_fn:
            # look for case conflict of the renamed file
            new_path = os.path.join(dir, new_fn)
            new_fn = rename_map.get(new_path, new_fn)
        else:
            # original filename unchanged, look for case conflict
            new_fn = rename_map.get(src_path)
        if new_fn:
            dst_path = os.path.join(dir, new_fn)
            print("Renaming {0}\n      to {1}".format(src_path, dst_path))
            shutil.move(src_path, dst_path)


def find_html_files(root):
    # find files that need to be preprocessed
    html_files = []
    for dir, _, filenames in os.walk(root):
        for filename in fnmatch.filter(filenames, '*.html'):
            html_files.append(os.path.join(dir, filename))
    return html_files


def is_loader_link(target):
    if re.match(r'https?://[a-z]+\.cppreference\.com/mwiki/load\.php', target):
        return True
    return False


def transform_loader_link(target, file, root):
    # Absolute loader.php links need to be made relative
    abstarget = os.path.join(root, "common", convert_loader_name(target))
    return os.path.relpath(abstarget, os.path.dirname(file))


def is_ranges_placeholder(target):
    if re.match(r'https?://[a-z]+\.cppreference\.com/w/cpp/ranges(-[a-z]+)?-placeholder/.+', target):  # noqa
        return True
    return False


def transform_ranges_placeholder(target, file, root):
    # Placeholder link replacement is implemented in the MediaWiki site JS at
    # https://en.cppreference.com/w/MediaWiki:Common.js

    ranges = 'cpp/experimental/ranges' in file
    repl = (r'\1/cpp/experimental/ranges/\2' if ranges else r'\1/cpp/\2')

    if 'ranges-placeholder' in target:
        match = r'https?://([a-z]+)\.cppreference\.com/w/cpp/ranges-placeholder/(.+)'  # noqa
    else:
        match = r'https?://([a-z]+)\.cppreference\.com/w/cpp/ranges-([a-z]+)-placeholder/(.+)'  # noqa
        repl += (r'/\3' if ranges else r'/ranges/\3')

    # Turn absolute placeholder link into site-relative link
    reltarget = re.sub(match, repl + '.html', target)

    # Make site-relative link file-relative
    abstarget = os.path.join(root, reltarget)
    return os.path.relpath(abstarget, os.path.dirname(file))


def is_external_link(target):
    url = urllib.parse.urlparse(target)
    return url.scheme != '' or url.netloc != ''


def trasform_relative_link(rename_map, target, file):
    # urlparse returns (scheme, host, path, params, query, fragment)
    _, _, path, params, _, fragment = urllib.parse.urlparse(target)
    assert params == ''

    path = urllib.parse.unquote(path)
    path = path.replace('../../upload.cppreference.com/mwiki/', '../common/')
    path = path.replace('../mwiki/', '../common/')

    dir, fn = os.path.split(path)
    new_fn = rename_map.get(fn)
    if new_fn:
        # look for case conflict of the renamed file
        abstarget = os.path.normpath(
                os.path.join(os.path.dirname(file), dir, new_fn))
        new_fn = rename_map.get(abstarget, new_fn)
    else:
        # original filename unchanged, look for case conflict
        abstarget = os.path.normpath(os.path.join(os.path.dirname(file), path))
        new_fn = rename_map.get(abstarget)
    if new_fn:
        path = os.path.join(dir, new_fn)

    path = urllib.parse.quote(path)
    return urllib.parse.urlunparse(('', '', path, params, '', fragment))


# Transforms a link in the given file according to rename map.
# target is the link to transform.
# file is the path of the file the link came from.
# root is the path to the root of the archive.
def transform_link(rename_map, target, file, root):
    if is_loader_link(target):
        return transform_loader_link(target, file, root)

    if is_ranges_placeholder(target):
        return transform_ranges_placeholder(target, file, root)

    if is_external_link(target):
        return target

    return trasform_relative_link(rename_map, target, file)


def has_class(el, *classes_to_check):
    value = el.get('class')
    if value is None:
        return False
    classes = value.split(' ')
    for cl in classes_to_check:
        if cl != '' and cl in classes:
            return True
    return False


# remove non-printable elements
def remove_noprint(html, keep_footer=False):
    for el in html.xpath('//*'):
        if has_class(el, 'noprint', 'editsection') and \
                not (keep_footer and el.get('id') == 'cpp-footer-base'):
            el.getparent().remove(el)
        elif el.get('id') in ['toc', 'catlinks']:
            el.getparent().remove(el)


# remove see also links between C and C++ documentations
def remove_see_also(html):
    for el in html.xpath('//tr[@class]'):
        if not has_class(el, 't-dcl-list-item', 't-dsc'):
            continue

        child_tds = el.xpath('.//td/div[@class]')
        if not any(has_class(td, 't-dcl-list-see', 't-dsc-see')
                   for td in child_tds):
            continue

        # remove preceding separator, if any
        prev = el.getprevious()
        if prev is not None:
            child_tds = prev.xpath('.//td[@class]')
            if any(has_class(td, 't-dcl-list-sep') for td in child_tds):
                prev.getparent().remove(prev)

        el.getparent().remove(el)

    for el in html.xpath('//h3'):
        if len(el.xpath(".//span[@id = 'See_also']")) == 0:
            continue

        next = el.getnext()
        if next is None:
            el.getparent().remove(el)
        elif next.tag == 'table' and has_class(next, 't-dcl-list-begin') and \
                len(next.xpath('.//tr')) == 0:
            el.getparent().remove(el)
            next.getparent().remove(next)


# remove Google Analytics scripts
def remove_google_analytics(html):
    for el in html.xpath('/html/body/script'):
        if el.get('src') is not None:
            if 'google-analytics.com/ga.js' in el.get('src'):
                el.getparent().remove(el)
        elif el.text is not None:
            if 'google-analytics.com/ga.js' in el.text or \
                    'pageTracker' in el.text:
                el.getparent().remove(el)


# remove ads
def remove_ads(html):
    # Carbon Ads
    for el in html.xpath('//script[@src]'):
        if 'carbonads.com/carbon.js' in el.get('src'):
            el.getparent().remove(el)
    for el in html.xpath('/html/body/style'):
        if el.text is not None and '#carbonads' in el.text:
            el.getparent().remove(el)
    # BuySellAds
    for el in html.xpath('//script[@type]'):
        if 'buysellads.com' in el.text:
            el.getparent().remove(el)
    for el in html.xpath('//div[@id]'):
        if el.get('id').startswith('bsap_'):
            el.getparent().remove(el)


# remove links to file info pages (e.g. on images)
def remove_fileinfo(html):
    info = etree.XPath(r"//a[re:test(@href, 'https?://[a-z]+\.cppreference\.com/w/File:')]/..",  # noqa
                       namespaces={'re':'http://exslt.org/regular-expressions'})  # noqa
    for el in info(html):
        el.getparent().remove(el)


# make custom footer
def add_footer(html, root, fn):
    footer = html.xpath('//*[@id=\'footer\']')[0]
    for child in footer.getchildren():
        id = child.get('id')
        if id == 'cpp-navigation':
            items = child.find('ul')
            items.clear()

            link = etree.SubElement(etree.SubElement(items, 'li'), 'a')
            url = re.sub(r'(..)/(.*)\.html',
                         r'https://\1.cppreference.com/w/\2',
                         os.path.relpath(fn, root))
            url = re.sub(r'(.*)/index', r'\1/', url)
            link.set('href', url)
            link.text = 'Online version'

            li = etree.SubElement(items, 'li')
            mtime = datetime.fromtimestamp(os.stat(fn).st_mtime)
            li.text = "Offline version retrieved {}.".format(
                    mtime.isoformat(sep=' ', timespec='minutes'))
        elif id == 'footer-info':
            pass
        else:
            footer.remove(child)


# remove external links to unused resources
def remove_unused_external(html):
    for el in html.xpath('/html/head/link'):
        if el.get('rel') in ('alternate', 'search', 'edit', 'EditURI'):
            el.getparent().remove(el)
        elif el.get('rel') == 'shortcut icon':
            (head, tail) = os.path.split(el.get('href'))
            el.set('href', os.path.join(head, 'common', tail))


def preprocess_html_file(root, fn, rename_map):
    parser = etree.HTMLParser()
    html = etree.parse(fn, parser)
    output = io.StringIO()

    remove_unused_external(html)
    remove_noprint(html, keep_footer=True)
    remove_google_analytics(html)
    remove_ads(html)
    remove_fileinfo(html)

    add_footer(html, root, fn)

    # apply changes to links caused by file renames
    for el in html.xpath('//*[@src]'):
        el.set('src', transform_link(rename_map, el.get('src'), fn, root))
    for el in html.xpath('//*[@href]'):
        el.set('href', transform_link(rename_map, el.get('href'), fn, root))

    for err in list(parser.error_log):
        print("HTML WARN: {0}".format(err), file=output)

    html.write(fn, encoding='utf-8', method='html')
    return output.getvalue()


def preprocess_css_file(fn):
    f = open(fn, "r", encoding='utf-8')
    text = f.read()
    f.close()

    # note that query string is not used in css files

    text = text.replace('../DejaVuSansMonoCondensed60.ttf',
                        'DejaVuSansMonoCondensed60.ttf')
    text = text.replace('../DejaVuSansMonoCondensed75.ttf',
                        'DejaVuSansMonoCondensed75.ttf')

    text = text.replace('../../upload.cppreference.com/mwiki/images/',
                        'images/')

    # QT Help viewer doesn't understand nth-child
    text = text.replace('nth-child(1)', 'first-child')

    f = open(fn, "w", encoding='utf-8')
    f.write(text)
    f.close()


def preprocess_startup_script(fn):
    with open(fn, "r", encoding='utf-8') as f:
        text = f.read()

    text = re.sub(r'document\.write\([^)]+\);', '', text)

    with open(fn, "w", encoding='utf-8') as f:
        f.write(text)
