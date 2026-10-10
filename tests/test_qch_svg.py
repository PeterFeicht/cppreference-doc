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

import unittest

from lxml import etree

from commands.qch_svg import BACKDROP_CLASS
from commands.qch_svg import GRADIENT_SUFFIX
from commands.qch_svg import dark_mark
from commands.qch_svg import fit_for_the_viewer

SVG = ('<svg xmlns="http://www.w3.org/2000/svg"'
       ' xmlns:xlink="http://www.w3.org/1999/xlink"'
       ' width="20" height="10" viewBox="0 0 20 10">%s</svg>')


def scheme(body):
    return fit_for_the_viewer((SVG % body).encode('utf-8')).decode('utf-8')


def parsed(body):
    return etree.fromstring(scheme(body).encode('utf-8'))


def find(root, localname):
    return [el for el in root.iter()
            if isinstance(el.tag, str)
            and etree.QName(el).localname == localname]


class TestDarkMark(unittest.TestCase):
    # A drawing is dark marks on a light ground, so a dark color is lightened
    # the way the page's text is and a light one darkened the way a surface
    # is.

    def test_lightens_the_lettering(self):
        self.assertEqual((209, 209, 209, 1.0), dark_mark((0, 0, 0, 1.0)))

    def test_darkens_the_ground(self):
        self.assertEqual((38, 38, 38, 1.0), dark_mark((255, 255, 255, 1.0)))

    def test_keeps_a_light_ground_apart_from_the_page(self):
        # the highlighted box of an inheritance chart is a light grey, and it
        # has to stay a step off the boxes around it
        self.assertNotEqual(dark_mark((211, 211, 211, 1.0)),
                            dark_mark((255, 255, 255, 1.0)))


class TestPresentationAttributes(unittest.TestCase):
    def test_names_the_color_by_a_class(self):
        root = parsed('<polygon fill="white" stroke="black"/>')
        self.assertEqual('f-ffffff s-000000',
                         find(root, 'polygon')[0].get('class'))

    def test_leaves_the_attribute_where_it_is(self):
        # a rule already outranks a presentation attribute, and leaving it is
        # what a renderer that reads no CSS at all goes on drawing
        polygon = find(parsed('<polygon fill="white"/>'), 'polygon')[0]
        self.assertEqual('white', polygon.get('fill'))

    def test_states_the_color_light_and_dark(self):
        css = scheme('<polygon fill="white"/>')
        self.assertIn('.f-ffffff { fill: #ffffff }', css)
        self.assertIn('svg.dark .f-ffffff { fill: #262626 }', css)

    def test_passes_over_what_names_no_color(self):
        root = parsed('<path fill="none" stroke="none"/>')
        self.assertIsNone(find(root, 'path')[0].get('class'))


class TestStyleAttribute(unittest.TestCase):
    def test_moves_the_color_out_of_the_style(self):
        # a declaration there outranks every rule, and the whole point is to
        # be outrankable
        path = find(parsed('<path style="fill:#000000;stroke-width:2"/>'),
                    'path')[0]
        self.assertEqual('stroke-width:2', path.get('style'))
        self.assertEqual('f-000000', path.get('class'))

    def test_keeps_the_color_it_took(self):
        self.assertIn('.f-000000 { fill: #000000 }',
                      scheme('<path style="fill:#000000"/>'))

    def test_drops_a_style_left_empty(self):
        path = find(parsed('<path style="fill:#000000"/>'), 'path')[0]
        self.assertIsNone(path.get('style'))

    def test_leaves_a_style_it_took_nothing_out_of(self):
        path = find(parsed('<path style="stroke-width:2;"/>'), 'path')[0]
        self.assertEqual('stroke-width:2;', path.get('style'))


class TestWhatTheCascadeArrivesAt(unittest.TestCase):
    # One rule per property per element is the whole of it: two of them
    # naming the same property would be settled between themselves by where
    # they happen to land in the <style>, which is nothing to do with what
    # the drawing says.

    def test_a_style_declaration_outranks_the_attribute(self):
        path = find(parsed('<path fill="#ff0000" style="fill:#0000ff"/>'),
                    'path')[0]
        self.assertEqual('f-0000ff', path.get('class'))

    def test_the_attribute_the_style_outranked_is_not_named_as_well(self):
        self.assertNotIn('f-ff0000',
                         scheme('<path fill="#ff0000" style="fill:#0000ff"/>'))

    def test_the_last_declaration_of_a_style_wins(self):
        path = find(parsed('<path style="fill:#ff0000;fill:#0000ff"/>'),
                    'path')[0]
        self.assertEqual('f-0000ff', path.get('class'))

    def test_the_declaration_it_outranked_goes_too(self):
        # left behind it would outrank the rule put in the winner's place
        path = find(parsed('<path style="fill:#ff0000;fill:#0000ff"/>'),
                    'path')[0]
        self.assertIsNone(path.get('style'))

    def test_a_gradient_in_a_style_outranks_a_color_attribute(self):
        root = parsed('<defs><linearGradient id="g">'
                      '<stop offset="0" stop-color="#e3e3e3"/>'
                      '</linearGradient></defs>'
                      '<rect id="r" fill="#000000" style="fill:url(#g)"/>')
        rect = [el for el in find(root, 'rect') if el.get('id') == 'r'][0]
        self.assertEqual('fu-g', rect.get('class'))
        self.assertIsNone(rect.get('style'))


class TestTheInitialFill(unittest.TestCase):
    # A mark that asks for no fill is painted black, which is what most of
    # the lettering comes down to and exactly the color that has to go.

    def test_says_the_color_a_mark_was_taking_anyway(self):
        text = find(parsed('<text>exception</text>'), 'text')[0]
        self.assertEqual('f-000000', text.get('class'))

    def test_leaves_a_mark_that_asks_for_a_color(self):
        text = find(parsed('<text fill="#808080">x</text>'), 'text')[0]
        self.assertEqual('f-808080', text.get('class'))

    def test_leaves_a_mark_that_inherits_one(self):
        text = find(parsed('<g fill="white"><text>x</text></g>'), 'text')[0]
        self.assertIsNone(text.get('class'))

    def test_leaves_what_a_use_site_colors(self):
        # a mark inside <defs> is stood up elsewhere and takes its color from
        # there; saying what it is painted in would cut it off from that
        root = parsed('<defs><path id="p"/></defs>'
                      '<use xlink:href="#p" fill="#0000ff"/>')
        self.assertIsNone(find(root, 'path')[0].get('class'))


class TestTheRoot(unittest.TestCase):
    # The viewer writes `class="dark"` onto the root itself, and a second
    # `class` attribute beside the first is not XML.  Qt's renderer applies
    # no rule to the root either way.

    def test_never_gives_the_root_a_class(self):
        self.assertIsNone(parsed('<text fill="black">x</text>').get('class'))

    def test_restates_what_the_root_is_drawn_in_on_a_group(self):
        root = etree.fromstring(
            ('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"'
             ' viewBox="0 0 20 10" fill="black"><text>x</text></svg>'
             ).encode('utf-8'))
        root = etree.fromstring(fit_for_the_viewer(etree.tostring(root)))

        groups = [el for el in find(root, 'g') if el.get('class')]
        self.assertEqual(['f-000000'], [el.get('class') for el in groups])
        self.assertEqual(['text'],
                         [etree.QName(child).localname for child in groups[0]])

    def test_leaves_the_color_on_the_root(self):
        # the drawing inherits from it, and no rule of ours reaches the root
        root = etree.fromstring(fit_for_the_viewer(
            ('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"'
             ' fill="black"><text>x</text></svg>').encode('utf-8')))
        self.assertEqual('black', root.get('fill'))


class TestTheBackdrop(unittest.TestCase):
    # The drawings have no ground of their own; they borrowed the page's.

    def test_draws_one_behind_everything(self):
        root = parsed('<polygon fill="white"/>')
        first = [el for el in root if isinstance(el.tag, str)][1]
        self.assertEqual(BACKDROP_CLASS, first.get('class'))

    def test_covers_the_view_box(self):
        rect = find(parsed('<polygon fill="white"/>'), 'rect')[0]
        self.assertEqual(('0', '0', '20', '10'),
                         (rect.get('x'), rect.get('y'),
                          rect.get('width'), rect.get('height')))

    def test_is_the_page_it_is_on(self):
        css = scheme('<polygon fill="white"/>')
        self.assertIn('.qch-backdrop { fill: #ffffff }', css)
        self.assertIn('svg.dark .qch-backdrop { fill: #262626 }', css)


class TestGradients(unittest.TestCase):
    # Qt's renderer reads a stop's color off the stop and never asks the
    # stylesheet, so a gradient is copied rather than restyled.

    GRADIENT = ('<defs><linearGradient id="g">'
                '<stop offset="0" stop-color="#e3e3e3"/>'
                '</linearGradient></defs>'
                '<rect fill="url(#g)"/>')

    def test_copies_the_gradient_into_a_dark_twin(self):
        ids = [el.get('id') for el in find(parsed(self.GRADIENT),
                                           'linearGradient')]
        self.assertEqual(['g', 'g' + GRADIENT_SUFFIX], ids)

    def test_the_twin_is_made_of_dark_stops(self):
        twin = find(parsed(self.GRADIENT), 'linearGradient')[1]
        self.assertEqual('#353535',
                         find(twin, 'stop')[0].get('stop-color'))

    def test_leaves_the_original_alone(self):
        original = find(parsed(self.GRADIENT), 'linearGradient')[0]
        self.assertEqual('#e3e3e3', find(original, 'stop')[0].get('stop-color'))

    def test_switches_the_reference_rather_than_the_color(self):
        css = scheme(self.GRADIENT)
        self.assertIn('.fu-g { fill: url(#g) }', css)
        self.assertIn('svg.dark .fu-g { fill: url(#g%s) }' % GRADIENT_SUFFIX,
                      css)

    def test_follows_a_gradient_standing_on_another(self):
        root = parsed('<defs>'
                      '<linearGradient id="a">'
                      '<stop offset="0" stop-color="#e3e3e3"/>'
                      '</linearGradient>'
                      '<linearGradient id="b" xlink:href="#a"/>'
                      '</defs><rect fill="url(#b)"/>')
        twin = [el for el in find(root, 'linearGradient')
                if el.get('id') == 'b' + GRADIENT_SUFFIX][0]
        self.assertEqual('#a' + GRADIENT_SUFFIX,
                         twin.get('{http://www.w3.org/1999/xlink}href'))

    def test_the_twin_carries_no_id_of_the_original(self):
        twin = find(parsed('<defs><linearGradient id="g">'
                           '<stop id="s" offset="0" stop-color="#e3e3e3"/>'
                           '</linearGradient></defs>'
                           '<rect fill="url(#g)"/>'), 'linearGradient')[1]
        self.assertIsNone(find(twin, 'stop')[0].get('id'))


class TestLeavingWellAlone(unittest.TestCase):
    def test_hands_back_what_it_cannot_read(self):
        self.assertEqual(b'not an svg', fit_for_the_viewer(b'not an svg'))

    def test_hands_back_what_is_not_an_svg(self):
        data = b'<html xmlns="http://www.w3.org/2000/svg"/>'
        self.assertEqual(data, fit_for_the_viewer(data))

    def test_states_no_scheme_for_a_drawing_with_no_color_to_map(self):
        # it is still given the pixels; there is just nothing to say about it
        root = parsed('<path fill="none"/>')
        self.assertEqual([], find(root, 'style'))
        self.assertEqual([], find(root, 'rect'))


class TestTheRaster(unittest.TestCase):
    # Qt rasterises a drawing at the size the file declares, whatever the
    # ratio of the display, so on a Retina screen it is blown up and comes
    # out soft.  Declare it larger and leave the layout to the page.

    def test_asks_for_more_pixels_of_the_drawing(self):
        root = parsed('<polygon fill="white"/>')
        self.assertEqual(('40', '20'), (root.get('width'), root.get('height')))

    def test_leaves_the_drawing_where_it_is(self):
        root = parsed('<polygon fill="white"/>')
        self.assertEqual('0 0 20 10', root.get('viewBox'))

    def test_keeps_the_unit_the_drawing_was_sized_in(self):
        root = etree.fromstring(fit_for_the_viewer(
            ('<svg xmlns="http://www.w3.org/2000/svg" width="243px"'
             ' height="40px" viewBox="0 0 269 44"/>').encode('utf-8')))
        self.assertEqual(('486px', '80px'),
                         (root.get('width'), root.get('height')))

    def test_says_what_the_coordinates_meant_when_nothing_did(self):
        # without a viewBox a larger `width` would only lay out a larger
        # canvas around the same drawing
        root = etree.fromstring(fit_for_the_viewer(
            ('<svg xmlns="http://www.w3.org/2000/svg" width="545.89282"'
             ' height="156.9409"/>').encode('utf-8')))
        self.assertEqual('0 0 545.89282 156.9409', root.get('viewBox'))
        self.assertEqual(('1091.7856', '313.8818'),
                         (root.get('width'), root.get('height')))

    def test_leaves_a_drawing_sized_in_a_way_it_cannot_read(self):
        data = ('<svg xmlns="http://www.w3.org/2000/svg" width="100%"'
                ' height="100%"/>').encode('utf-8')
        self.assertEqual(data, fit_for_the_viewer(data))
