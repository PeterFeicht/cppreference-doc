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

import os
import tempfile
import unittest

from lxml import etree

from commands.preprocess_qch_html import add_color_classes
from commands.preprocess_qch_html import clamp_rowspans
from commands.preprocess_qch_html import drop_navbar_menus
from commands.preprocess_qch_html import lift_style_blocks
from commands.preprocess_qch_html import link_stylesheet
from commands.preprocess_qch_html import preprocess_html_file
from commands.preprocess_qch_html import referenced_images
from commands.preprocess_qch_html import strip_scripts
from commands.preprocess_qch_html import unstack_vertical_headers

DATA_DIR = os.path.join(os.path.dirname(__file__), 'preprocess_qch_data')


class HTMLTestBase(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def parse(self, body):
        return etree.fromstring(
            '<html><body>{0}</body></html>'.format(body), etree.HTMLParser())

    def assert_converts_html(self, input, expected_output, function):
        root = self.parse(input)
        function(root)

        self.assertEqual(
            '<html><body>{0}</body></html>'.format(expected_output),
            etree.tostring(root, encoding=str, method='xml'))


class TestLiftStyleBlocks(HTMLTestBase):
    def test_takes_the_blocks_out_of_the_page(self):
        root = etree.fromstring(
            '<html><head><style>.a { color: red }</style>'
            '<style>.b { color: blue }</style></head>'
            '<body><p>text</p></body></html>', etree.HTMLParser())

        self.assertEqual(('.a { color: red }', '.b { color: blue }'),
                         lift_style_blocks(root))
        self.assertNotIn(b'<style', etree.tostring(root))

    def test_reports_a_repeated_block_once(self):
        root = self.parse('<style>.a { color: red }</style>'
                          '<style>.a { color: red }</style>')

        self.assertEqual(('.a { color: red }',), lift_style_blocks(root))

    def test_ignores_an_empty_block(self):
        self.assertEqual((), lift_style_blocks(self.parse('<style> </style>')))


class TestStripScripts(HTMLTestBase):
    def test_removes_them(self):
        self.assert_converts_html(
            '<p>a</p><script src="mw.js"></script><script>x()</script>',
            '<p>a</p>', strip_scripts)


class TestDropNavbarMenus(HTMLTestBase):
    def test_removes_them(self):
        self.assert_converts_html(
            '<div class="t-navbar-menu t-nv-begin">C++</div><p>a</p>',
            '<p>a</p>', drop_navbar_menus)

    def test_keeps_the_text_after_one(self):
        # it belongs to the page, as it does for the <style> and <script>
        # blocks stripped beside this
        self.assert_converts_html(
            '<div>before<div class="t-navbar-menu">menu</div>after</div>',
            '<div>beforeafter</div>', drop_navbar_menus)

    def test_keeps_the_text_after_one_that_follows_an_element(self):
        self.assert_converts_html(
            '<div><b>a</b><div class="t-navbar-menu">menu</div>after</div>',
            '<div><b>a</b>after</div>', drop_navbar_menus)


class TestLinkStylesheet(HTMLTestBase):
    def head_of(self, html):
        root = etree.fromstring(html, etree.HTMLParser())
        link_stylesheet(root, '../common/offline-simple.css')
        return etree.tostring(root.find('head'), encoding=str, method='xml')

    def test_replaces_the_links_to_the_site_stylesheets(self):
        self.assertEqual(
            '<head><link rel="stylesheet" type="text/css"'
            ' href="../common/offline-simple.css"/></head>',
            self.head_of('<html><head>'
                         '<link rel="stylesheet" href="../common/ext.css"/>'
                         '<link rel="stylesheet" href="../common/site.css"/>'
                         '</head><body/></html>'))

    def test_leaves_a_link_that_is_not_a_stylesheet(self):
        self.assertIn('shortcut icon',
                      self.head_of('<html><head><link rel="shortcut icon"'
                                   ' href="f.ico"/></head><body/></html>'))


class TestClampRowspans(HTMLTestBase):
    def test_clamps_to_the_row_group(self):
        # the declaration tables ask for a rowspan of 142 to mean "the rest
        # of this group"; litehtml would take it to mean the whole table
        self.assert_converts_html(
            '<table><tbody><tr><td rowspan="142">a</td><td>b</td></tr>'
            '<tr><td>c</td></tr></tbody>'
            '<tbody><tr><td>d</td></tr></tbody></table>',
            '<table><tbody><tr><td rowspan="2">a</td><td>b</td></tr>'
            '<tr><td>c</td></tr></tbody>'
            '<tbody><tr><td>d</td></tr></tbody></table>',
            clamp_rowspans)

    def test_leaves_a_rowspan_that_fits(self):
        self.assert_converts_html(
            '<table><tr><td rowspan="2">a</td></tr><tr><td>b</td></tr>'
            '</table>',
            '<table><tr><td rowspan="2">a</td></tr><tr><td>b</td></tr>'
            '</table>',
            clamp_rowspans)

    def test_ignores_a_rowspan_that_is_not_a_number(self):
        self.assert_converts_html(
            '<table><tr><td rowspan="all">a</td></tr></table>',
            '<table><tr><td rowspan="all">a</td></tr></table>',
            clamp_rowspans)


class TestUnstackVerticalHeaders(HTMLTestBase):
    def test_frees_the_height_the_row_reserved(self):
        self.assert_converts_html(
            '<table><tr style="height:15em"><th>'
            '<div class="t-vertical"><div>GCC</div></div></th></tr></table>',
            '<table><tr><th>'
            '<div class="t-vertical"><div>GCC</div></div></th></tr></table>',
            unstack_vertical_headers)

    def test_keeps_the_rest_of_the_style(self):
        self.assert_converts_html(
            '<table><tr style="height:15em; color: red"><th>'
            '<div class="t-vertical">GCC</div></th></tr></table>',
            '<table><tr style="color: red"><th>'
            '<div class="t-vertical">GCC</div></th></tr></table>',
            unstack_vertical_headers)

    def test_leaves_a_row_without_a_standing_heading(self):
        self.assert_converts_html(
            '<table><tr style="height:15em"><th>GCC</th></tr></table>',
            '<table><tr style="height:15em"><th>GCC</th></tr></table>',
            unstack_vertical_headers)


class TestAddColorClasses(HTMLTestBase):
    def classes_of(self, body):
        root = self.parse(body)
        used = add_color_classes(root)
        return used, etree.tostring(root, encoding=str, method='xml')

    def test_names_the_color_of_an_inline_declaration(self):
        used, html = self.classes_of(
            '<td style="background: #90ff90; color: black">yes</td>')

        self.assertEqual({'bg-90ff90', 'c-000000'}, used)
        self.assertIn('class="bg-90ff90 c-000000"', html)

    def test_keeps_the_classes_the_element_already_had(self):
        _, html = self.classes_of(
            '<td class="t-dsc" style="color: #505050">x</td>')

        self.assertIn('class="t-dsc c-505050"', html)

    def test_passes_over_a_declaration_without_a_color(self):
        used, html = self.classes_of('<p style="font-size: 0.9em">x</p>')

        self.assertEqual(set(), used)
        self.assertNotIn('class=', html)


class TestReferencedImages(unittest.TestCase):
    def images_of(self, body):
        root = etree.fromstring('<html><body>{0}</body></html>'.format(body),
                                etree.HTMLParser())
        return referenced_images(root, os.path.join('out', 'en', 'cpp',
                                                    'page.html'))

    def test_resolves_against_the_page(self):
        self.assertEqual(
            {os.path.join('out', 'common', 'images', 'a.svg')},
            self.images_of('<img src="../../common/images/a.svg"/>'))

    def test_drops_a_cache_busting_query(self):
        self.assertEqual(
            {os.path.join('out', 'en', 'cpp', 'a.png')},
            self.images_of('<img src="a.png?2013-09-04"/>'))

    def test_passes_over_an_image_from_elsewhere(self):
        self.assertEqual(
            set(), self.images_of('<img src="https://example.org/a.png"/>'))


class TestPreprocessHtmlFile(unittest.TestCase):
    def assert_matches_expected(self, name):
        expected_path = os.path.join(DATA_DIR, name + '_expected.html')

        with tempfile.TemporaryDirectory() as directory:
            dst_path = os.path.join(directory, name + '.html')
            preprocess_html_file(os.path.join(DATA_DIR, name + '.html'),
                                 dst_path, 'common/offline-simple.css')

            with open(dst_path, 'r') as a_file:
                output = a_file.read()

        with open(expected_path, 'r') as a_file:
            self.assertEqual(a_file.read(), output)

    def test_multiset(self):
        self.assert_matches_expected('multiset')

    def test_basic_string(self):
        self.assert_matches_expected('basic_string')

    def run_on(self, text):
        with tempfile.TemporaryDirectory() as directory:
            src_path = os.path.join(directory, 'page.html')
            dst_path = os.path.join(directory, 'out', 'page.html')

            with open(src_path, 'w', encoding='utf-8') as a_file:
                a_file.write(text)

            result = preprocess_html_file(src_path, dst_path,
                                          'common/offline-simple.css')

            with open(dst_path, 'r', encoding='utf-8') as a_file:
                return result, a_file.read()

    def test_reads_the_page_as_utf_8(self):
        # whatever locale the build runs under
        _, output = self.run_on('<html><body><p>— naïve</p>'
                                '</body></html>')
        self.assertIn('— naïve', output)

    def test_carries_a_page_with_no_content_through(self):
        # the parser hands back no element at all -- rather than raising --
        # for one of these, and a page that came down truncated should not
        # take the whole run with it
        result, output = self.run_on('<!DOCTYPE html>')
        self.assertEqual((set(), (), set()), result)
        self.assertEqual('<!DOCTYPE html>', output)
