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
import unittest

from commands.qch_css import DARK_BASE_CSS
from commands.qch_css import DARK_LINK
from commands.qch_css import DARK_PAGE_BACKGROUND
from commands.qch_css import DARK_PAGE_TEXT
from commands.qch_css import DARK_TEXT_MIN_CONTRAST
from commands.qch_css import FONT_SIZE_COMPRESSION
from commands.qch_css import build_stylesheets
from commands.qch_css import class_for_declaration
from commands.qch_css import clean_inline_style
from commands.qch_css import clean_site_css
from commands.qch_css import color_from_key
from commands.qch_css import color_key
from commands.qch_css import compress_font_sizes
from commands.qch_css import contrast_ratio
from commands.qch_css import dark_class_rules
from commands.qch_css import dark_color
from commands.qch_css import dark_stylesheet_rules
from commands.qch_css import format_color
from commands.qch_css import hex_to_rgb
from commands.qch_css import font_selectors
from commands.qch_css import monospace_size_rules
from commands.qch_css import parse_color
from commands.qch_css import read_asset
from commands.qch_css import referenced_images
from commands.qch_css import simplify_font_families
from commands.qch_css import stylesheet_href


class TestParseColor(unittest.TestCase):
    def test_hex(self):
        self.assertEqual((204, 204, 204, 1.0), parse_color('#ccc'))
        self.assertEqual((214, 214, 214, 1.0), parse_color('#D6D6D6'))

    def test_named(self):
        self.assertEqual((255, 255, 255, 1.0), parse_color('white'))
        self.assertEqual((192, 192, 192, 1.0), parse_color('silver'))

    def test_functional(self):
        self.assertEqual((0, 0, 0, 0.031),
                         parse_color('rgba(0, 0, 0, 0.031)'))
        self.assertEqual((1, 2, 3, 1.0), parse_color('rgb(1, 2, 3)'))

    def test_skips_non_color_tokens_of_a_shorthand(self):
        self.assertEqual((214, 214, 214, 1.0),
                         parse_color('1px solid #D6D6D6'))
        self.assertEqual((192, 192, 192, 1.0),
                         parse_color('1px solid silver'))

    def test_skips_a_url_holding_a_word_that_is_also_a_color(self):
        self.assertIsNone(parse_color('url(images/tan-tab.png) no-repeat'))
        self.assertEqual((255, 255, 255, 1.0),
                         parse_color('#fff url(images/red.png)'))

    def test_no_color(self):
        self.assertIsNone(parse_color('none'))
        self.assertIsNone(parse_color('inherit'))
        self.assertIsNone(parse_color('1px solid'))
        self.assertIsNone(parse_color('0'))


class TestColorKey(unittest.TestCase):
    def test_opaque(self):
        self.assertEqual('008000', color_key((0, 128, 0, 1.0)))
        self.assertEqual((0, 128, 0, 1.0), color_from_key('008000'))

    def test_translucent(self):
        self.assertEqual('000000-031', color_key((0, 0, 0, 0.031)))
        self.assertEqual((0, 0, 0, 0.031), color_from_key('000000-031'))

    def test_format(self):
        self.assertEqual('#008000', format_color((0, 128, 0, 1.0)))
        self.assertEqual('rgba(0, 0, 0, 0.031)',
                         format_color((0, 0, 0, 0.031)))


class TestClassForDeclaration(unittest.TestCase):
    def test_color(self):
        self.assertEqual('c-008000',
                         class_for_declaration('color', '#008000'))

    def test_background(self):
        self.assertEqual('bg-ffffff',
                         class_for_declaration('background-color', 'white'))

    def test_border_shorthand(self):
        self.assertEqual('bd-d6d6d6',
                         class_for_declaration('border', '1px solid #D6D6D6'))
        self.assertEqual(
            'bdb-c0c0c0',
            class_for_declaration('border-bottom', '1px solid silver'))

    def test_property_without_a_color(self):
        self.assertIsNone(class_for_declaration('font-size', '16pt'))
        self.assertIsNone(
            class_for_declaration('background-image', 'url(tab.png)'))

    def test_value_without_a_color(self):
        self.assertIsNone(class_for_declaration('border', 'none'))
        self.assertIsNone(
            class_for_declaration('background-color', 'transparent'))

    def test_value_settling_more_than_one_color(self):
        # a class names one color and the rule sets the whole property to it,
        # so there is no saying this with one
        self.assertIsNone(class_for_declaration(
            'border-color', 'transparent transparent silver transparent'))
        self.assertIsNone(class_for_declaration(
            'background', 'linear-gradient(#ffffff, #eeeeee)'))

    def test_keyword_sub_property_of_a_shorthand(self):
        # the `none` is the background image, not a side with no color on it
        self.assertEqual('bg-f0f0f0', class_for_declaration(
            'background', 'none repeat scroll 0 0 #f0f0f0'))


class TestDarkColor(unittest.TestCase):
    def test_lightens_dark_text(self):
        self.assertEqual((148, 230, 148, 1.0),
                         dark_color('text', (0, 128, 0, 1.0)))

    def test_keeps_text_that_already_suits_a_dark_page(self):
        self.assertIsNone(dark_color('text', (255, 255, 255, 1.0)))

    def test_darkens_light_surfaces(self):
        self.assertEqual((38, 38, 38, 1.0),
                         dark_color('surface', (255, 255, 255, 1.0)))

    def test_keeps_the_spread_between_surfaces(self):
        # the bands of a table have to stay apart from the page background
        self.assertEqual((66, 66, 66, 1.0),
                         dark_color('surface', (204, 204, 204, 1.0)))

    def test_resolves_a_translucent_color_against_the_light_page(self):
        self.assertEqual((42, 42, 42, 1.0),
                         dark_color('surface', (0, 0, 0, 0.031)))

    def test_keeps_surfaces_that_are_already_dark(self):
        self.assertIsNone(dark_color('surface', (0, 0, 64, 1.0)))

    def test_a_pale_tint_stays_near_grey(self):
        # HSL calls #f3f3fc two thirds saturated, but it is almost white
        self.assertEqual((38, 38, 47, 1.0),
                         dark_color('surface', (243, 243, 252, 1.0)))

    def test_takes_down_a_surface_the_body_text_would_not_read_over(self):
        # the orange of a highlight band lands too light on reach alone
        self.assertEqual((110, 85, 34, 1.0),
                         dark_color('surface', (224, 160, 32, 1.0)))

    def test_dark_surfaces_carry_the_body_text(self):
        text = hex_to_rgb(DARK_PAGE_TEXT)
        for light in [(255, 255, 255, 1.0), (204, 204, 204, 1.0),
                      (224, 160, 32, 1.0), (255, 255, 144, 1.0),
                      (144, 255, 144, 1.0), (255, 144, 144, 1.0),
                      (188, 188, 255, 1.0), (227, 249, 223, 1.0)]:
            dark = dark_color('surface', light)
            self.assertGreaterEqual(
                contrast_ratio(text, dark[:3]), DARK_TEXT_MIN_CONTRAST,
                'light color {0}'.format(light))

    def test_lines_sit_above_the_surfaces(self):
        self.assertEqual((71, 71, 71, 1.0),
                         dark_color('line', (214, 214, 214, 1.0)))

    def test_lifts_a_blue_past_what_lightening_alone_reaches(self):
        # the keywords of the code samples; HSL calls #6b6bdc as light, but
        # blue carries too little luminance for it to read
        self.assertEqual((132, 132, 226, 1.0),
                         dark_color('text', (0, 0, 221, 1.0)))

    def test_dark_text_clears_wcag_aa(self):
        background = hex_to_rgb(DARK_PAGE_BACKGROUND)
        for light in [(0, 0, 0, 1.0), (128, 128, 128, 1.0),
                      (0, 0, 221, 1.0), (0, 0, 255, 1.0), (0, 0, 64, 1.0),
                      (0, 128, 0, 1.0), (0, 128, 128, 1.0),
                      (0, 48, 128, 1.0)]:
            dark = dark_color('text', light)
            self.assertGreaterEqual(
                contrast_ratio(dark[:3], background), DARK_TEXT_MIN_CONTRAST,
                'light color {0}'.format(light))


class TestDarkStylesheetRules(unittest.TestCase):
    def test_restates_the_selector_with_the_dark_color(self):
        self.assertIn('.t-dsc { color: #94e694 }',
                      dark_stylesheet_rules('.t-dsc { color: #008000 }'))

    def test_picks_the_color_out_of_a_shorthand(self):
        # the rest of the shorthand is left to the rule it came from
        self.assertIn(
            'td { border-color: #474747 }',
            dark_stylesheet_rules('td { border: 1px solid #d6d6d6 }'))

    def test_keeps_the_shape_of_a_value_holding_a_color_per_side(self):
        # `border-color` takes one per side, and the triangle a dropdown
        # arrow is drawn as has three of them transparent; restating the one
        # color on its own would paint all four sides and make it a square
        self.assertIn(
            '.a { border-color: transparent transparent #585858 transparent }',
            dark_stylesheet_rules(
                '.a { border-color: transparent transparent silver'
                ' transparent }'))

    def test_leaves_a_shorthand_settling_more_than_one_color(self):
        # the declaration we write is the longhand, so only a color comes
        # over, and a gradient's first stop is not what the element is
        # painted in
        self.assertEqual('', dark_stylesheet_rules(
            '.a { background: linear-gradient(#ffffff, #eeeeee) }'))

    def test_reads_a_keyword_sub_property_of_a_shorthand_as_one(self):
        # the `none` is the background image, not a side with no color on it
        self.assertIn(
            'div { background-color: #2e2e2e }',
            dark_stylesheet_rules(
                'div { background: none repeat scroll 0 0 #f0f0f0 }'))

    def test_keeps_an_important_declaration_important(self):
        self.assertIn('p { color: #d1d1d1 !important }',
                      dark_stylesheet_rules('p { color: black !important }'))

    def test_passes_over_a_rule_with_no_color(self):
        self.assertEqual('', dark_stylesheet_rules('p { margin: 0 }'))

    def test_keeps_the_rules_in_their_original_order(self):
        # each one restates a selector from above, so it has to stay below
        css = dark_stylesheet_rules('.a { color: #008000 }'
                                    '.b { color: #0000dd }')
        self.assertLess(css.index('.a {'), css.index('.b {'))

    def test_is_written_for_the_screen_only(self):
        # a reader printing from a dark viewer wants the page as it was meant
        # to be, so the site's own print rules are left to it
        self.assertIn('@media screen {',
                      dark_stylesheet_rules('p { color: black }'))

    def test_passes_over_what_the_site_wrote_for_print(self):
        self.assertEqual(
            '', dark_stylesheet_rules('@media print { p { color: black } }'))

    def test_follows_the_last_word_on_a_property(self):
        # everything derived is appended to the end of the dark sheet, where
        # it outranks the whole of the light one, so a counterpart for a
        # declaration that something below it settles would put a color on
        # the dark page that the light page does not have
        self.assertEqual(
            '', dark_stylesheet_rules('code { background-color: #f9f9f9 }'
                                      ' code { background-color: transparent }'
                                      ))

    def test_reads_the_sheets_as_one_cascade(self):
        # the cascade runs through all of them: what one sheet says about a
        # selector is settled by what the next one says about it
        self.assertEqual(
            '', dark_stylesheet_rules('code { background-color: #f9f9f9 }',
                                      'code, table'
                                      ' { background-color: transparent }'))

    def test_an_important_declaration_has_the_last_word(self):
        css = dark_stylesheet_rules('p { color: black !important }'
                                    ' p { color: #008000 }')
        self.assertIn('p { color: #d1d1d1 !important }', css)
        self.assertNotIn('#94e694', css)

    def test_splits_a_rule_whose_selectors_no_longer_agree(self):
        # `code` is settled below; `tt` is not, and keeps its counterpart
        css = dark_stylesheet_rules('tt, code { color: black }'
                                    ' code { color: #008000 }')
        self.assertIn('tt { color: #d1d1d1 }', css)
        self.assertIn('code { color: #94e694 }', css)

    def test_states_no_priority_the_site_made_up(self):
        # cssutils keeps the old `!ie` hack as it found it, and repeating one
        # would only write a declaration every renderer throws away
        self.assertIn('p { color: #d1d1d1 }',
                      dark_stylesheet_rules('p { color: black !ie }'))

    def test_carries_a_rule_over_in_its_own_media(self):
        self.assertIn(
            '@media screen and (max-width: 480px) {',
            dark_stylesheet_rules('@media screen and (max-width: 480px)'
                                  ' { p { color: black } }'))


class TestDarkClassRules(unittest.TestCase):
    def test_overrides_the_inline_color(self):
        css = dark_class_rules(['c-008000', 'bg-ffffff'])
        self.assertIn('.c-008000 { color: #94e694 !important }', css)
        self.assertIn('.bg-ffffff { background-color: #262626 !important }',
                      css)

    def test_omits_a_color_that_needs_no_counterpart(self):
        # leaving the rule out lets the inline declaration stand
        self.assertEqual('', dark_class_rules(['c-ffffff']))

    def test_is_deterministic(self):
        classes = ['c-008000', 'bg-ffffff', 'bd-d6d6d6']
        self.assertEqual(dark_class_rules(classes),
                         dark_class_rules(list(reversed(classes))))


class TestBuildStylesheets(unittest.TestCase):
    def setUp(self):
        self.light, self.dark = build_stylesheets(
            ['.t-dsc { color: #008000 }'], ['.kw1 { color: #0000dd }'],
            ['bg-90ff90'])

    def test_the_light_sheet_is_the_site_stylesheet(self):
        self.assertIn('.t-dsc { color: #008000 }', self.light)
        self.assertIn('.kw1 { color: #0000dd }', self.light)

    def test_the_light_sheet_states_no_dark_color(self):
        self.assertNotIn('#262626', self.light)
        self.assertNotIn('.bg-90ff90', self.light)

    def test_the_dark_sheet_is_the_light_one_and_then_some(self):
        self.assertIn('.t-dsc { color: #008000 }', self.dark)
        self.assertIn('.t-dsc { color: #94e694 }', self.dark)
        self.assertLess(self.dark.index('color: #008000'),
                        self.dark.index('color: #94e694'))

    def test_the_dark_sheet_reaches_the_rules_lifted_out_of_the_pages(self):
        self.assertIn('.kw1 { color: #8484e2 }', self.dark)

    def test_the_dark_sheet_names_the_page_colors(self):
        self.assertIn('background-color: #262626', self.dark)
        self.assertIn('color: #6ab0f3', self.dark)

    def test_the_dark_sheet_overrides_the_colors_carried_inline(self):
        self.assertIn('.bg-90ff90 { background-color:', self.dark)


class TestDarkPageColors(unittest.TestCase):
    # The colors the dark page is built on are stated twice: here, where the
    # mapping measures contrast against them, and in "qch-dark.css", which
    # hands them to the elements that name no color of their own.  Neither
    # can be derived from the other, so check that they still agree.
    def setUp(self):
        self.css = read_asset(DARK_BASE_CSS)

    def test_the_page_background(self):
        self.assertIn(DARK_PAGE_BACKGROUND, self.css)

    def test_the_page_text(self):
        self.assertIn(DARK_PAGE_TEXT, self.css)

    def test_the_link_color(self):
        self.assertIn(DARK_LINK, self.css)


class TestCleanSiteCss(unittest.TestCase):
    def test_drops_an_encoded_cache_busting_query(self):
        self.assertEqual(
            'a { background: url("images/lock.png") }',
            clean_site_css('a { background: url("images/lock.png'
                           '%3F2013-09-04T19:18:20Z") }'))

    def test_leaves_a_plain_url(self):
        css = 'a { background: url(images/lock.png) no-repeat }'
        self.assertEqual(css, clean_site_css(css))


class TestSimplifyFontFamilies(unittest.TestCase):
    # A help viewer resolves the first family of a stack and substitutes its
    # own default when that one is missing, rather than trying the next, so
    # a stack is worth its first *resolvable* name and nothing else.
    def test_cuts_a_stack_down_to_its_first_generic(self):
        self.assertEqual(
            'code { font-family: monospace }',
            simplify_font_families(
                'code { font-family: DejaVuSansMono,'
                ' "DejaVu Sans Mono", courier, monospace }'))

    def test_keeps_a_serif_stack_serif(self):
        self.assertEqual(
            'i { font-family: serif }',
            simplify_font_families("i { font-family: Georgia,"
                                   " 'DejaVu Serif', serif }"))

    def test_a_proportional_stack_asks_to_inherit(self):
        # naming `sans-serif` would hand the reader Arial whatever font they
        # chose for the help pane; `inherit` is their font at the root, and
        # still takes an element back out of a monospace rule further in
        self.assertEqual(
            'body { font-family: inherit }',
            simplify_font_families('body { font-family: DejaVuSans,'
                                   ' "DejaVu Sans", arial, sans-serif }'))

    def test_a_stack_with_nothing_resolvable_asks_to_inherit(self):
        self.assertEqual(
            'p { font-family: inherit }',
            simplify_font_families('p { font-family: "DejaVu Sans" }'))

    def test_keeps_an_important_declaration_important(self):
        self.assertEqual(
            'tt { font-family: monospace !important }',
            simplify_font_families('tt { font-family: "DejaVu Sans Mono",'
                                   ' courier, monospace !important }'))

    def test_keeps_the_rest_of_the_rule(self):
        self.assertEqual(
            'b { font-weight: bold; font-family: monospace; color: red }',
            simplify_font_families('b { font-weight: bold; font-family:'
                                   ' DejaVuSansMono, monospace; color: red }'))

    def test_leaves_font_face_alone(self):
        # there the family is the name of the face being defined
        css = ('@font-face{font-family:"DejaVuSans";'
               'src:local("DejaVu Sans")}')
        self.assertEqual(css, simplify_font_families(css))

    def test_rewrites_around_a_font_face(self):
        self.assertEqual(
            '@font-face{font-family:"X"} p { font-family: monospace }',
            simplify_font_families('@font-face{font-family:"X"}'
                                   ' p { font-family: X, monospace }'))


class TestCompressFontSizes(unittest.TestCase):
    def test_pulls_a_proportion_towards_the_middle(self):
        self.assertEqual('p { font-size: 0.8944em }',
                         compress_font_sizes('p { font-size: 0.8em }'))
        self.assertEqual('h1 { font-size: 1.414em }',
                         compress_font_sizes('h1 { font-size: 2em }'))

    def test_handles_a_percentage(self):
        self.assertEqual('p { font-size: 96.95% }',
                         compress_font_sizes('p { font-size: 94% }'))

    def test_leaves_the_middle_alone(self):
        self.assertEqual('p { font-size: 1em }',
                         compress_font_sizes('p { font-size: 1em }'))

    def test_compressing_each_step_compresses_the_whole_cascade(self):
        # the sizes of a cascade multiply and a root distributes over a
        # product, which is what lets this be done to the stylesheet rather
        # than to every element of every page
        declared = [0.8, 2.0, 0.9]
        compressed = 1.0
        for value in declared:
            css = compress_font_sizes('p { font-size: %gem }' % value)
            compressed *= float(css.split(':')[1].strip().rstrip('em }'))

        product = 0.8 * 2.0 * 0.9
        self.assertAlmostEqual(product ** FONT_SIZE_COMPRESSION, compressed,
                               places=3)

    def test_keeps_an_important_declaration_important(self):
        self.assertEqual(
            'p { font-size: 0.8944em !important }',
            compress_font_sizes('p { font-size: 0.8em !important }'))

    def test_leaves_a_size_stated_outright_alone(self):
        # these are on the MediaWiki furniture, which no offline page shows,
        # and on `html, body`, where a length would be the root itself
        for css in ['p { font-size: 12px }', 'p { font-size: 9pt }',
                    'p { font-size: x-small }', 'p { font-size: larger }']:
            self.assertEqual(css, compress_font_sizes(css))

    def test_keeps_the_rest_of_the_rule(self):
        self.assertEqual(
            'p { color: red; font-size: 0.8944em; margin: 0 }',
            compress_font_sizes('p { color: red; font-size: 0.8em;'
                                ' margin: 0 }'))


class TestCleanInlineStyle(unittest.TestCase):
    # A rule cannot reach into a `style` attribute, so what the passes above
    # do to the stylesheets is done to the attributes as well.

    def test_compresses_a_proportion(self):
        self.assertEqual('font-size: 0.8367em',
                         clean_inline_style('font-size:0.7em'))

    def test_cuts_a_stack_down_to_its_first_generic(self):
        self.assertEqual(
            'font-family: serif; font-style:italic',
            clean_inline_style("font-family: Georgia, 'DejaVu Serif', serif;"
                               ' font-style:italic'))

    def test_keeps_the_rest_of_the_declarations(self):
        self.assertEqual('color:#006600; font-size: 0.8944em; width:5em',
                         clean_inline_style('color:#006600;'
                                            ' font-size:0.8em; width:5em'))

    def test_leaves_a_size_stated_outright_alone(self):
        self.assertEqual('font-size:21px',
                         clean_inline_style('font-size:21px'))


class TestFontSelectors(unittest.TestCase):
    def test_finds_the_rules_that_set_monospace(self):
        self.assertEqual(
            (['tt', 'code'], ['p']),
            font_selectors('tt, code { font-family: courier, monospace }'
                           ' p { font-family: serif }'))

    def test_looks_inside_a_media_rule(self):
        self.assertEqual(
            (['code'], []),
            font_selectors('@media screen { code'
                           ' { font-family: monospace } }'))

    def test_passes_over_what_the_site_wrote_for_print(self):
        self.assertEqual(
            ([], []),
            font_selectors('@media print { code'
                           ' { font-family: monospace } }'))

    def test_reports_a_selector_once(self):
        self.assertEqual(
            (['code'], []),
            font_selectors('code { font-family: monospace }'
                           ' code { font-family: courier, monospace }'))

    def test_reads_the_sheets_as_one_cascade(self):
        self.assertEqual(
            (['code'], ['q']),
            font_selectors('code { font-family: monospace }',
                           'q { font-family: serif }'))

    def test_a_selector_is_judged_by_the_family_it_ends_up_with(self):
        # set in monospace and then taken back out: it is proportional
        self.assertEqual(
            ([], ['code']),
            font_selectors('code { font-family: monospace }'
                           ' code { font-family: inherit }'))

    def test_leaves_out_a_selector_the_site_sizes_itself(self):
        # the correction is about the face, and overriding a size the site
        # asked for outright is not ours to do
        self.assertEqual(
            (['code'], []),
            font_selectors('code { font-family: monospace }'
                           ' body { font-family: serif; font-size: 0.8em }'))


class TestMonospaceSizeRules(unittest.TestCase):
    # The correction belongs to the face, so it is taken where the monospace
    # starts and not again inside it -- and monospace nests on every page.
    def setUp(self):
        self.css = monospace_size_rules(['code', '.mw-geshi'])

    def test_asks_for_less_of_the_monospace_face(self):
        self.assertIn('code,\n.mw-geshi {\n    font-size: 85%;\n}', self.css)

    def test_does_not_take_the_correction_twice(self):
        for nested in ['code code', 'code .mw-geshi', '.mw-geshi code',
                       '.mw-geshi .mw-geshi']:
            self.assertIn(nested, self.css)
        self.assertIn('font-size: 100%;', self.css)

    def test_the_reset_outranks_the_correction(self):
        # a descendant selector is more specific than the one it is built
        # from, so the rules below settle it without an `!important`
        self.assertLess(self.css.index('font-size: 85%'),
                        self.css.index('font-size: 100%'))

    def test_says_nothing_when_nothing_is_monospace(self):
        self.assertEqual('', monospace_size_rules([]))

    def test_leaves_a_proportional_element_the_size_it_inherits(self):
        # the members of the declaration tables are matched by a monospace
        # rule and by a proportional one on the same element, and the one
        # they end up in is the viewer's own face, which needs no correction
        css = monospace_size_rules(['.t-dsc-member-div > div:first-child'],
                                   ['.t-dsc-member-nobold-div'
                                    ' > div:first-child'])
        self.assertLess(
            css.index('.t-dsc-member-div > div:first-child {'),
            css.index('.t-dsc-member-nobold-div > div:first-child'))
        self.assertIn('font-size: 100%;', css)


class TestReferencedImages(unittest.TestCase):
    def test_resolves_against_the_stylesheet(self):
        self.assertEqual(
            {os.path.join('out', 'common', 'skins', 'tab.png')},
            referenced_images(['a { background: url("skins/tab.png") }'],
                              'out'))

    def test_passes_over_what_is_not_an_image(self):
        self.assertEqual(
            set(),
            referenced_images(['@font-face { src: url("../a.ttf") }'], 'out'))


class TestStylesheetHref(unittest.TestCase):
    def test_relative_to_the_page(self):
        css_dir = os.path.join('out', 'common')
        self.assertEqual(
            'common/offline-simple.css',
            stylesheet_href(css_dir, os.path.join('out', 'index.html')))
        self.assertEqual(
            '../../common/offline-simple.css',
            stylesheet_href(css_dir,
                            os.path.join('out', 'cpp', 'string', 'a.html')))
