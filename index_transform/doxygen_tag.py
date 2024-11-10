'''
    Copyright (C) 2014  Povilas Kanapickas <povilas@radix.lt>
    Copyright (C) 2018  Monika Kairaityte <monika@kibit.lt>

    This file is part of cppreference-doc

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.
'''

from functools import total_ordering
import re

from index_transform.common import IndexTransform
from xml_utils import xml_escape


class ItemKind:
    VARIABLE = 0
    FUNCTION = 1
    CLASS = 2
    TYPEDEF = 3
    NAMESPACE = 4


@total_ordering
class Item:

    def __init__(self):
        self.name = ""
        self.full_name = ""
        self.kind = ItemKind.NAMESPACE
        self.link = ""
        self.members = {}

    def __eq__(self, other):
        return self.full_name == other.full_name

    def __lt__(self, other):
        return self.full_name < other.full_name


def split_full_name(full_name):
    if m := re.match(r"([^(]+)(\([^)]+\))", full_name):
        names = m.group(1).split('::')
        names[len(names)-1] += m.group(2)
        return names
    return full_name.split('::')


def add_to_map(ns_map, full_name, full_link, item_kind):
    names = split_full_name(full_name)
    parsed_names = []
    last_name = names.pop()  # i.e. unqualified name
    curr_item = ns_map

    for name in names:
        parsed_names.append(name)
        if name in curr_item.members:
            curr_item = curr_item.members[name]
            if curr_item.kind not in [ItemKind.CLASS, ItemKind.NAMESPACE]:
                print("ERROR: " + name + " in " + full_name +
                      " is not a class or namespace")
                return
        else:
            # we add inexistent intermediate elements as namespaces and convert
            # them to classes later when class definitions are encountered
            new_item = Item()
            new_item.name = name
            new_item.full_name = "::".join(parsed_names)
            new_item.kind = ItemKind.NAMESPACE

            curr_item.members[name] = new_item
            curr_item = new_item

    if last_name in curr_item.members:
        curr_item = curr_item.members[last_name]
        if (item_kind == ItemKind.CLASS and
                curr_item.kind in [ItemKind.CLASS, ItemKind.NAMESPACE]):

            # fix namespaces that are actually classes
            curr_item.kind = item_kind
            curr_item.link = full_link
        else:
            print("ERROR: Duplicate element: " + full_name)
    else:
        new_item = Item()
        new_item.full_name = full_name
        new_item.name = last_name
        new_item.link = full_link
        new_item.kind = item_kind
        curr_item.members[last_name] = new_item
        curr_item = new_item
    return


def print_members(out_f, link_map, curr_item):
    for item in sorted(curr_item.members.values()):
        if link_map:
            link = link_map.get_dest(item.link)
            if link is None and item.kind != ItemKind.NAMESPACE:
                print("WARN: " + item.full_name + " contains invalid link")
                link = '404'
        else:
            link = item.link

        print_member(out_f, item, link)


def print_member(out_f, item, link):
    if item.kind == ItemKind.VARIABLE:
        out_f.write(
            '    <member kind="variable">\n' +
            '      <type>T</type>\n' +
            '      <name>' + xml_escape(item.name) + '</name>\n' +
            '      <anchorfile>' + xml_escape(link) + '</anchorfile>\n' +
            '      <anchor></anchor>\n' +
            '      <arglist></arglist>\n' +
            '    </member>\n')
    elif item.kind == ItemKind.FUNCTION:
        out_f.write(
            '    <member kind="function">\n' +
            '      <type>T</type>\n' +
            '      <name>' + xml_escape(item.name) + '</name>\n' +
            '      <anchorfile>' + xml_escape(link) + '</anchorfile>\n' +
            '      <anchor></anchor>\n' +
            '      <arglist>(T... args)</arglist>\n' +
            '    </member>\n')
    elif item.kind == ItemKind.CLASS:
        out_f.write(
            '    <class kind="class">' + xml_escape(item.full_name) +
            '</class>\n')
    elif item.kind == ItemKind.NAMESPACE:
        out_f.write(
            '    <namespace>' + xml_escape(item.full_name) +
            '</namespace>\n')


def print_map_item(out_f, link_map, curr_item):
    item_kind_to_attr = {ItemKind.NAMESPACE: 'namespace',
                         ItemKind.CLASS: 'class'}
    if curr_item.kind not in item_kind_to_attr:
        print('ERROR: only namespaces and classes can have members')
        return

    out_f.write(
        '  <compound kind="' + item_kind_to_attr[curr_item.kind] + '">\n' +
        '    <name>' + xml_escape(curr_item.full_name) + '</name>\n' +
        '    <filename>' + xml_escape(curr_item.link) + '</filename>\n')
    print_members(out_f, link_map, curr_item)
    out_f.write('  </compound>\n')

    for item in sorted(curr_item.members.values()):
        if item.kind in [ItemKind.NAMESPACE, ItemKind.CLASS]:
            print_map_item(out_f, link_map, item)


def print_map(out_f, link_map, ns_map):
    for item in sorted(ns_map.members.values()):
        if item.kind in [ItemKind.NAMESPACE, ItemKind.CLASS]:
            print_map_item(out_f, link_map, item)
        elif item.kind in [ItemKind.FUNCTION, ItemKind.VARIABLE]:
            # Members in the global namespace
            print_member(out_f, item, item.link)
        else:
            print("WARN: " + item.full_name + " ignored")


class Index2DoxygenTag(IndexTransform):
    def __init__(self, ns_map):
        super().__init__()
        self.ns_map = ns_map

    def get_item_kind(self, el):
        tag_to_kind = {
            'const': None,
            'function': ItemKind.FUNCTION,
            'constructor': ItemKind.FUNCTION,
            'destructor': ItemKind.FUNCTION,
            'class': ItemKind.CLASS,
            'enum': 'enum',
            'typedef': ItemKind.CLASS,
            'specialization': None,
            'overload': None,
            'variable': ItemKind.VARIABLE,
        }

        if el.tag in tag_to_kind:
            return tag_to_kind[el.tag]
        return None

    def process_item_hook(self, el, full_name, full_link):
        item_kind = self.get_item_kind(el)
        if item_kind is not None:
            add_to_map(self.ns_map, full_name, full_link, item_kind)
        IndexTransform.process_item_hook(self, el, full_name, full_link)
