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


def is_data_file(fn):
    # Everything the wiki serves next to the pages themselves: the skin, the
    # style sheets and scripts the loader assembles, and the fonts and the
    # favicon in case the site serves them again.
    return (fn in ['skins', 'resources', 'favicon.ico'] or
            fn.startswith('load.php') or fn.endswith('.ttf'))


def move_data_to_dir(src, dstdir):
    # the data should be the same for all languages, so the first language to
    # bring a file wins
    dst = os.path.join(dstdir, os.path.basename(src))
    if os.path.isdir(src) and os.path.isdir(dst):
        for fn in os.listdir(src):
            move_data_to_dir(os.path.join(src, fn), dst)
        os.rmdir(src)
    elif not os.path.exists(dst):
        shutil.move(src, dst)


def loader_modules(fn):
    match = re.search(r'modules=([^&]*)', fn)
    if match is None:
        return set()
    return set(urllib.parse.unquote(match.group(1)).split('|'))


def collapse_loader_files(data_path):
    # Since the 2026 upgrade the loader serves a style sheet cut to measure
    # for every page: the skin, plus whatever extensions that page happens to
    # draw on.  That is the same rules in a dozen combinations, and
    # convert_loader_name() gives them all one name, so keep the one that
    # asks for the most modules and throw the rest away.
    groups = dict()
    for fn in os.listdir(data_path):
        if fn.startswith('load.php'):
            groups.setdefault(convert_loader_name(fn), []).append(fn)

    for name, filenames in groups.items():
        filenames.sort(key=lambda fn: len(loader_modules(fn)))
        keep = loader_modules(filenames[-1])

        for fn in filenames[:-1]:
            missing = loader_modules(fn) - keep
            if missing:
                msg = '{0} asks for {1}, which no other {2} has'.format(
                    fn, ', '.join(sorted(missing)), name)
                raise Exception(msg)
            os.remove(os.path.join(data_path, fn))


def rearrange_archive(root):
    # rearrange the archive. {root} here is output/reference

    # before
    # {root}/en.cppreference.com/ : html
    # {root}/en.cppreference.com/load.php?... : data
    # {root}/en.cppreference.com/{skins,resources}/ : data
    # ... (other languages)
    # {root}/upload.cppreference.com/images/ : data

    # after
    # {root}/common/ : all common data
    # {root}/en/ : html for en
    # ... (other languages)

    data_path = os.path.join(root, 'common')
    rmtree_if_exists(data_path)
    os.makedirs(data_path)

    upload_path = os.path.join(root, 'upload.cppreference.com')
    move_dir_contents_to_dir(upload_path, data_path)
    shutil.rmtree(upload_path)

    for lang in ["en"]:
        path = os.path.join(root, lang + ".cppreference.com")
        html_path = os.path.join(root, lang)

        for fn in os.listdir(path):
            if is_data_file(fn):
                move_data_to_dir(os.path.join(path, fn), data_path)

        # what is left are the pages
        shutil.move(path, html_path)

    collapse_loader_files(data_path)

    # remove the XML source file
    for fn in fnmatch.filter(os.listdir(root), 'cppreference-export*.xml'):
        os.remove(os.path.join(root, fn))


def convert_loader_name(fn):
    # Converts complex URL to resources supplied by MediaWiki loader to a
    # simplified name
    if "modules=site&only=scripts" in fn:
        return "site_scripts.js"
    if re.search(r'modules=site(\.styles)?&only=styles', fn):
        return "site_modules.css"
    if "modules=startup&only=scripts" in fn:
        return "startup_scripts.js"
    if re.search("modules=skins.*&only=scripts", fn):
        return "skin_scripts.js"
    # the styles of the skin and of whatever extensions the page draws on,
    # which the loader serves in one file
    if re.search(r'modules=.*(ext|jquery|mediawiki|skins).*&only=styles', fn):
        return "ext.css"
    msg = 'Loader file {0} does not match any known files'.format(fn)
    raise Exception(msg)


def build_rename_map(root):
    # Returns a rename map: a map from old to new file name
    loader = re.compile(r'load\.php[\?@].*')
    query = re.compile(r'[\?@].*')
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
    # The loader sits at the root of the site, so the link is relative in a
    # page that wget got the file for and absolute in one that it did not.
    if re.search(r'(^|/)load\.php(?:[\?@]|%3[Ff])', target):
        return True
    return False


def transform_loader_link(target, file, root):
    # Loader links point into the common data directory wherever they came
    # from, so the link is built from scratch rather than adjusted
    abstarget = os.path.join(root, "common", convert_loader_name(target))
    return os.path.relpath(abstarget, os.path.dirname(file))


# The uploaded images moved out of /mwiki/ with the 2026 upgrade, but the
# pages still link to the old location.
UPLOAD_LINK = re.compile(
    r'(?:https?:)?//upload\.cppreference\.com/(?:mwiki/)?images/')


def is_upload_link(target):
    if UPLOAD_LINK.match(target):
        return True
    return False


def transform_upload_link(target, file, root):
    path = urllib.parse.unquote(UPLOAD_LINK.sub('', target))
    abstarget = os.path.join(root, "common", "images", path)
    return urllib.parse.quote(
        os.path.relpath(abstarget, os.path.dirname(file)))


def is_ranges_placeholder(target):
    if re.match(r'https?://[a-z]+\.cppreference\.com/(w/)?cpp/ranges(-[a-z]+)?-placeholder/.+', target):  # noqa
        return True
    return False


def transform_ranges_placeholder(target, file, root):
    # Placeholder link replacement is implemented in the MediaWiki site JS at
    # https://en.cppreference.com/w/MediaWiki:Common.js

    ranges = 'cpp/experimental/ranges' in file
    repl = (r'\1/cpp/experimental/ranges/\2' if ranges else r'\1/cpp/\2')

    if 'ranges-placeholder' in target:
        match = r'https?://([a-z]+)\.cppreference\.com/(?:w/)?cpp/ranges-placeholder/(.+)'  # noqa
    else:
        match = r'https?://([a-z]+)\.cppreference\.com/(?:w/)?cpp/ranges-([a-z]+)-placeholder/(.+)'  # noqa
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

    if is_upload_link(target):
        return transform_upload_link(target, file, root)

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


# remove analytics scripts; the New Relic agent is inlined into the head of
# every page and makes up the bulk of what a page weighs
def remove_analytics(html):
    sources = ['google-analytics.com/ga.js',
               'static.cloudflareinsights.com']
    texts = ['google-analytics.com/ga.js', 'pageTracker', 'NREUM']

    for el in html.xpath('/html/head/script') + html.xpath('/html/body/script'):
        if el.get('src') is not None:
            if any(src in el.get('src') for src in sources):
                el.getparent().remove(el)
        elif el.text is not None:
            if any(text in el.text for text in texts):
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
    info = etree.XPath(r"//a[re:test(@href, 'https?://[a-z]+\.cppreference\.com/(w/)?File:')]/..",  # noqa
                       namespaces={'re':'http://exslt.org/regular-expressions'})  # noqa
    for el in info(html):
        el.getparent().remove(el)


# make custom footer
def add_footer(html, root, fn):
    footer = html.xpath("//*[@id='footer']")[0]
    for child in footer.getchildren():
        id = child.get('id')
        if id == 'cpp-navigation':
            items = child.find('ul')
            items.clear()

            link = etree.SubElement(etree.SubElement(items, 'li'), 'a')
            url = re.sub(r'(..)/(.*)\.html',
                         r'https://\1.cppreference.com/\2',
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

    if html.getroot() is None:
        # The parser hands back no element at all -- rather than raising --
        # for a document with nothing in it, which is what a page that came
        # down truncated looks like.  Leave it as it is, so that one bad file
        # does not take the whole run with it.
        print('Not an HTML page: {}'.format(fn), file=output)
        return output.getvalue()

    remove_unused_external(html)
    remove_noprint(html, keep_footer=True)
    remove_analytics(html)
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


def preprocess_css(text):
    # the uploaded images and the skin files the site still points at the
    # locations they had before the 2026 upgrade; both now live next to the
    # style sheet in the common data directory
    text = UPLOAD_LINK.sub('images/', text)
    text = re.sub(r'(?:https?:)?//[a-z]+\.cppreference\.com/mwiki/skins/[^)\'"]*/images/',  # noqa
                  'skins/Cppreference2/resources/images/', text)

    # the loader stamps a version onto the images it serves; the copy of the
    # site has it as part of the file name, percent-encoded, and the files
    # were renamed without it
    text = re.sub(r'(url\([^)]*?)(?:[\?@]|%3[Ff])[^)\'"]*', r'\1', text)

    # the fonts are no longer served; the rules that are left behind name
    # locally installed fonts and the generic families to fall back to
    text = re.sub(r'@font-face\s*{[^}]*(?:https?:)?//[a-z]+\.cppreference\.com/[^}]*}',  # noqa
                  '', text)

    # QT Help viewer doesn't understand nth-child
    return text.replace('nth-child(1)', 'first-child')


def preprocess_css_file(fn):
    with open(fn, "r", encoding='utf-8') as f:
        text = f.read()

    with open(fn, "w", encoding='utf-8') as f:
        f.write(preprocess_css(text))


def preprocess_startup_script(fn):
    with open(fn, "r", encoding='utf-8') as f:
        text = f.read()

    text = re.sub(r'document\.write\([^)]+\);', '', text)

    with open(fn, "w", encoding='utf-8') as f:
        f.write(text)
