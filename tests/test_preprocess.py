#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#   Copyright (C) 2018  Monika Kairaityte <monika@kibit.lt>
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

import contextlib
import io
import os
import sys
import unittest
import unittest.mock

from lxml import etree

from commands.preprocess import build_rename_map
from commands.preprocess import convert_loader_name
from commands.preprocess import has_class
from commands.preprocess import is_external_link
from commands.preprocess import is_ranges_placeholder
from commands.preprocess import remove_ads
from commands.preprocess import remove_fileinfo
from commands.preprocess import remove_google_analytics
from commands.preprocess import remove_noprint
from commands.preprocess import remove_see_also
from commands.preprocess import remove_unused_external
from commands.preprocess import rename_files
from commands.preprocess import transform_ranges_placeholder
from commands.preprocess import trasform_relative_link


class DummyFile(object):
    def write(self, x):
        pass


# From https://stackoverflow.com/a/2829036/1849769
@contextlib.contextmanager
def nostdout():
    save_stdout = sys.stdout
    sys.stdout = DummyFile()
    yield
    sys.stdout = save_stdout


class TestConvertLoaderName(unittest.TestCase):
    def test_convert_loader_name(self):
        url = 'http://en.cppreference.com/mwiki/load.php?debug=false&lang=en&modules=site&only=scripts&skin=cppreference2&*'  # noqa
        self.assertEqual('site_scripts.js', convert_loader_name(url))

        url = 'http://en.cppreference.com/mwiki/load.php?debug=false&lang=en&modules=site&only=styles&skin=cppreference2&*'  # noqa
        self.assertEqual('site_modules.css', convert_loader_name(url))

        url = 'http://en.cppreference.com/mwiki/load.php?debug=false&lang=en&modules=skins.cppreference2&only=scripts&skin=cppreference2&*'  # noqa
        self.assertEqual('skin_scripts.js', convert_loader_name(url))

        url = 'http://en.cppreference.com/mwiki/load.php?debug=false&lang=en&modules=startup&only=scripts&skin=cppreference2&*'  # noqa
        self.assertEqual('startup_scripts.js', convert_loader_name(url))

        url = 'http://en.cppreference.com/mwiki/load.php?debug=false&lang=en&modules=ext.gadget.ColiruCompiler%2CMathJax%7Cext.rtlcite%7Cmediawiki.legacy.commonPrint%2Cshared%7Cskins.cppreference2&only=styles&skin=cppreference2&*'  # noqa
        self.assertEqual('ext.css', convert_loader_name(url))

        with self.assertRaises(Exception):
            convert_loader_name('')


class TestHasClass(unittest.TestCase):
    def test_has_class(self):
        el = etree.Element('tag')
        self.assertEqual(False, has_class(el))
        self.assertEqual(False, has_class(el, ''))
        self.assertEqual(False, has_class(el, 'a'))
        self.assertEqual(False, has_class(el, 'tag'))

        el.set('class', '')
        self.assertEqual(False, has_class(el, ))
        self.assertEqual(False, has_class(el, ''))
        self.assertEqual(False, has_class(el, 'a'))
        self.assertEqual(False, has_class(el, 'tag'))

        el.set('class', 'a')
        self.assertEqual(False, has_class(el, ))
        self.assertEqual(False, has_class(el, ''))
        self.assertEqual(True, has_class(el, 'a'))
        self.assertEqual(False, has_class(el, 'b'))
        self.assertEqual(False, has_class(el, 'tag'))
        self.assertEqual(True, has_class(el, 'a', 'b'))
        self.assertEqual(True, has_class(el, 'b', 'a'))
        self.assertEqual(False, has_class(el, 'b', 'c'))

        el.set('class', 'a b')
        self.assertEqual(False, has_class(el, ))
        self.assertEqual(False, has_class(el, ''))
        self.assertEqual(True, has_class(el, 'a'))
        self.assertEqual(True, has_class(el, 'b'))
        self.assertEqual(False, has_class(el, 'tag'))
        self.assertEqual(True, has_class(el, 'a', 'b'))
        self.assertEqual(True, has_class(el, 'b', 'a'))
        self.assertEqual(True, has_class(el, 'b', 'c'))

        el.set('class', 'a  b')
        self.assertEqual(False, has_class(el, ))
        self.assertEqual(False, has_class(el, ''))
        self.assertEqual(True, has_class(el, 'a'))
        self.assertEqual(True, has_class(el, 'b'))
        self.assertEqual(False, has_class(el, 'tag'))
        self.assertEqual(True, has_class(el, 'a', 'b'))
        self.assertEqual(True, has_class(el, 'b', 'a'))
        self.assertEqual(True, has_class(el, 'b', 'c'))


class TestIsExternalLink(unittest.TestCase):
    def test_is_external_link(self):
        external = [
            'http://example.com',
            'https://example.com',
            'ftp://example.com',
            'ftps://example.com',
            'slack://example.com',
            'https:///foo.html',  # Not technically external,
                                  # but we say so anyway
            '//example.com'
        ]
        for link in external:
            self.assertTrue(is_external_link(link),
                            msg="Should be external: {}".format(link))

        relative = [
            '/example.com',
            '../foo.html',
            'foo.html',
            'foo'
        ]
        for link in relative:
            self.assertFalse(is_external_link(link),
                             msg="Should not be external: {}".format(link))


class TestPlaceholderLinks(unittest.TestCase):
    # Placeholder link replacement is implemented in the MediaWiki site JS at
    # https://en.cppreference.com/w/MediaWiki:Common.js

    def test_is_ranges_placeholder(self):
        match = [
            'http://en.cppreference.com/w/cpp/ranges-placeholder/concepts/Assignable',  # noqa
            'http://en.cppreference.com/w/cpp/ranges-placeholder/iterator/Incrementable',  # noqa
            'http://en.cppreference.com/w/cpp/ranges-algorithm-placeholder/all_any_none_of',  # noqa
            'http://en.cppreference.com/w/cpp/ranges-iterator-placeholder/dangling',  # noqa
            'http://en.cppreference.com/w/cpp/ranges-utility-placeholder/swap',  # noqa
        ]
        for target in match:
            self.assertTrue(is_ranges_placeholder(target),
                            msg="Should match '{}'".format(target))

            target = target.replace("http://", "https://")
            self.assertTrue(is_ranges_placeholder(target),
                            msg="Should match '{}'".format(target))

        nomatch = [
            'http://en.cppreference.com/w/cpp/ranges--placeholder/swap',
            'https://en.cppreference.com/w/cpp/ranges--placeholder/swap',
            'http://www.mediawiki.org/',
            'http://en.cppreference.com/w/Cppreference:About',
            'http://en.wikipedia.org/wiki/Normal_distribution',
            'https://www.mediawiki.org/',
            'https://en.cppreference.com/w/Cppreference:About',
            'https://en.wikipedia.org/wiki/Normal_distribution',
            'w/cpp.html',
            'w/cpp/language/expressions.html',
            '../utility/functional/is_placeholder.html',
            'utility/functional/placeholders.html',
            'w/cpp/experimental/ranges.html',
        ]
        for target in nomatch:
            self.assertFalse(is_ranges_placeholder(target),
                             msg="Should not match '{}'".format(target))

    def test_transform_ranges_placeholder(self):
        entries = [
            # (target, file, expected)
            ('http://en.cppreference.com/w/cpp/ranges-placeholder/concepts/Assignable',  # noqa
             'output/reference/en/cpp/concepts/ConvertibleTo.html',
             'Assignable.html'),

            ('http://en.cppreference.com/w/cpp/ranges-placeholder/concepts/Assignable',  # noqa
             'output/reference/en/cpp/concepts/long/path/ConvertibleTo.html',
             '../../Assignable.html'),

            ('http://en.cppreference.com/w/cpp/ranges-placeholder/concepts/Assignable',  # noqa
             'output/reference/en/cpp/other/path/ConvertibleTo.html',
             '../../concepts/Assignable.html'),

            ('http://en.cppreference.com/w/cpp/ranges-algorithm-placeholder/all_any_none_of',  # noqa
             'output/reference/en/cpp/concepts/ConvertibleTo.html',
             '../algorithm/ranges/all_any_none_of.html'),

            ('http://en.cppreference.com/w/cpp/ranges-algorithm-placeholder/all_any_none_of',  # noqa
             'output/reference/en/cpp/algorithm/ConvertibleTo.html',
             'ranges/all_any_none_of.html'),

            ('http://en.cppreference.com/w/cpp/ranges-placeholder/concepts/Assignable',  # noqa
             'output/reference/en/cpp/experimental/ranges/concepts/View.html',
             'Assignable.html'),

            ('http://en.cppreference.com/w/cpp/ranges-placeholder/concepts/Assignable',  # noqa
             'output/reference/en/cpp/experimental/ranges/View.html',
             'concepts/Assignable.html'),

            ('http://en.cppreference.com/w/cpp/ranges-placeholder/concepts/Assignable',  # noqa
             'output/reference/en/cpp/experimental/ranges/range/View.html',
             '../concepts/Assignable.html'),

            ('http://en.cppreference.com/w/cpp/ranges-algorithm-placeholder/all_any_none_of',  # noqa
             'output/reference/en/cpp/experimental/ranges/View.html',
             'algorithm/all_any_none_of.html'),

            ('http://en.cppreference.com/w/cpp/ranges-algorithm-placeholder/all_any_none_of',  # noqa
             'output/reference/en/cpp/experimental/ranges/range/View.html',
             '../algorithm/all_any_none_of.html'),
        ]

        def msg(target, file, root):
            return "target='{}', file='{}', root='{}'".format(
                    target, file, root)

        # transform_ranges_placeholder(target, file, root)
        #  target: the placeholder link
        #  file:   path of the file that contains the link
        #  root:   path to the site root (where '/' should link to)
        root = "output/reference"
        for target, file, expected in entries:
            res = transform_ranges_placeholder(target, file, root)
            self.assertEqual(expected, res,
                             msg=msg(target, file, root))

            target = target.replace('http://', 'https://')
            res = transform_ranges_placeholder(target, file, root)
            self.assertEqual(expected, res,
                             msg=msg(target, file, root))


class TestPreprocessHtml(unittest.TestCase):
    def setUp(self):
        self.testdata = os.path.join(os.path.dirname(__file__),
                                     'preprocess_data')
        infile = os.path.join(self.testdata, "fabs.html")
        self.parser = etree.HTMLParser(encoding='utf-8')
        self.html = etree.parse(infile, self.parser)

    # Check whether the HTML matches the contents of the specified test data
    # file
    def check_output(self, expected_file):
        with open(os.path.join(self.testdata, expected_file), 'rb') as f:
            expected = f.read()
        with io.BytesIO() as buf:
            self.html.write(buf, encoding='utf-8', method='html')
            actual = buf.getvalue()

        self.assertEqual(expected, actual)

    def test_remove_noprint(self):
        remove_noprint(self.html)
        self.check_output("fabs_noprint.html")

    def test_remove_see_also(self):
        remove_see_also(self.html)
        self.check_output("fabs_seealso.html")

    def test_remove_google_analytics(self):
        remove_google_analytics(self.html)
        self.check_output("fabs_ga.html")

    def test_remove_ads(self):
        remove_ads(self.html)
        self.check_output("fabs_ads.html")

    def test_remove_fileinfo(self):
        remove_fileinfo(self.html)
        self.check_output("fabs_fileinfo.html")

    def test_remove_unused_external(self):
        remove_unused_external(self.html)
        self.check_output("fabs_external.html")


class TestFileRename(unittest.TestCase):
    def make_rename_map(self, root):
        def p(*dirs):
            return os.path.join(root, 'dir1', *dirs)
        return {
            'invalid*.txt': 'invalid_star_.txt',
            'confl"ict".html': 'confl_q_ict_q_.html',
            'Confl"ict".html': 'Confl_q_ict_q_.html',
            'load.php?modules=site&only=scripts': 'site_scripts.js',
            'load.php?modules=someext&only=styles': 'ext.css',
            p('sub2', 'Conflict.html'): 'Conflict.2.html',
            p('sub3', 'Confl_q_ict_q_.html'): 'Confl_q_ict_q_.2.html',
            p('sub4', 'Conflict'): 'Conflict.2',
            p('sub4', 'conFlict'): 'conFlict.3',
            p('sub5', 'Conflict'): 'Conflict.2'
        }

    def make_walk_result(self, root):
        def p(*dirs):
            return os.path.join(root, 'dir1', *dirs)

        return [
            # Nothing to do
            (p(),
             ('sub1', 'sub2', 'sub3', 'sub4', 'sub5', 'sub6'),
             ('f1', 'f2')),

            # Unwanted characters
            (p('sub1'),
             (),
             ('invalid*.txt', 'valid.txt')),

            # Case conflict
            (p('sub2'),
             (),
             ('conflict.html', 'Conflict.html')),

            # Unwanted characters + case conflict
            (p('sub3'),
             (),
             ('confl"ict".html', 'Confl"ict".html')),

            # Multiple case conflicts, no extension
            (p('sub4'),
             (),
             ('conflict', 'Conflict', 'conFlict')),

            # Case conflict in second directory
            (p('sub5'),
             (),
             ('conflict', 'Conflict')),

            # Loader links
            (p('sub6'),
             (),
             ('load.php?modules=site&only=scripts',
              'load.php?modules=someext&only=styles'))
        ]

    def test_build_rename_map(self):
        with unittest.mock.patch('os.walk') as walk:
            walk.return_value = self.make_walk_result('output')

            actual = build_rename_map('output')

        expected = self.make_rename_map('output')
        self.assertEqual(expected, actual)

    def test_rename_files(self):
        expected = [
            (('output/dir1/sub1/invalid*.txt',
              'output/dir1/sub1/invalid_star_.txt'), {}),
            (('output/dir1/sub2/Conflict.html',
              'output/dir1/sub2/Conflict.2.html'), {}),
            (('output/dir1/sub3/confl"ict".html',
              'output/dir1/sub3/confl_q_ict_q_.html'), {}),
            (('output/dir1/sub3/Confl"ict".html',
              'output/dir1/sub3/Confl_q_ict_q_.2.html'), {}),
            (('output/dir1/sub4/Conflict',
              'output/dir1/sub4/Conflict.2'), {}),
            (('output/dir1/sub4/conFlict',
              'output/dir1/sub4/conFlict.3'), {}),
            (('output/dir1/sub5/Conflict',
              'output/dir1/sub5/Conflict.2'), {}),
            (('output/dir1/sub6/load.php?modules=site&only=scripts',
              'output/dir1/sub6/site_scripts.js'), {}),
            (('output/dir1/sub6/load.php?modules=someext&only=styles',
              'output/dir1/sub6/ext.css'), {})
        ]

        actual = []

        def record_call(*args, **kwargs):
            actual.append((args, kwargs))

        with unittest.mock.patch('os.walk') as walk, \
                unittest.mock.patch('shutil.move') as move:
            walk.return_value = self.make_walk_result('output')
            move.side_effect = record_call

            with nostdout():
                rename_files('output', self.make_rename_map('output'))

        self.assertEqual(expected, actual,
                         msg="Unexpected sequence of calls to shutil.move")

    def test_transform_relative_link(self):
        entries = [
            # (file, target, expected)
            ('output/dir1/sub2/conflict.html',
             '../f1',
             '../f1'),

            ('output/dir1/sub2/Conflict.html',
             '../f1',
             '../f1'),

            ('output/dir1/sub2/Conflict.html',
             '../f1#p2',
             '../f1#p2'),

            ('output/dir1/sub2/Conflict.html',
             '../f1?some=param',
             '../f1'),

            ('output/dir1/sub2/Conflict.html',
             '../f1?some=param#p2',
             '../f1#p2'),

            ('output/dir1/sub2/Conflict.html',
             '../mwiki/site.css',
             '../common/site.css'),

            ('output/dir1/sub2/Conflict.html',
             '../../upload.cppreference.com/mwiki/site.css',
             '../common/site.css'),

            ('output/dir1/f2',
             'sub1/invalid*.txt',
             'sub1/invalid_star_.txt'),

            ('output/dir1/sub0/other.html',
             '../sub1/invalid*.txt',
             '../sub1/invalid_star_.txt'),

            ('output/dir1/sub1/valid.txt',
             '../sub2/conflict.html',
             '../sub2/conflict.html'),

            ('output/dir1/sub1/valid.txt',
             '../sub2/Conflict.html',
             '../sub2/Conflict.2.html'),

            ('output/dir1/sub1/valid.txt',
             '../sub3/confl"ict".html',
             '../sub3/confl_q_ict_q_.html'),

            ('output/dir1/sub1/valid.txt',
             '../sub3/Confl"ict".html',
             '../sub3/Confl_q_ict_q_.2.html'),

            ('output/dir1/sub1/valid.txt',
             '../sub4/conflict',
             '../sub4/conflict'),

            ('output/dir1/sub1/valid.txt',
             '../sub4/Conflict',
             '../sub4/Conflict.2'),

            ('output/dir1/sub1/valid.txt',
             '../sub4/conFlict',
             '../sub4/conFlict.3'),

            ('output/dir1/sub1/valid.txt',
             '../sub5/conflict',
             '../sub5/conflict'),

            ('output/dir1/sub1/valid.txt',
             '../sub5/Conflict',
             '../sub5/Conflict.2'),
        ]

        # trasform_relative_link(rename_map, target, file)
        #  target: the relative link to transform, if target is in rename map
        #  file:   path of the file that contains the link
        rename_map = self.make_rename_map('output')
        for file, target, expected in entries:
            self.assertEqual(expected,
                             trasform_relative_link(rename_map, target, file),
                             msg="target='{}', file='{}'".format(target, file))
