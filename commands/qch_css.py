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

# Builds the stylesheets that the Qt Help (.qch) rendition of the
# documentation links.
#
# Both help viewers that read the archive -- Qt Assistant since Qt 6.2 and Qt
# Creator since 4.11 -- render with litehtml, which follows a stylesheet, so
# the pages keep their classes and link one rather than carrying the site
# stylesheet flattened into `style` attributes.  See `preprocess_qch_html`.
#
# Three files are written, because of the names the viewers go looking for.
# Asked for `offline-simple.css`, both serve `offline-dark.css` in its place
# when their own theme is dark, and `offline.css` when it is light; Qt Creator
# 21 does the same for a page that asks for `offline.css` directly.  The pages
# here ask for `offline-simple.css`, and the light sheet is written under both
# of the other names so that whichever one a viewer reaches for is there.
#
# The dark sheet is the light one followed by a counterpart for every color it
# declares, mapped from the light color rather than written out by hand, so
# that it keeps up with cppreference's own stylesheet on its own.  What a rule
# cannot reach is the color a wiki template wrote into a `style` attribute --
# the green and red of the compiler-support tables, the tints behind the
# revision markers.  `preprocess_qch_html` names each of those with a class,
# and the rules for them are marked `!important`, which is what lets them beat
# an inline declaration.

import colorsys
import logging
import os
import re

from xml.dom import SyntaxErr

import cssutils

from cssutils.css import ColorValue

CSS_DIR = 'common'

# The site's own stylesheets, in the order the pages link them.
SITE_CSS_NAMES = ['ext.css', 'site_modules.css']

# Ours, which the two above are folded into.
LINKED_CSS_NAME = 'offline-simple.css'
LIGHT_CSS_NAMES = ['offline.css', 'offline-simple.css']
DARK_CSS_NAME = 'offline-dark.css'

# The stylesheets kept at the root of the source tree: `qch-viewer.css`
# adapts the site layout to a help pane and carries the workarounds a help
# viewer needs, `qch-dark.css` the page colors of the dark scheme.
ASSET_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWER_CSS = 'qch-viewer.css'
DARK_BASE_CSS = 'qch-dark.css'

# A class name is `<prefix>-<key>`, where the prefix says which property the
# generated rule sets and which of the three palette roles maps the color, and
# the key is the color itself (see `color_key`).  The class name is therefore
# the only thing the HTML pass needs to hand over.
CLASS_PREFIXES = {
    'c':   ('color', 'text'),
    'bg':  ('background-color', 'surface'),
    'bd':  ('border-color', 'line'),
    'bdt': ('border-top-color', 'line'),
    'bdr': ('border-right-color', 'line'),
    'bdb': ('border-bottom-color', 'line'),
    'bdl': ('border-left-color', 'line'),
}

# The CSS properties whose color we map.  Shorthands are listed too: we pick
# the color out of them and leave the rest of the shorthand alone, since the
# generated declarations only ever set a color.
COLOR_PROPERTIES = {
    'color': 'c',
    'background': 'bg',
    'background-color': 'bg',
    'border': 'bd',
    'border-color': 'bd',
    'border-top': 'bdt',
    'border-top-color': 'bdt',
    'border-right': 'bdr',
    'border-right-color': 'bdr',
    'border-bottom': 'bdb',
    'border-bottom-color': 'bdb',
    'border-left': 'bdl',
    'border-left-color': 'bdl',
}

# Keywords that stand where a color would, but name no color of their own.
COLOR_KEYWORDS = frozenset([
    'inherit', 'initial', 'unset', 'revert', 'transparent', 'currentcolor',
    'none',
])

# `url(...)` is matched so that it is passed over whole: a file name can hold
# a word that is also a color, such as `tan`.
COLOR_TOKEN_RE = re.compile(
    r'url\([^)]*\)'
    r'|#[0-9a-fA-F]+'
    r'|(?:rgb|rgba|hsl|hsla)\([^)]*\)'
    r'|[a-zA-Z]+')


# -- colors ----------------------------------------------------------------

def token_color(token):
    # The color one token of a declaration value names as (r, g, b, a), or
    # None if it names none: a length such as `1px`, a keyword such as
    # `solid` or `transparent`, a `url(...)`.
    lowered = token.lower()
    if lowered in COLOR_KEYWORDS or lowered.startswith('url('):
        return None
    try:
        color = ColorValue(token)
    except SyntaxErr:
        return None
    return (color.red, color.green, color.blue, color.alpha)


def parse_color(value):
    # Returns the first color of a declaration value as (r, g, b, a), or None
    # if it names no color.  Tokens that are not colors, such as `1px` or
    # `solid` in a border shorthand, are skipped.
    for token in COLOR_TOKEN_RE.findall(value):
        rgba = token_color(token)
        if rgba is not None:
            return rgba
    return None


def single_color(name, value):
    # The one color a declaration of this property settles, or None if it
    # settles none -- or more than one, which is a value nothing can be
    # pulled out of and restated on its own: doing that to the
    # `transparent transparent silver transparent` of a CSS triangle would
    # paint all four of its sides, and to a gradient would put its first stop
    # behind the whole element.
    #
    # Which tokens stand where a color would depends on the property.  One
    # that states nothing else takes a color per side -- `border-color` takes
    # four -- so a keyword among them is one of those sides.  In a shorthand
    # a keyword is usually some other sub-property: the `none` of
    # `background: none repeat scroll 0 0 #f0f0f0` is the background image.
    prop, _ = CLASS_PREFIXES[COLOR_PROPERTIES[name]]
    found = []

    for token in COLOR_TOKEN_RE.findall(value):
        rgba = token_color(token)
        if rgba is not None:
            found.append(rgba)
        elif prop == name and token.lower() in COLOR_KEYWORDS:
            found.append(None)

    return found[0] if len(found) == 1 else None


def map_value_colors(role, value):
    # The value with every color in it carried over to a dark page where it
    # stands, and everything else -- a length, a keyword, a `url(...)` -- left
    # as it was.  None if nothing in it needed mapping.
    mapped = False

    def replace(match):
        nonlocal mapped
        token = match.group(0)
        rgba = token_color(token)
        if rgba is None or rgba[3] <= 0:
            return token

        dark = dark_color(role, rgba)
        if dark is None:
            return token

        mapped = True
        return format_color(dark)

    text = COLOR_TOKEN_RE.sub(replace, value)
    return text if mapped else None


def color_key(rgba):
    # Returns the part of a class name that spells out the color.  The alpha
    # channel is kept to a thousandth, which is finer than any value the site
    # stylesheet uses.
    red, green, blue, alpha = rgba
    if alpha >= 1:
        return '%02x%02x%02x' % (red, green, blue)
    return '%02x%02x%02x-%03d' % (red, green, blue, round(alpha * 1000))


def color_from_key(key):
    digits, _, alpha = key.partition('-')
    rgb = tuple(int(digits[i:i+2], 16) for i in (0, 2, 4))
    return rgb + (int(alpha) / 1000 if alpha else 1.0,)


def format_color(rgba):
    red, green, blue, alpha = rgba
    if alpha >= 1:
        return '#%02x%02x%02x' % (red, green, blue)
    return 'rgba(%d, %d, %d, %s)' % (red, green, blue, '%g' % alpha)


def class_for_declaration(name, value):
    # Returns the class naming the color of a CSS declaration, or None if the
    # declaration carries no color we can re-declare.
    prefix = COLOR_PROPERTIES.get(name)
    if prefix is None:
        return None
    # A class names one color and the rule it hangs on sets the whole
    # property to it, so a value settling more than one is one we have no way
    # to say anything about; leave it light.
    rgba = single_color(name, value)
    if rgba is None or rgba[3] <= 0:
        return None
    return '%s-%s' % (prefix, color_key(rgba))


def hex_to_rgb(value):
    return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))


def lightness_of(value):
    return colorsys.rgb_to_hls(*[c / 255 for c in hex_to_rgb(value)])[1]


# -- dark palette ----------------------------------------------------------

# The page colors of the dark scheme.  They are those of the stylesheet Qt
# Creator falls back to for documentation that ships no dark variant, so that
# the cppreference pages sit well next to the Qt pages in the same help pane.
DARK_PAGE_BACKGROUND = '#262626'
DARK_PAGE_TEXT = '#d0d0d0'
DARK_LINK = '#6ab0f3'

# The dark backgrounds are laid out from the page background upwards.
DARK_BACKGROUND_L = lightness_of(DARK_PAGE_BACKGROUND)

# A color light enough to have been meant for a dark background already is
# left alone, rather than flipped into something unreadable.
DARK_TEXT_KEEP_L = 0.55
DARK_SURFACE_KEEP_L = 0.45

# How far from grey a dark background or border is allowed to be.  The light
# highlight bands are vivid enough that carrying all of it over would make
# them shout on a dark page.
DARK_SURFACE_MAX_CHROMA = 0.30

# WCAG AA for normal text, which lightening in HSL alone does not reach: a
# saturated blue, such as the keywords of the code samples, carries little
# luminance however light HSL calls it.
DARK_TEXT_MIN_CONTRAST = 4.5


def hsl_to_rgb(hue, saturation, lightness):
    # Note the argument order, which is that of CSS rather than `colorsys`.
    return tuple(round(c * 255)
                 for c in colorsys.hls_to_rgb(hue, lightness, saturation))


def relative_luminance(rgb):
    channels = []
    for value in (c / 255 for c in rgb):
        channels.append(value / 12.92 if value <= 0.03928
                        else ((value + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(rgb, other):
    lighter, darker = sorted(
        [relative_luminance(rgb), relative_luminance(other)], reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def lighten_to_contrast(hue, saturation, lightness):
    background = hex_to_rgb(DARK_PAGE_BACKGROUND)
    while lightness < 0.92:
        if contrast_ratio(hsl_to_rgb(hue, saturation, lightness),
                          background) >= DARK_TEXT_MIN_CONTRAST:
            break
        lightness += 0.01
    return lightness


def dark_text(hue, saturation, lightness):
    if lightness >= DARK_TEXT_KEEP_L:
        return None
    if saturation < 0.08:
        # Grey text, including the body color: black lands just short of
        # white, and the muted greys stay a step below it.
        saturation, lightness = 0.0, 0.82 - 0.44 * lightness
    else:
        # Colored text, the bulk of which is the syntax highlighting of the
        # code samples.  Lighten it and take the edge off the saturation,
        # which would otherwise glare against the dark background.
        saturation = min(saturation, 0.62)
        lightness = min(max(0.88 - 0.55 * lightness, 0.58), 0.76)
    return (hue, saturation,
            lighten_to_contrast(hue, saturation, lightness))


def chroma_of(saturation, lightness):
    return (1.0 - abs(2.0 * lightness - 1.0)) * saturation


def saturation_for_chroma(chroma, lightness):
    # The HSL saturation that gives this chroma at this lightness.
    span = 1.0 - abs(2.0 * lightness - 1.0)
    return min(chroma / span, 1.0) if span else 0.0


def darken(hue, saturation, lightness, reach):
    # Carries a light color down into the dark range, keeping how far from
    # grey it was.  Chroma, and not HSL saturation, is what measures that: a
    # pale tint such as `#f3f3fc` is almost grey, yet HSL calls it two thirds
    # saturated, and holding on to that would turn it into a vivid navy.
    chroma = min(chroma_of(saturation, lightness), DARK_SURFACE_MAX_CHROMA)
    return chroma, DARK_BACKGROUND_L + (1.0 - lightness) * reach


def darken_to_contrast(hue, chroma, lightness):
    text = hex_to_rgb(DARK_PAGE_TEXT)
    while lightness > DARK_BACKGROUND_L:
        if contrast_ratio(
                hsl_to_rgb(hue, saturation_for_chroma(chroma, lightness),
                           lightness), text) >= DARK_TEXT_MIN_CONTRAST:
            break
        lightness -= 0.01
    return lightness


def dark_surface(hue, saturation, lightness):
    if lightness <= DARK_SURFACE_KEEP_L:
        return None
    # The light backgrounds span white down to the greys of the table bands,
    # and the spread between them has to survive, or the tables lose their
    # shape.  Keep the order and compress it into the dark range, then take
    # down whatever the body text would not read over: the vivid highlight
    # bands land too light otherwise.
    chroma, lightness = darken(hue, saturation, lightness, 0.55)
    lightness = darken_to_contrast(hue, chroma, lightness)
    return (hue, saturation_for_chroma(chroma, lightness), lightness)


def dark_line(hue, saturation, lightness):
    if lightness <= DARK_SURFACE_KEEP_L:
        return None
    # Borders sit a little above the surfaces, so that they read as lines
    # without being the brightest thing on the page.  They carry no text, so
    # they need no contrast floor of their own.
    chroma, lightness = darken(hue, saturation, lightness, 0.8)
    return (hue, saturation_for_chroma(chroma, lightness), lightness)


DARK_ROLES = {
    'text': dark_text,
    'surface': dark_surface,
    'line': dark_line,
}


def composite_over_white(rgba):
    # The light pages are white underneath, so a translucent color is the
    # opaque color it ends up as.  Resolve it before mapping, and emit the
    # dark counterpart opaque: compositing it over the dark background would
    # be the same thing, and the help viewers handle opaque colors better.
    red, green, blue, alpha = rgba
    return tuple(round(c * alpha + 255 * (1 - alpha))
                 for c in (red, green, blue))


def dark_color(role, rgba):
    # Returns the dark counterpart of a color, or None if it needs none.
    red, green, blue = composite_over_white(rgba)
    hue, lightness, saturation = colorsys.rgb_to_hls(
        red / 255, green / 255, blue / 255)

    mapped = DARK_ROLES[role](hue, saturation, lightness)
    if mapped is None:
        return None

    return hsl_to_rgb(*mapped) + (1.0,)


# -- deriving the dark sheet from the light one ----------------------------

def silence_cssutils():
    # cssutils complains at length about a stylesheet it did not write.
    log = logging.Logger('qch_css')
    log.addHandler(logging.NullHandler())
    cssutils.log.setLog(log)


def dark_declaration_value(name, role, value):
    # What a declaration's value becomes on a dark page, or None if it needs
    # nothing: it names no color of its own, or the color it names already
    # suits a dark page.
    prop, _ = CLASS_PREFIXES[COLOR_PROPERTIES[name]]

    if prop == name:
        # A property that states nothing but color keeps the shape of its
        # value, since it may hold one per side.
        return map_value_colors(role, value)

    # A shorthand such as `border` or `background` states a good deal else
    # besides, and the declaration we write is the longhand, so only the
    # color comes over -- which means a value settling more than one of them
    # is one we have to leave alone.
    rgba = single_color(name, value)
    if rgba is None or rgba[3] <= 0:
        return None

    dark = dark_color(role, rgba)
    return format_color(dark) if dark is not None else None


def color_declarations(style):
    # The declarations of one rule that settle a color, as
    # `(property, dark value, important)`.  One that needs no dark
    # counterpart -- it names no color of its own, or the color it names
    # suits a dark page already -- is reported with none rather than passed
    # over: it is still what the cascade arrives at for that property, and so
    # it still settles what was said above it.
    for prop in style:
        prefix = COLOR_PROPERTIES.get(prop.name)
        if prefix is None:
            continue

        name, role = CLASS_PREFIXES[prefix]
        # Only `!important` is carried over.  cssutils keeps a non-standard
        # priority as it found it -- the site stylesheet carries the old
        # `!ie` hack -- and repeating one would only write a declaration that
        # every renderer throws away.
        yield (name, dark_declaration_value(prop.name, role, prop.value),
               prop.priority == 'important')


# The media a dark counterpart is written for.  A rule the site wrote for
# `print` is left alone: a reader printing from a dark help viewer wants the
# page on paper the way it was meant to be, and everything we derive is
# therefore kept out of the way of the print rules.
DARK_MEDIA = 'screen'


def style_rules(rules, media):
    # Every style rule of a stylesheet, in cascade order and paired with the
    # media it was written for, with the print-only ones left out.
    for rule in rules:
        if rule.typeString == 'MEDIA_RULE':
            if 'print' not in rule.media.mediaText:
                yield from style_rules(rule, rule.media.mediaText)
        elif rule.typeString == 'STYLE_RULE':
            yield media, rule


def declarations_in_cascade_order(rule_list):
    # The color declarations of the sheets, numbered in the order the cascade
    # reads them and kept grouped by the rule and the selector they belong
    # to.  The numbering runs across the sheets together, because the cascade
    # does: what `ext.css` says about `code` is settled by what
    # `site_modules.css` says about it afterwards.
    grouped = []
    index = 0

    for media, rule in rule_list:
        declarations = list(color_declarations(rule.style))
        selectors = []

        for selector in rule.selectorList:
            numbered = []
            for name, dark, important in declarations:
                numbered.append((index, name, dark, important))
                index += 1
            selectors.append((selector.selectorText, numbered))

        grouped.append((media, selectors))

    return grouped


def color_winners(grouped):
    # Which declaration of each (media, selector, property) the light sheet
    # arrives at: an `!important` one ahead of the rest, and the last of
    # those.  Everything we derive is appended to the end of the dark sheet,
    # where it outranks the whole of the light one on order alone, so a
    # counterpart for any other declaration would put a color on the dark
    # page that the light page does not have.
    winners = {}

    for media, selectors in grouped:
        for selector, declarations in selectors:
            for index, name, _, important in declarations:
                key = (media, selector, name)
                winners[key] = max(winners.get(key, (False, -1)),
                                   (important, index))

    return winners


def dark_declarations(media, selector, declarations, winners):
    # The dark counterparts of what one selector of one rule settles.
    texts = []

    for index, name, dark, important in declarations:
        if winners[(media, selector, name)] != (important, index):
            # Something below it has the last word on this property; the dark
            # counterpart belongs to that one.
            continue

        if dark is None:
            # The declaration names no color of its own, or the color works
            # on a dark background as it is; leaving it out lets the light
            # declaration stand.
            continue

        texts.append('%s: %s%s' % (name, dark,
                                   ' !important' if important else ''))

    return texts


def dark_segments(grouped, winners):
    # The dark counterparts of the rules as `(media, rule)` pairs, in their
    # original order.  Order is what makes this work: every rule we emit
    # restates a selector that appears above it in the sheet, so it wins on
    # being later, and two of them settle between themselves exactly as the
    # two rules they came from do.
    #
    # A rule is split when its selectors no longer have the same thing to
    # say -- one of them may have been settled below and the others not --
    # and the ones that still agree are written out together as they were.
    for media, selectors in grouped:
        groups = []

        for selector, declarations in selectors:
            texts = dark_declarations(media, selector, declarations, winners)
            if not texts:
                continue

            for group_texts, group_selectors in groups:
                if group_texts == texts:
                    group_selectors.append(selector)
                    break
            else:
                groups.append((texts, [selector]))

        for texts, group_selectors in groups:
            yield media, '%s { %s }' % (', '.join(group_selectors),
                                        '; '.join(texts))


def wrap_in_media(segments):
    # Runs of rules sharing a media query, each wrapped in one `@media`.
    lines = []
    media = None

    for rule_media, text in segments:
        if rule_media != media:
            if media is not None:
                lines.append('}')
            lines.append('@media %s {' % rule_media)
            media = rule_media
        lines.append('  ' + text)

    if media is not None:
        lines.append('}')

    return '\n'.join(lines)


def dark_stylesheet_rules(*css_texts):
    # The sheets are read together rather than one at a time: the cascade
    # runs through all of them, and which declaration has the last word on a
    # property is only answerable with the lot of them in hand.
    silence_cssutils()
    rule_list = []

    for css_text in css_texts:
        rule_list += list(style_rules(
            cssutils.parseString(css_text, validate=False), DARK_MEDIA))

    grouped = declarations_in_cascade_order(rule_list)
    return wrap_in_media(dark_segments(grouped, color_winners(grouped)))


def dark_class_rules(classes):
    # The counterparts of the colors a wiki template wrote into a `style`
    # attribute.  No rule of ours can outrank an inline declaration on
    # specificity, so these say `!important`, which litehtml honours over the
    # `style` attribute as the cascade asks.
    segments = []

    for name in sorted(classes):
        prefix, _, key = name.partition('-')
        prop, role = CLASS_PREFIXES[prefix]

        dark = dark_color(role, color_from_key(key))
        if dark is None:
            continue

        segments.append((DARK_MEDIA, '.%s { %s: %s !important }' % (
                name, prop, format_color(dark))))

    return wrap_in_media(segments)


# -- assembling the sheets -------------------------------------------------

LIGHT_HEADER = '''\
/* The stylesheet of the Qt Help (.qch) rendition of the documentation.
 *
 * It is cppreference's own stylesheet, the rules the pages used to carry in a
 * <style> block of their own, and a layer that fits the result to a help
 * pane.  Generated by "commands/qch_css.py"; edit that, or "qch-viewer.css".
 */
'''

DARK_HEADER = '''\
/* The dark stylesheet of the Qt Help (.qch) rendition of the documentation.
 *
 * Qt Assistant and Qt Creator serve this file in place of "offline.css" or
 * "offline-simple.css" when their own theme is dark.  It is the light
 * stylesheet followed by a dark counterpart for every color in it, mapped
 * from the light one.  Generated by "commands/qch_css.py"; edit that, or
 * "qch-dark.css".
 */
'''


def read_asset(name):
    with open(os.path.join(ASSET_DIR, name), encoding='utf-8') as a_file:
        return a_file.read()


def read_site_css(source_root):
    return [clean_site_css(read_text(os.path.join(source_root, CSS_DIR, name)))
            for name in SITE_CSS_NAMES]


def clean_page_css(blocks):
    # The <style> blocks lifted out of the pages name a font too, and size
    # it: the syntax highlighting asks for one for the code it colors.
    return [compress_font_sizes(simplify_font_families(text))
            for text in blocks]


def read_text(path):
    with open(path, encoding='utf-8') as a_file:
        return a_file.read()


def clean_inline_style(style):
    # A wiki template asks for a font and a size in the `style` attribute it
    # writes, and no rule of ours reaches into one, so what the two passes
    # below do to the stylesheets has to be done here as well.
    #
    # For the sizes it is not a tidiness: the scale only comes out right if
    # every declared proportion is compressed, since what that buys us is
    # that compressing each step of a cascade by an exponent compresses the
    # size at the end of it by the same exponent.  A `0.7em` left alone in a
    # `style` attribute is a step that was not compressed, and everything
    # under it is smaller than the rest of the page by that much.
    return compress_font_sizes(simplify_font_families(style))


# MediaWiki stamps a cache-busting query onto the images its skin draws on,
# and the copy of the site came down with the `?` percent-encoded, which
# makes it part of the file name rather than a query.  Nothing renamed the
# files to match, so every one of those is a broken reference.
CSS_URL_QUERY_RE = re.compile(r'(url\([^)]*?)%3[Ff][^)\'"]*')


def clean_site_css(text):
    text = CSS_URL_QUERY_RE.sub(r'\1', text)
    return compress_font_sizes(simplify_font_families(text))


# A `font-family` is worth exactly its first name.  litehtml hands the whole
# list to the help viewer, and the viewer hands it to `QFont::setFamilies`,
# but that list is for glyph coverage and not for choosing a face: Qt
# resolves the first family and, when it is not installed, substitutes its
# own default rather than trying the next one.  cppreference names DejaVu
# first throughout, which hardly anyone outside Linux has, so every code
# sample on every page came out in a proportional font.
#
# The names we can count on are the generic ones, which qlitehtml answers
# with faces of its own (`container_qpainter.cpp`, `create_font`).  So a
# stack is cut down to the first generic in it, and whatever stood in front
# is dropped: it would only decide the outcome on the machines that happen
# to have it, and lose the font everywhere else.
GENERIC_FAMILIES = ('monospace', 'serif', 'sans-serif', 'cursive', 'fantasy')

# qlitehtml answers `sans-serif` with Arial outright, whatever font the
# reader chose for the help pane, so a stack that comes down to it asks for
# `inherit` instead: at the root that is the font they chose, and further in
# it is whatever the text around it is set in.
#
# What it must not do is say nothing at all.  A proportional stack is
# usually there to take an element back out of a monospace one it would
# otherwise inherit -- `.t-dsc-member-nobold-div` sits on the same element
# as the `.t-dsc-member-div` rule that sets the member names in monospace --
# and a declaration that is simply gone loses that argument.
BODY_GENERIC = 'sans-serif'
INHERIT = 'inherit'

# `@font-face` names the face it defines rather than asking for one.  It is
# inert here -- no help viewer loads a font off a stylesheet, which is the
# other half of why DejaVu never resolves -- but rewriting it would be
# nonsense, so it is passed over whole.
FONT_FACE_RE = re.compile(r'@font-face\s*\{[^}]*\}')

FONT_FAMILY_RE = re.compile(r'font-family\s*:([^;}]*)')


def resolvable_family(value):
    for name in value.split(','):
        name = name.strip().strip('\'"').lower()
        if name in GENERIC_FAMILIES:
            return name
    return None


def simplify_font_family(match):
    value = match.group(1)
    # whatever separated the declaration from the next one, kept as it was
    trailing = value[len(value.rstrip()):]

    important = '!important' in value.replace(' ', '')
    family = resolvable_family(value.split('!')[0])

    if family is None or family == BODY_GENERIC:
        family = INHERIT

    return 'font-family: %s%s%s' % (
        family, ' !important' if important else '', trailing)


def outside_font_face(text, rewrite):
    parts = []
    position = 0

    for match in FONT_FACE_RE.finditer(text):
        parts.append(rewrite(text[position:match.start()]))
        parts.append(match.group(0))
        position = match.end()

    parts.append(rewrite(text[position:]))
    return ''.join(parts)


def simplify_font_families(text):
    return outside_font_face(
        text, lambda part: FONT_FAMILY_RE.sub(simplify_font_family, part))


# -- type sizes ------------------------------------------------------------

# The site is written against a browser's 16px default; a help viewer starts
# from the font the reader chose for the pane, which is 14px in Qt Creator
# until they say otherwise.  So every proportion the site asks for is taken
# of a smaller root, and a page that is mostly `0.8em` of it comes out too
# small to read -- while the proportions themselves run from 0.7em to 2em,
# which is a wider scale than a help pane wants.
#
# Pull every proportion towards the middle by raising it to a power.  The
# sizes of a cascade multiply, and a root distributes over a product, so
# compressing each declared proportion by the same exponent compresses the
# size every element ends up at by exactly that exponent -- without anyone
# having to work out what each element inherits.  The root is left alone, so
# the whole scale still follows the reader's Help font size.
#
# That leaves the content at 0.89 of whatever the reader chose and a page
# title at 1.26 of it -- 14px and 20px of a 16px Help font, 12.5px and 17.7px
# of a 14px one -- which is the scale Qt's own documentation reads at.
#
# This holds only if every declared proportion is compressed, the ones in a
# `style` attribute along with the ones in the sheets; see
# `clean_inline_style`.
FONT_SIZE_COMPRESSION = 0.5

FONT_SIZE_RE = re.compile(r'font-size\s*:([^;}]*)')

# Only the proportions are compressed.  What the site states outright is a
# handful of sizes on the MediaWiki furniture -- the edit box, the tooltip
# gadget, the site notice -- which no offline page shows, and `html, body`
# itself, where a length would be the root we are deliberately not moving.
RELATIVE_SIZE_RE = re.compile(
    r'^\s*([0-9]*\.?[0-9]+)\s*(em|rem|%)\s*(!important)?\s*$', re.IGNORECASE)


def compress_font_size(match):
    value = match.group(1)
    trailing = value[len(value.rstrip()):]

    size = RELATIVE_SIZE_RE.match(value)
    if size is None:
        return match.group(0)

    number, unit, important = size.groups()
    scale = 100.0 if unit == '%' else 1.0
    compressed = (float(number) / scale) ** FONT_SIZE_COMPRESSION

    return 'font-size: %s%s%s%s' % (
        format_number(compressed * scale), unit,
        ' ' + important if important else '', trailing)


def format_number(value):
    return '{0:.4g}'.format(value)


def compress_font_sizes(text):
    return outside_font_face(
        text, lambda part: FONT_SIZE_RE.sub(compress_font_size, part))


# -- the monospace correction ----------------------------------------------

# Courier, which is what a help viewer gives us for `monospace`, draws
# larger than the proportional face beside it at the same size, so a type
# name in the middle of a sentence stands up out of the line.  Ask for less
# of it, as GitHub and others do for the same reason.
MONOSPACE_FONT_SIZE = 85

# The correction belongs to the face, not to the text, so it is taken once
# where the monospace starts and not again inside it.  A `<pre>` inside a
# highlighted block inside a monospace cell is three deep, and on a sample
# of 400 pages every single one nests somewhere, so saying `85%` on each of
# these selectors would compound to 61%.  There is no way to ask CSS for
# "unless you are already inside one", so the pairs are written out: every
# monospace selector under every other goes back to the size it inherits.
MONOSPACE_RESET_SIZE = 100


def collect_font_families(rules, families, sized):
    # `families` maps a selector to the family its last `font-family`
    # declaration asks for, in the order the selectors first appear; `sized`
    # gathers the selectors the sheets give a `font-size` of their own.
    for rule in rules:
        if rule.typeString == 'MEDIA_RULE':
            if 'print' not in rule.media.mediaText:
                collect_font_families(rule, families, sized)
            continue

        if rule.typeString != 'STYLE_RULE':
            continue

        family = rule.style.getPropertyValue('font-family')

        for selector in rule.selectorList:
            text = selector.selectorText
            if rule.style.getPropertyValue('font-size'):
                sized.add(text)
            if family:
                families[text] = resolvable_family(family)


def font_selectors(*css_texts):
    # The selectors that put an element into monospace and the ones that take
    # it back out, in the order the stylesheets state them.  A selector is
    # judged by the last family it is given, since that is the one it ends up
    # with: `code` is named monospace by three sheets in a row and counts
    # once, and a selector set in monospace and then reset is proportional.
    silence_cssutils()
    families = {}
    sized = set()

    for css_text in css_texts:
        collect_font_families(cssutils.parseString(css_text, validate=False),
                              families, sized)

    monospace = [selector for selector, family in families.items()
                 if family == 'monospace']

    # A selector the sheets size themselves is left out of the reset: the
    # correction is about the face an element is set in, and overriding a
    # size the site asked for outright is not ours to do.  That is what keeps
    # `html` and `body` out of it.
    proportional = [selector for selector, family in families.items()
                    if family != 'monospace' and selector not in sized]

    return monospace, proportional


def monospace_size_rules(monospace, proportional=()):
    if not monospace:
        return ''

    # The correction is taken once where the monospace starts, so a monospace
    # selector inside another goes back to the size it inherits.  So does a
    # selector that is set proportionally: it draws in the viewer's own face
    # whether it is matched by a monospace rule as well -- the member names
    # of the declaration tables are, their `.t-dsc-member-nobold-div` rule
    # sitting on the same element as the `.t-dsc-member-div` one -- or simply
    # sits inside one, and neither is a reason to shrink it.
    reset = ['%s %s' % (outer, inner)
             for outer in monospace for inner in monospace]
    reset += list(proportional)

    return ('%s {\n    font-size: %d%%;\n}\n\n%s {\n    font-size: %d%%;\n}\n'
            % (',\n'.join(monospace), MONOSPACE_FONT_SIZE,
               ',\n'.join(reset), MONOSPACE_RESET_SIZE))


def section(title, body, media=None):
    body = body.strip()
    if media is not None:
        body = '@media %s {\n%s\n}' % (media, body)
    return '\n/* ---- %s ---- */\n\n%s\n' % (title, body)


def build_stylesheets(site_css, page_css, classes):
    # `site_css` are cppreference's own stylesheets in cascade order, and
    # `page_css` the <style> blocks lifted out of the pages, which the pages
    # carried after them.  `classes` name the colors found in the `style`
    # attributes that survive in the HTML.
    page_css = clean_page_css(page_css)
    shared = []

    for name, text in zip(SITE_CSS_NAMES, site_css):
        shared.append(section(name, text))
    if page_css:
        shared.append(section('lifted out of the pages',
                              '\n'.join(page_css)))

    sheets = site_css + list(page_css)

    shared.append(section('monospace, which draws large for its size',
                          monospace_size_rules(*font_selectors(*sheets))))

    shared.append(section(VIEWER_CSS, read_asset(VIEWER_CSS)))

    dark = list(shared)
    derived = dark_stylesheet_rules(*sheets)
    dark.append(section('the colors above, mapped for a dark page', derived))
    dark.append(section(DARK_BASE_CSS, read_asset(DARK_BASE_CSS),
                        media=DARK_MEDIA))

    rules = dark_class_rules(classes)
    if rules:
        dark.append(section('the colors the pages carry inline', rules))

    return LIGHT_HEADER + ''.join(shared), DARK_HEADER + ''.join(dark)


def write_stylesheets(directory, site_css, page_css, classes):
    os.makedirs(directory, exist_ok=True)

    light, dark = build_stylesheets(site_css, page_css, classes)

    for name in LIGHT_CSS_NAMES:
        write_text(os.path.join(directory, name), light)
    write_text(os.path.join(directory, DARK_CSS_NAME), dark)


def write_text(path, text):
    with open(path, 'w', encoding='utf-8') as a_file:
        a_file.write(text)


CSS_URL_RE = re.compile(r'url\(\s*[\'"]?([^\'")]+)')

IMAGE_SUFFIXES = ('.gif', '.ico', '.jpeg', '.jpg', '.png', '.svg', '.webp')


def referenced_images(site_css, source_root):
    # The images the site stylesheet draws on -- the tabs of the navigation
    # bar, the bullets of the lists.  Their URLs are relative to the
    # stylesheet, which ends up in the same directory as the one it came
    # from, so they go on resolving as they are.
    directory = os.path.join(source_root, CSS_DIR)
    images = set()

    for text in site_css:
        for url in CSS_URL_RE.findall(text):
            url = url.split('?')[0].split('#')[0]
            if '://' in url or not url.lower().endswith(IMAGE_SUFFIXES):
                continue
            images.add(os.path.normpath(os.path.join(directory, url)))

    return images


def stylesheet_href(css_dir, html_path):
    # The link each page carries, relative to the page itself.
    rel_path = os.path.relpath(css_dir, os.path.dirname(html_path))
    return os.path.join(rel_path, LINKED_CSS_NAME).replace(os.sep, '/')
