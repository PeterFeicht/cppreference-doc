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

# Fits the diagrams of the website for a help viewer: a dark scheme of their
# own, and enough pixels to be drawn sharply.
#
# They are drawn for a page that is white -- black strokes, black lettering,
# a grey label, and nothing at all behind them -- so on a dark page they all
# but disappear.  A stylesheet cannot reach inside an image to say otherwise,
# and no help viewer repaints one.
#
# What a help viewer does do is tell the drawing which page it is on: both
# Qt Assistant and Qt Creator put `class="dark"` on the root <svg> element
# when their own theme is dark, and leave it off when it is light.  So the
# drawing can answer for itself.  Name every color one is drawn with by a
# class, state under that class the color it already had, and state the dark
# counterpart under `svg.dark`.
#
# Nothing is taken away by this.  A viewer that does not know the trick never
# matches `svg.dark` and renders exactly what it rendered before -- which is
# also why a backdrop is drawn behind the whole thing.  The drawings have no
# ground of their own; they borrowed the page's, and once the dark sheet
# stops plating every image in white they need to bring one.
#
# Qt's own SVG renderer is what settles all of this, and it honours a class
# selector but not an attribute one, which is why the classes are written out
# rather than the colors matched where they stand.
#
# The pixels are the other half: see `RASTER_SCALE`.

import copy
import re

from io import BytesIO

from lxml import etree

from commands import qch_css

SVG_NS = 'http://www.w3.org/2000/svg'

# The properties a drawing states a color in, and the letter that stands for
# each in a class name.
SVG_COLOR_PROPERTIES = (('fill', 'f'), ('stroke', 's'))

COLOR_PREFIXES = dict(SVG_COLOR_PROPERTIES)

# A gradient is the one thing a rule cannot restyle: Qt's renderer reads a
# stop's color off the stop and never asks the stylesheet, so `stop-color`
# is not a property we can name by a class.  What a rule can do is say which
# gradient to use -- `fill: url(#...)` is honoured -- so each one is copied
# into a dark twin and the reference is switched instead.
GRADIENT_SUFFIX = '-qch-dark'
GRADIENT_PREFIXES = {'fill': 'fu', 'stroke': 'su'}
STOP_COLOR = 'stop-color'
XLINK_HREF = '{http://www.w3.org/1999/xlink}href'
URL_RE = re.compile(r'^url\(\s*[\'"]?#([^\'")\s]+)')

# The ground the drawing brings with it.  White is what it was drawn against
# and what it has been borrowing from the page.
BACKDROP_CLASS = 'qch-backdrop'
BACKDROP_LIGHT = '#ffffff'

# What SVG paints a shape in when nothing says otherwise.  Most of the
# lettering in these drawings asks for no color at all and takes this, which
# is the very color that has to go.
INITIAL_FILL = 'black'

# The elements that put a mark on the page themselves.  A <g> is left out:
# it paints nothing, and naming a color on one would hand it to every child
# that inherits rather than to the mark we are after.  So is a <use>, whose
# fill is settled by what it points at.
PAINTED_TAGS = frozenset([
    'circle', 'ellipse', 'line', 'path', 'polygon', 'polyline', 'rect',
    'text', 'tspan',
])

# A mark inside one of these is not drawn where it stands -- a <use>
# elsewhere stands it up, and it takes its color from there.  Saying what it
# is painted in would cut it off from the color the use site hands it, which
# is how the plot markers of the graphs are colored.
REFERENCED_CONTAINERS = frozenset([
    'clipPath', 'defs', 'marker', 'mask', 'pattern', 'symbol',
])

VIEW_BOX_RE = re.compile(r'[\s,]+')

# How much more of a drawing to rasterise than the page asks for.
#
# A help viewer hands an SVG to Qt as it found it, and Qt rasterises it at the
# size the file declares, taking no account of the ratio of the display.  On a
# Retina screen that bitmap is then blown up to twice the pixels it was drawn
# with, and a hairline diagram comes out soft.  The viewer's own zoom
# multiplies on top of that.
#
# So declare the drawing at twice the size and leave what it is drawn at to
# the page.  Every one of these figures is sized by `width` and `height` on
# the <img> element -- litehtml maps the two onto the CSS properties and only
# falls back on the file's own size when neither is given -- so nothing moves;
# there is simply more of the drawing to draw.  A display that is not Retina
# scales it back down, which the viewer does smoothly and which if anything
# reads better than rasterising at the size.
RASTER_SCALE = 2

LENGTH_RE = re.compile(r'^\s*([0-9]*\.?[0-9]+)\s*([a-z]*)\s*$', re.IGNORECASE)


def dark_mark(rgba):
    # A diagram is dark marks on a light ground, and on a dark page it wants
    # to be light marks on a dark one.  Which of the two a color is, the
    # color itself says: map a dark one the way the text of the page is
    # mapped and a light one the way a surface is, and the drawing comes
    # over whole -- the lettering lightens, the box behind it darkens, and
    # the muted grey of a label stays the step off the lettering that it was.
    return (qch_css.dark_color('text', rgba)
            or qch_css.dark_color('surface', rgba))


def color_rule(prop, value):
    # What one color declaration becomes: the class that names it, and the
    # color it stands for light and dark.  None if it states no color we can
    # map -- `none`, a `url(...)` naming a gradient, a color that already
    # suits a dark page.
    rgba = qch_css.parse_color(value)
    if rgba is None or rgba[3] <= 0:
        return None

    dark = dark_mark(rgba)
    if dark is None:
        return None

    return ('%s-%s' % (COLOR_PREFIXES[prop], qch_css.color_key(rgba)),
            prop, qch_css.format_color(rgba), qch_css.format_color(dark))


def style_declarations(style):
    # The declarations of a `style` attribute as `(property, value, text)`,
    # with the text of each kept so that one we do not touch goes back as it
    # was.
    for declaration in style.split(';'):
        if not declaration.strip():
            continue
        name, separator, value = declaration.partition(':')
        if separator:
            yield name.strip().lower(), value.strip(), declaration
        else:
            yield None, None, declaration


def declared_paint(el, prop):
    # What one paint property is set to on an element, as
    # `(value, from the style attribute)`, or `(None, False)` if nothing on
    # the element sets it.  A `style` declaration outranks a presentation
    # attribute, and the last of several inside the attribute is the one the
    # cascade arrives at.
    value = None

    for name, declared, _ in style_declarations(el.get('style') or ''):
        if name == prop:
            value = declared

    if value is not None:
        return value, True

    return el.get(prop), False


def declares_fill(el):
    if el.get('fill') is not None:
        return True
    return any(prop == 'fill'
               for prop, _, _ in style_declarations(el.get('style') or ''))


def marks_taking_the_initial_fill(root):
    # The marks painted black because nothing asks for anything else, which
    # is what most of the lettering in these drawings comes down to and
    # exactly the color that has to go.  Nothing states it, so there is
    # nothing to move out of the way or to outrank: say it outright, which
    # paints what was being painted anyway and gives the dark rule something
    # to hang on.
    #
    # This is answered before anything is rewritten.  The elements are walked
    # in document order, so by the time a mark is reached its ancestors have
    # had their colors moved into classes already, and asking them then would
    # get the wrong answer.
    found = []

    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        if etree.QName(el).localname not in PAINTED_TAGS:
            continue

        ancestors = [a for a in el.iterancestors() if isinstance(a.tag, str)]
        if any(etree.QName(a).localname in REFERENCED_CONTAINERS
               for a in ancestors):
            continue
        if any(declares_fill(el) for el in [el] + ancestors):
            continue

        found.append(el)

    return found


def add_classes(el, names):
    if not names:
        return
    existing = el.get('class')
    el.set('class', ' '.join(([existing] if existing else []) + names))


def is_gradient(el):
    return (isinstance(el.tag, str)
            and etree.QName(el).localname.endswith('Gradient'))


def set_stop_color(stop, value):
    kept = [text
            for prop, _, text in style_declarations(stop.get('style') or '')
            if prop != STOP_COLOR]
    if kept:
        stop.set('style', ';'.join(kept))
    else:
        stop.attrib.pop('style', None)
    stop.set(STOP_COLOR, value)


def stop_color(stop):
    # As the cascade reads it: a `style` declaration outranks the attribute,
    # and the last of several inside the attribute is the one that counts.
    found = None

    for prop, value, _ in style_declarations(stop.get('style') or ''):
        if prop == STOP_COLOR:
            found = value

    return found if found is not None else stop.get(STOP_COLOR)


def darken_gradient(twin, twins):
    # The copy keeps everything that shapes the gradient and changes only
    # what it is made of.  One gradient standing on another -- which is how
    # a drawing program states a gradient placed on a shape -- is pointed at
    # the other's twin.
    href = twin.get(XLINK_HREF) or ''
    if href.startswith('#') and href[1:] in twins:
        twin.set(XLINK_HREF, '#' + twins[href[1:]])

    for el in twin.iter():
        if not isinstance(el.tag, str):
            continue
        if el is not twin:
            # the ids of the copy are no one's business and must not collide
            el.attrib.pop('id', None)
        if etree.QName(el).localname != 'stop':
            continue

        value = stop_color(el)
        if value is None:
            continue
        rgba = qch_css.parse_color(value)
        if rgba is None or rgba[3] <= 0:
            continue
        dark = dark_mark(rgba)
        if dark is not None:
            set_stop_color(el, qch_css.format_color(dark))


def twin_gradients(root):
    # Returns the gradients that now have a dark twin, as `{id: twin id}`.
    originals = [el for el in root.iter()
                 if is_gradient(el) and el.get('id')]
    twins = {el.get('id'): el.get('id') + GRADIENT_SUFFIX for el in originals}

    for el in originals:
        twin = copy.deepcopy(el)
        twin.set('id', twins[el.get('id')])
        darken_gradient(twin, twins)
        el.addnext(twin)

    return twins


def gradient_rule(prop, value, twins):
    # `fill: url(#...)` is a reference rather than a color, and a rule can
    # say which gradient to follow even where it cannot say what the
    # gradient is made of.
    match = URL_RE.match(value)
    if match is None or match.group(1) not in twins:
        return None

    name = match.group(1)
    return ('%s-%s' % (GRADIENT_PREFIXES[prop], name), prop, value,
            'url(#%s)' % twins[name])


def take_paint_colors(el, twins, initial_fill):
    # The rules for what one element is painted in: at most one for each of
    # `fill` and `stroke`, built from the declaration the cascade arrives at.
    # One per property is the whole of it -- two rules naming the same
    # property on the same element would be settled between themselves by
    # where they happen to land in the <style>, which is nothing to do with
    # what the drawing says.
    #
    # A `style` declaration we answer is moved out of the attribute, that
    # outranking every rule and the whole point being to be outrankable; the
    # rule put in its place states what it stated, so the drawing reads as it
    # did.  A presentation attribute is left where it is: a rule already
    # outranks one, and leaving it is what a renderer that reads no CSS at
    # all goes on drawing.
    found = []
    taken = set()

    for prop, _ in SVG_COLOR_PROPERTIES:
        value, from_style = declared_paint(el, prop)

        if value is None:
            if prop != 'fill' or not initial_fill:
                continue
            # Nothing asks for a fill, so the mark takes the black SVG paints
            # with.  Say it outright, which paints what was being painted
            # anyway and gives the dark rule something to hang on.
            value = INITIAL_FILL

        rule = gradient_rule(prop, value, twins) or color_rule(prop, value)
        if rule is None:
            continue

        if from_style:
            taken.add(prop)
        found.append(rule)

    if taken:
        drop_style_declarations(el, taken)

    return found


def drop_style_declarations(el, props):
    # Every declaration of these properties goes, and not just the one the
    # cascade arrived at: a loser left behind would outrank the rule we put
    # in the winner's place and paint the element in a color the drawing had
    # already taken back.
    kept = [text for name, _, text in style_declarations(el.get('style') or '')
            if name not in props]
    if kept:
        el.set('style', ';'.join(kept))
    else:
        el.attrib.pop('style', None)


def scale_for_the_raster(root):
    # Leaves the drawing exactly where it is and asks for more pixels of it.
    # The `viewBox` is what holds the two apart: the coordinates inside it go
    # on meaning what they meant, and only the box they are drawn into grows.
    width = LENGTH_RE.match(root.get('width') or '')
    height = LENGTH_RE.match(root.get('height') or '')
    if width is None or height is None:
        # a drawing sized in a way we are not going to second-guess, or in
        # per cent of something we cannot see
        return False

    if not root.get('viewBox'):
        # Nothing yet says what the coordinates inside mean, and without that
        # a larger `width` would only lay out a larger canvas around the same
        # drawing.  State the box it has been drawn in all along.
        root.set('viewBox', '0 0 %s %s' % (width.group(1), height.group(1)))

    for name, length in (('width', width), ('height', height)):
        root.set(name, '%s%s' % (
            format_length(float(length.group(1)) * RASTER_SCALE),
            length.group(2)))

    return True


def format_length(value):
    return ('%.4f' % value).rstrip('0').rstrip('.')


def backdrop_box(root):
    # The rectangle the drawing is laid out in: the `viewBox` it states, or
    # the size it declares when it states none.
    view_box = root.get('viewBox')
    if view_box:
        numbers = VIEW_BOX_RE.split(view_box.strip())
        if len(numbers) == 4:
            return numbers

    width, height = root.get('width'), root.get('height')
    if width and height:
        return ['0', '0', width, height]

    return None


def add_backdrop(root, rules):
    box = backdrop_box(root)
    if box is None:
        return

    rect = etree.Element('{%s}rect' % SVG_NS)
    rect.set('class', BACKDROP_CLASS)
    for name, value in zip(('x', 'y', 'width', 'height'), box):
        rect.set(name, value)

    root.insert(0, rect)
    rules[BACKDROP_CLASS] = ('fill', BACKDROP_LIGHT,
                             qch_css.DARK_PAGE_BACKGROUND)


def root_colors(root):
    # What the root element is drawn in, read without touching it.  Nothing
    # of the root's is moved or removed: the whole drawing inherits from it,
    # and Qt's renderer does not apply a rule to the root at all, so taking
    # a color off it would leave the drawing with no color to inherit.
    found = []

    for prop, _ in SVG_COLOR_PROPERTIES:
        value, _ = declared_paint(root, prop)
        if value is None:
            continue

        rule = color_rule(prop, value)
        if rule is not None:
            found.append(rule)

    return found


def wrap_root_colors(root, found):
    # Qt's renderer applies no rule to the root <svg> element, and the root
    # is the one element we cannot hand a class to in any case -- the viewer
    # writes `class="dark"` onto it, and a second `class` attribute beside
    # the first is not XML.  So what the root is drawn in is restated on a
    # <g> put around everything it holds.  The class goes there, and the
    # drawing inherits from it exactly as it inherited from the root.
    if not found:
        return

    names = []
    for class_name, _, _, _ in found:
        if class_name not in names:
            names.append(class_name)

    group = etree.Element('{%s}g' % SVG_NS)
    group.set('class', ' '.join(names))
    for child in list(root):
        group.append(child)
    root.append(group)


def style_element(rules):
    # The colors as they were, and then the dark counterparts.  Both are
    # stated: the light ones are what a color moved out of a `style`
    # attribute falls back to, and the dark ones outrank them on the `dark`
    # class the root carries as well as on being below.
    light = ['  .%s { %s: %s }' % (name, rules[name][0], rules[name][1])
             for name in sorted(rules)]
    dark = ['  svg.dark .%s { %s: %s }' % (name, rules[name][0],
                                           rules[name][2])
            for name in sorted(rules)]

    style = etree.Element('{%s}style' % SVG_NS)
    style.set('type', 'text/css')
    style.text = '\n%s\n\n%s\n' % ('\n'.join(light), '\n'.join(dark))
    return style


def fit_for_the_viewer(data):
    # The drawing with a dark scheme of its own and enough pixels to be drawn
    # sharply, or the data as it came if there is nothing to be done to it.
    try:
        tree = etree.parse(BytesIO(data))
    except etree.XMLSyntaxError:
        return data

    root = tree.getroot()
    if etree.QName(root).localname != 'svg':
        return data

    scaled = scale_for_the_raster(root)
    rules = {}
    initial_fill = set(marks_taking_the_initial_fill(root))
    twins = twin_gradients(root)

    from_root = root_colors(root)
    wrap_root_colors(root, from_root)
    for class_name, prop, light, dark in from_root:
        rules[class_name] = (prop, light, dark)

    for el in root.iter():
        if el is root or not isinstance(el.tag, str):
            # the root is answered above; the rest is a comment or a
            # processing instruction
            continue

        found = take_paint_colors(el, twins, el in initial_fill)

        names = []
        for class_name, prop, light, dark in found:
            rules[class_name] = (prop, light, dark)
            if class_name not in names:
                names.append(class_name)
        add_classes(el, names)

    if not rules and not scaled:
        return data

    if rules:
        add_backdrop(root, rules)
        root.insert(0, style_element(rules))

    return etree.tostring(tree, xml_declaration=True, encoding='UTF-8')
