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

import os
import unittest

from lxml import etree

from commands.preprocess_cssless import apply_font_size
from commands.preprocess_cssless import convert_font_size_property_to_pt
from commands.preprocess_cssless import convert_inline_block_elements_to_table
from commands.preprocess_cssless import convert_span_tables_to_tr_td
from commands.preprocess_cssless import \
    convert_table_border_top_to_tr_background
from commands.preprocess_cssless import convert_zero_td_width_to_nonzero
from commands.preprocess_cssless import preprocess_html_merge_cssless
from commands.preprocess_cssless import silence_cssutils_warnings


class TestPreprocessHtmlMergeCss(unittest.TestCase):
    def test_preprocess_html_merge_cssless(self):
        dir_path = os.path.dirname(__file__)
        src_path = os.path.join(
            dir_path, 'preprocess_cssless_data/multiset.html')
        dst_path = os.path.join(
            dir_path, 'preprocess_cssless_data/multiset_out.html')
        expected_path = os.path.join(
            dir_path, 'preprocess_cssless_data/multiset_expected.html')

        preprocess_html_merge_cssless(src_path, dst_path)

        with open(dst_path, 'r', encoding='utf-8') as a_file:
            test = a_file.read()

        with open(expected_path, 'r', encoding='utf-8') as a_file:
            expected = a_file.read()

        self.assertEqual(test, expected)
        os.remove(dst_path)

    def test_preprocess_html_merge_cssless2(self):
        dir_path = os.path.dirname(__file__)
        src_path = os.path.join(
            dir_path, 'preprocess_cssless_data/basic_string.html')
        dst_path = os.path.join(
            dir_path, 'preprocess_cssless_data/basic_string_out.html')
        expected_path = os.path.join(
            dir_path, 'preprocess_cssless_data/basic_string_expected.html')

        preprocess_html_merge_cssless(src_path, dst_path)

        with open(dst_path, 'r', encoding='utf-8') as a_file:
            test = a_file.read()

        with open(expected_path, 'r', encoding='utf-8') as a_file:
            expected = a_file.read()

        self.assertEqual(test, expected)
        os.remove(dst_path)


class HTMLTestBase(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        silence_cssutils_warnings()

    def assert_converts_html(self, input, expected_output, function):
        input = '<html><body>{0}</body></html>'.format(input)
        expected_output = \
            '<html><body>{0}</body></html>'.format(expected_output)

        parser = etree.HTMLParser(encoding='utf-8')
        root = etree.fromstring(input, parser)

        root = function(root)

        output = etree.tostring(root, encoding=str, method='xml')

        self.assertEqual(expected_output, output)


class TestConvertSpanTablesToTrTd(HTMLTestBase):
    def assert_processes_table(self, input, expected_output):
        def test_fun(root):
            convert_span_tables_to_tr_td(root)
            return root

        self.assert_converts_html(input, expected_output, test_fun)

    def test_normal_table(self):
        input = '''\
<div>
  <one_more_block>
    <span style="border:solid 1.5px red; display:table; padding:2px">
      <span style="display:table-row;">
        <span style="border:solid 1px green; display:table-cell; padding:1.5px">1</span>
        <span style="border:none; display:table-cell; padding:1.5px">2</span>
      </span>
    </span>
  </one_more_block>
</div>
'''  # noqa

        expected = '''\
<div>
  <one_more_block>
    <table style="border: solid 1.5px red;padding: 2px">
      <tr>
        <td style="border: solid 1px green;padding: 1.5px">1</td>
        <td style="border: none;padding: 1.5px">2</td>
      </tr>
    </table>
  </one_more_block>
</div>
'''
        self.assert_processes_table(input, expected)

    def test_wraps_table_row_text(self):
        input = '''\
<div>
  <one_more_block>
    <span style="border:solid 1.5px red; display:table; padding:2px">
      <span style="display:table-row;">little text</span>
    </span>
  </one_more_block>
</div>
'''
        expected = '''\
<div>
  <one_more_block>
    <table style="border: solid 1.5px red;padding: 2px">
      <tr><td>little text</td></tr>
    </table>
  </one_more_block>
</div>
'''
        self.assert_processes_table(input, expected)

    def test_wraps_into_td_table_row_children(self):
        input = '''\
<div>
  <one_more_block>
    <span style="border:solid 1.5px red; display:table; padding:2px">
      <span style="display:table-row;">
        <span>blabla</span>
        <span>blabla2</span>
      </span>
    </span>
  </one_more_block>
</div>
'''
        expected = '''\
<div>
  <one_more_block>
    <table style="border: solid 1.5px red;padding: 2px">
      <tr><td>
        <span>blabla</span>
        <span>blabla2</span>
      </td></tr>
    </table>
  </one_more_block>
</div>
'''
        self.assert_processes_table(input, expected)

    def test_wraps_into_td_table_row_children_with_style(self):
        input = '''\
<div>
  <one_more_block>
    <span style="border:solid 1.5px red; display:table; padding:2px">
      <span style="display:table-row">
        <span style="color:#008000; font-size:0.8em">(C++11)</span>
      </span>
    </span>
  </one_more_block>
</div>
'''
        expected = '''\
<div>
  <one_more_block>
    <table style="border: solid 1.5px red;padding: 2px">
      <tr><td>
        <span style="color:#008000; font-size:0.8em">(C++11)</span>
      </td></tr>
    </table>
  </one_more_block>
</div>
'''
        self.assert_processes_table(input, expected)

    def test_wraps_into_td_table_row_children_with_tags(self):
        input = '''\
<div>
  <one_more_block>
    <span style="border:solid 1.5px red; display:table; padding:2px">
      <span style="display:table-row;">
        <span>
          <div>bla</div>
        </span>
        <span>blabla2</span>
      </span>
    </span>
  </one_more_block>
</div>
'''
        expected = '''\
<div>
  <one_more_block>
    <table style="border: solid 1.5px red;padding: 2px">
      <tr><td>
        <span>
          <div>bla</div>
        </span>
        <span>blabla2</span>
      </td></tr>
    </table>
  </one_more_block>
</div>
'''
        self.assert_processes_table(input, expected)

    def test_does_not_wrap_into_td_children_when_not_in_table_row(self):
        input = '''\
<div>
  <one_more_block>
    <span style="border:solid 1.5px red; display:table; padding:2px">
      <span>
        <span style="display:table-cell;">2</span>
      </span>
    </span>
  </one_more_block>
</div>
'''
        expected = '''\
<div>
  <one_more_block>
    <table style="border: solid 1.5px red;padding: 2px">
      <span>
        <span style="display:table-cell;">2</span>
      </span>
    </table>
  </one_more_block>
</div>
'''
        self.assert_processes_table(input, expected)

    def test_does_not_wrap_children_when_sibling_is_td(self):
        input = '''\
<div>
  <one_more_block>
    <span style="border:solid 1.5px red; display:table; padding:2px">
      <span style="display:table-row;">
        <span>1</span>
        <span style="display:table-cell;">2</span>
      </span>
    </span>
  </one_more_block>
</div>
'''
        expected = '''\
<div>
  <one_more_block>
    <table style="border: solid 1.5px red;padding: 2px">
      <tr>
        <span>1</span>
        <td>2</td>
      </tr>
    </table>
  </one_more_block>
</div>
'''
        self.assert_processes_table(input, expected)

    def test_does_not_convert_tr_when_parent_is_not_table(self):
        input = '''\
<div>
  <one_more_block>
    <span style="border:solid 1.5px red; display:table; padding:2px">
      <span style="display:table-row;">
        <span style="display:table-row;">
          blabla
        </span>
      </span>
    </span>
  </one_more_block>
</div>
'''
        expected = '''\
<div>
  <one_more_block>
    <table style="border: solid 1.5px red;padding: 2px">
      <tr>
        <span style="display:table-row;">
          blabla
        </span>
      </tr>
    </table>
  </one_more_block>
</div>
'''
        self.assert_processes_table(input, expected)

    def test_does_not_convert_td_when_parent_is_not_tr(self):
        input = '''\
<div>
  <one_more_block>
    <span style="border:solid 1.5px red; display:table; padding:2px">
      <span style="display:table-cell;">
        <span style="display:table-cell;">
          blabla
        </span>
      </span>
    </span>
  </one_more_block>
</div>
'''
        expected = '''\
<div>
  <one_more_block>
    <table style="border: solid 1.5px red;padding: 2px">
      <span style="display:table-cell;">
        <span style="display:table-cell;">
          blabla
        </span>
      </span>
    </table>
  </one_more_block>
</div>
'''
        self.assert_processes_table(input, expected)


class TestConvertInlineBlockElementsToTable(HTMLTestBase):
    def perform_test(self, input, expected_output):
        def test_fun(root):
            convert_inline_block_elements_to_table(root)
            return root

        self.assert_converts_html(input, expected_output, test_fun)

    def test_does_not_convert_single(self):
        input = '''\
<div>
  <div style="display:inline-block; padding:0"/>
</div>
'''
        self.perform_test(input, input)

    def test_converts_multiple(self):
        input = '''\
<div>
  <div style="display:inline-block;"/>
  <div style="display:inline-table;"/>
</div>
'''
        expected = '''\
<div>
  <table style="padding:0; margin:0; border:none;"><tr><td><div style="display:inline-block;"/>
  </td><td><div style="display:inline-table;"/>
</td></tr></table></div>
'''  # noqa
        self.perform_test(input, expected)


class TestConvertZeroTdWidthToNonzero(HTMLTestBase):
    def test_css_property(self):
        def test_fun(root):
            convert_zero_td_width_to_nonzero(root)
            return root

        input = '''\
<tr>
  <td style="white-space:nowrap; width:0%; border-top:1px solid #CCC">
  </td>
</tr>
'''
        expected = '''\
<tr>
  <td style="white-space: nowrap;border-top: 1px solid #CCC" width="1px">
  </td>
</tr>
'''
        self.assert_converts_html(input, expected, test_fun)

    def test_attribute(self):
        def test_fun(root):
            convert_zero_td_width_to_nonzero(root)
            return root

        input = '''\
<tr>
  <td width="0%">
  </td>
</tr>
'''
        expected = '''\
<tr>
  <td width="1px">
  </td>
</tr>
'''
        self.assert_converts_html(input, expected, test_fun)


class TestApplyFontSize(unittest.TestCase):
    def test_em(self):
        self.assertEqual(10, apply_font_size('1em', 10))
        self.assertEqual(8, apply_font_size('0.8em', 10))
        self.assertEqual(10, apply_font_size('1.0em', 10))
        self.assertEqual(15, apply_font_size('1.5em', 10))

        self.assertEqual(15, apply_font_size('1.5 em', 10))
        self.assertEqual(15, apply_font_size(' 1.5em ', 10))
        self.assertEqual(15, apply_font_size('1.5em ', 10))

    def test_px(self):
        self.assertEqual(8, apply_font_size('8px', 10))
        self.assertEqual(10, apply_font_size('10px', 10))
        self.assertEqual(15, apply_font_size('15px', 10))

        self.assertEqual(15, apply_font_size('15 px', 10))
        self.assertEqual(15, apply_font_size(' 15px ', 10))
        self.assertEqual(15, apply_font_size('15px ', 10))

    def test_ptc(self):
        self.assertEqual(8, apply_font_size('80%', 10))
        self.assertEqual(10, apply_font_size('100%', 10))
        self.assertEqual(15, apply_font_size('150%', 10))

        self.assertEqual(15, apply_font_size('150 %', 10))
        self.assertEqual(15, apply_font_size(' 150% ', 10))
        self.assertEqual(15, apply_font_size('150% ', 10))


class TestConvertFontSizePropertyToPt(HTMLTestBase):
    def test_simple(self):
        def test_fun(root):
            convert_font_size_property_to_pt(root, 10)
            return root

        input = '''\
<div style="font-size: 1em">
text
</div>
'''
        expected = '''\
<div style="font-size: 10pt">
text
</div>
'''
        self.assert_converts_html(input, expected, test_fun)

    def test_font_size_value_is_unsupported(self):
        def test_fun(root):
            convert_font_size_property_to_pt(root, 10)
            return root

        input = '''\
<div style="font-size: 1.5em">
  <div style="font-size: abcd">
    text
  </div>
</div>'''
        expected = '''\
<div style="font-size: 15pt">
  <div style="font-size: 15pt">
    text
  </div>
</div>'''
        self.assert_converts_html(input, expected, test_fun)

    def test_simple_px(self):
        def test_fun(root):
            convert_font_size_property_to_pt(root, 10)
            return root

        input = '''\
<div style="font-size: 1px">
text
</div>
'''
        expected = '''\
<div style="font-size: 1pt">
text
</div>
'''
        self.assert_converts_html(input, expected, test_fun)

    def test_simple_pt(self):
        def test_fun(root):
            convert_font_size_property_to_pt(root, 10)
            return root

        input = '''\
<div style="font-size: 1pt">
text
</div>
'''
        expected = '''\
<div style="font-size: 1pt">
text
</div>
'''
        self.assert_converts_html(input, expected, test_fun)

    def test_inherits(self):
        def test_fun(root):
            convert_font_size_property_to_pt(root, 10)
            return root

        input = '''\
<div style="font-size: 1.5em">
  <div style="font-size: 1.5em">
    text
  </div>
</div>'''
        expected = '''\
<div style="font-size: 15pt">
  <div style="font-size: 22.5pt">
    text
  </div>
</div>'''
        self.assert_converts_html(input, expected, test_fun)

    def test_inherits_1em(self):
        def test_fun(root):
            convert_font_size_property_to_pt(root, 10)
            return root

        input = '''\
<div style="font-size: 1.5em">
  <div style="font-size: 1.5em">
    text
    <div style="font-size: 1em">
      text
    </div>
  </div>
</div>'''
        expected = '''\
<div style="font-size: 15pt">
  <div style="font-size: 22.5pt">
    text
    <div style="font-size: 22.5pt">
      text
    </div>
  </div>
</div>'''
        self.assert_converts_html(input, expected, test_fun)


class TestConvertTableBorderTopToTrBackground(HTMLTestBase):
    def test_no_border(self):
        def test_fun(root):
            convert_table_border_top_to_tr_background(root)
            return root

        input = '''\
<table>
  <tr>
    <td/>
  </tr>
</table>
'''
        self.assert_converts_html(input, input, test_fun)

    def test_single_td(self):
        def test_fun(root):
            convert_table_border_top_to_tr_background(root)
            return root

        input = '''\
<table>
  <tr>
    <td style="border-top: 1px solid #ccc"/>
  </tr>
</table>
'''
        expected = '''\
<table>
  <tr><td colspan="1" style="height:1px; font-size:1px; background-color: #ccc;"/></tr><tr>
    <td/>
  </tr>
</table>
'''  # noqa
        self.assert_converts_html(input, expected, test_fun)

    def test_multiple_td(self):
        def test_fun(root):
            convert_table_border_top_to_tr_background(root)
            return root

        input = '''\
<table>
 <tr>
   <td style="border-top: 1px solid #ccc"/>
   <td/>
   <td/>
 </tr>
</table>
'''
        expected = '''\
<table>
 <tr><td colspan="3" style="height:1px; font-size:1px; background-color: #ccc;"/></tr><tr>
   <td/>
   <td/>
   <td/>
 </tr>
</table>
'''  # noqa
        self.assert_converts_html(input, expected, test_fun)

    def test_subtable_does_not_affect_parent_table(self):
        def test_fun(root):
            convert_table_border_top_to_tr_background(root)
            return root

        input = '''\
<table>
  <tr>
    <td>
      <table>
        <tr>
          <td style="border-top: 1px solid #ccc"/>
        </tr>
      </table>
    </td>
  </tr>
</table>
'''
        expected = '''\
<table>
  <tr>
    <td>
      <table>
        <tr><td colspan="1" style="height:1px; font-size:1px; background-color: #ccc;"/></tr><tr>
          <td/>
        </tr>
      </table>
    </td>
  </tr>
</table>
'''  # noqa
        self.assert_converts_html(input, expected, test_fun)
