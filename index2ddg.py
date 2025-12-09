#!/usr/bin/env python3
'''
    Copyright (C) 2013  Povilas Kanapickas <povilas@radix.lt>

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

import argparse
import fnmatch
import os
import re
import sys

import lxml.etree as e
from lxml import html

from build_link_map import build_link_map
from ddg_parse_html import DdgException
from ddg_parse_html import get_declarations
from ddg_parse_html import get_short_description
from index_transform.common import IndexTransform

# Entry types
# a class or struct
ITEM_TYPE_CLASS = 1

# a member function or free function
ITEM_TYPE_FUNCTION = 2

# a constructor
ITEM_TYPE_CONSTRUCTOR = 3

# a constructor that is described in the same page as the class
ITEM_TYPE_CONSTRUCTOR_INLINEMEM = 4

# a destructor
ITEM_TYPE_DESTRUCTOR = 5

# a destructor that is described in the same page as the class
ITEM_TYPE_DESTRUCTOR_INLINEMEM = 6

# a member function that is described in the same page as the class
ITEM_TYPE_FUNCTION_INLINEMEM = 7

# an enum
ITEM_TYPE_ENUM = 8

# a value of an enum
ITEM_TYPE_ENUM_CONST = 9

# a variable
ITEM_TYPE_VARIABLE = 10

# a member variable that is described in the same page as the containing class
ITEM_TYPE_VARIABLE_INLINEMEM = 11


def get_item_type(el):
    if (el.tag == 'const' and el.getparent().tag == 'enum' and
            el.get('link') == '.'):
        return ITEM_TYPE_ENUM_CONST
    if el.tag == 'function':
        if el.get('link') == '.':
            return ITEM_TYPE_FUNCTION_INLINEMEM
        return ITEM_TYPE_FUNCTION
    if el.tag == 'variable':
        if el.get('link') == '.':
            return ITEM_TYPE_VARIABLE_INLINEMEM
        return ITEM_TYPE_VARIABLE
    if el.tag == 'constructor':
        if el.get('link') == '.':
            return ITEM_TYPE_CONSTRUCTOR_INLINEMEM
        return ITEM_TYPE_CONSTRUCTOR
    if el.tag == 'destructor':
        if el.get('link') == '.':
            return ITEM_TYPE_DESTRUCTOR_INLINEMEM
        return ITEM_TYPE_DESTRUCTOR
    if el.tag == 'class':
        return ITEM_TYPE_CLASS
    if el.tag == 'enum':
        return ITEM_TYPE_ENUM
    return None  # not recognized


class DDGDebug:

    def __init__(self, enabled=False, ident_match=None,
                 debug_abstracts_path=None):
        self.enabled = enabled
        self.ident_match = ident_match
        self.stat_line_nums = []
        self.debug_abstracts_file = sys.stdout
        if debug_abstracts_path is not None:
            self.debug_abstracts_file = \
                open(debug_abstracts_path, 'w', encoding='utf-8')

    # track the statistics of number of lines used by the entries
    def submit_line_num(self, line_num):
        while len(self.stat_line_nums) <= line_num:
            self.stat_line_nums.append(0)
        self.stat_line_nums[line_num] += 1

    def should_skip_ident(self, ident):
        if self.ident_match is None:
            return False

        if isinstance(ident, list):
            for i in ident:
                if self.ident_match in i:
                    return False
        else:
            if self.ident_match in ident:
                return False
        return True


class Index2DuckDuckGoList(IndexTransform):

    def __init__(self, ident_map):
        self.ident_map = ident_map
        super().__init__(ignore_typedefs=True)

    def process_item_hook(self, el, full_name, full_link):

        item_type = get_item_type(el)
        if item_type:
            if full_link in self.ident_map:
                self.ident_map[full_link][full_name] = item_type
            else:
                self.ident_map[full_link] = {full_name: item_type}
        IndexTransform.process_item_hook(self, el, full_name, full_link)


def get_html_files(root):
    files = []
    for dir, _, filenames in os.walk(root):
        for filename in fnmatch.filter(filenames, '*.html'):
            files.append(os.path.join(dir, filename))
    return files


def get_processing_instructions(ident_map, link_map):
    proc_ins = {}

    for link in ident_map:
        if link in link_map.mapping:
            fn = link_map.mapping[link]
            if fn not in proc_ins:
                proc_ins[fn] = {'fn': fn, 'link': link, 'idents': {}}
            for ident in ident_map[link]:
                proc_ins[fn]['idents'][ident] = {'ident': ident,
                                                 'type': ident_map[link][ident]}
    return proc_ins


# process the files

# returns the unqualified name of an identifier
def get_unqualified_name(ident):
    if ident.find('(') != -1:
        ident = re.sub(r'\(.*?\)', '', ident)
    if ident.find('<') != -1:
        ident = re.sub(r'\<.*?\>', '', ident)
    qpos = ident.rfind('::')
    if qpos != -1:
        ident = ident[qpos+2:]
    return ident


# returns the version number common to all declarations. Returns none if two
# declarations have different version numbers or if no version number is
# provided
def get_version(decls):
    rv = None
    for code, v in decls:
        if v:
            if rv is None:
                rv = v
            elif v != rv:
                return None
    return rv


def build_abstract(decls, desc, max_code_lines, split_code_lines,
                   debug=DDGDebug()):

    limited = False
    code_snippets = []

    for i, (code, ver) in enumerate(decls):
        code = code.strip()
        code = code.replace('<', '&lt;').replace('>', '&gt;')
        code_num_lines = code.count('\n') + 1

        # limit the number of code snippets to be included so that total number
        # of lines is less than max_code_lines. The limit becomes active only
        # for the second and subsequent snippets.
        first = (i == 0)
        last = (i == len(decls)-1)

        if not first:
            if last:
                if code_num_lines > max_code_lines:
                    limited = True
                    break
            else:
                if code_num_lines > max_code_lines - 1:
                    # -1 because we need to take into account
                    # < omitted declarations > message
                    limited = True
                    break

        code_snippets.append(code)
        max_code_lines -= code_num_lines

    if split_code_lines:
        code_snippets = ['<pre><code>' + s + '</code></pre>'
                         for s in code_snippets]
        code_text = ''.join(code_snippets)
    else:
        code_text = '<pre><code>' + '\n\n'.join(code_snippets) + '</code></pre>'

    if limited:
        code_text += \
            '\n<p><em>Additional declarations have been omitted</em></p>'

    # count the number of lines used
    num_lines = code_text.count('\n') + 1  # last line has no newline after it
    if len(desc) > 110:
        num_lines += 2
    else:
        num_lines += 1

    debug.submit_line_num(num_lines)

    result_lines = [
        '<section class="prog__container">',
        '<p>' + desc + '</p>',
        code_text,
        '</section>'
    ]
    result_text = '\n'.join(result_lines)

    if debug.enabled and num_lines >= 10:
        print("# error : large number of lines: ")
        print("# BEGIN ======")
        print(result_text)
        print("# END ========")
    return result_text


def build_redirects(redirects, item_ident, item_type):
    ''' Outputs additional redirects for an identifier.

        Firstly, we replace '::' with spaces. Then we add two redirects: one
        with unchanged text and another with '_' replaced with spaces. We strip
        one level of namespace/class qualification and repeat the process with
        the remaining text.

        For constructors and destructors, we strip the function name and apply
        the abovementioned algorithm, the only difference being that we append
        (or prepend) 'constructor' or 'destructor' to the title of the redirect
        respectively.

        Each redirect has a 'priority', which is defined by the number of
        stripped namespace/class qualifications from the entry that produced
        the redirect. This is used to remove duplicate redirects. For each
        group of duplicate redirects, we find the redirect with the highest
        priority (i.e. lowest number of qualifications stripped) and remove all
        other redirects. If the number of highest-priority redirects is more
        than one, then we remove all redirects from the group altogether.

        We don't add any redirects to specializations, overloads or operators.
    '''
    ''' array of dict { 'title' -> redirect title,
                        'target' -> redirect target,
                        'priority' -> redirect priority as int
                      }
    '''

    for ch in ['(', ')', '<', '>', 'operator']:
        if ch in item_ident:
            return

    target = item_ident
    parts = item_ident.split('::')

    # -----
    def do_parts(redirects, parts, prepend='', append=''):
        if prepend != '':
            prepend = prepend + ' '
        if append != '':
            append = ' ' + append

        p = 0
        while p < len(parts):
            redir1 = prepend + ' '.join(parts[p:]) + append
            redir2 = prepend + \
                ' '.join(x.replace('_', ' ') for x in parts[p:]) + append

            redir1 = redir1.replace('  ', ' ').replace('  ', ' ')
            redir2 = redir2.replace('  ', ' ').replace('  ', ' ')

            redirects.append({'title': redir1, 'target': target,
                              'priority': p})
            if redir1 != redir2:
                redirects.append({'title': redir2, 'target': target,
                                  'priority': p})
            p += 1
    # -----

    if item_type in [ITEM_TYPE_CLASS,
                     ITEM_TYPE_FUNCTION,
                     ITEM_TYPE_FUNCTION_INLINEMEM,
                     ITEM_TYPE_VARIABLE,
                     ITEM_TYPE_VARIABLE_INLINEMEM,
                     ITEM_TYPE_ENUM,
                     ITEM_TYPE_ENUM_CONST]:
        do_parts(redirects, parts)

    elif item_type in [ITEM_TYPE_CONSTRUCTOR,
                       ITEM_TYPE_CONSTRUCTOR_INLINEMEM]:
        parts.pop()
        do_parts(redirects, parts, prepend='constructor')
        do_parts(redirects, parts, append='constructor')
    elif item_type in [ITEM_TYPE_DESTRUCTOR,
                       ITEM_TYPE_DESTRUCTOR_INLINEMEM]:
        parts.pop()
        do_parts(redirects, parts, prepend='destructor')
        do_parts(redirects, parts, append='destructor')
    else:
        pass    # should not be here


def output_redirects(out, redirects):

    # convert to a convenient data structure
    # dict { title -> dict { priority -> list ( targets ) } }
    redir_map = {}

    for r in redirects:
        title = r['title']
        target = r['target']
        priority = r['priority']

        if title not in redir_map:
            redir_map[title] = {}
        if priority not in redir_map[title]:
            redir_map[title][priority] = []

        redir_map[title][priority].append(target)

    # get non-duplicate redirects
    ok_redirects = []  # list ( dict { 'title' : title, 'target' : target  })

    for title in redir_map:
        # priority decreases with increasing values
        highest_prio = min(redir_map[title])
        if len(redir_map[title][highest_prio]) == 1:
            # not duplicate
            target = redir_map[title][highest_prio][0]
            ok_redirects.append({'title': title, 'target': target})

    # sort the redirects
    ok_redirects = sorted(ok_redirects, key=lambda x: x['title'])

    # output
    for r in ok_redirects:
        # title
        line = r['title'] + '\t'
        # type
        line += 'R\t'
        # redirect
        line += r['target'] + '\t'
        # otheruses, categories, references, see_also, further_reading,
        # external links, disambiguation, images, abstract, source url
        line += '\t\t\t\t\t\t\t\t\t\t\n'
        out.write(line)


def process_identifier(out, redirects, root, link, item_ident, item_type,
                       opts, debug=DDGDebug()):
    # get the name by extracting the unqualified identifier
    name = get_unqualified_name(item_ident)
    debug_verbose = False
    if debug.enabled and debug.ident_match is not None:
        debug_verbose = True

    try:
        if item_type == ITEM_TYPE_CLASS:
            decls = get_declarations(root, name)
            desc = get_short_description(root, get_version(decls),
                                         opts.max_sentences,
                                         opts.max_characters,
                                         opts.max_paren_chars,
                                         debug=debug_verbose)
            abstract = build_abstract(decls, desc, opts.max_code_lines,
                                      opts.split_code_snippets, debug=debug)

        elif item_type in [ITEM_TYPE_FUNCTION,
                           ITEM_TYPE_CONSTRUCTOR,
                           ITEM_TYPE_DESTRUCTOR]:
            decls = get_declarations(root, name)
            desc = get_short_description(root, get_version(decls),
                                         opts.max_sentences,
                                         opts.max_characters,
                                         opts.max_paren_chars,
                                         debug=debug_verbose)
            abstract = build_abstract(decls, desc, opts.max_code_lines,
                                      opts.split_code_snippets, debug=debug)

        elif item_type in [ITEM_TYPE_FUNCTION_INLINEMEM,
                           ITEM_TYPE_CONSTRUCTOR_INLINEMEM,
                           ITEM_TYPE_DESTRUCTOR_INLINEMEM]:
            ''' Implementation notes:
                * the declarations are possibly versioned
                * declaration is selected from the member table
                * the member table is found according to the identifier
                  (last part after :: is enough, hopefully)
            '''
            raise DdgException("INLINEMEM")  # not implemented

        elif item_type in [ITEM_TYPE_VARIABLE,
                           ITEM_TYPE_VARIABLE_INLINEMEM,
                           ITEM_TYPE_ENUM]:
            ''' Implementation notes:
                * the declarations are possibly versioned
            '''
            raise DdgException("ENUM")      # not implemented

        elif item_type == ITEM_TYPE_ENUM_CONST:
            ''' Implementation notes:
                * the abstract will come from the const -> definition table,
                  which is always put before the first heading.
                * the declaration will come from the dcl template. We need
                  to split the content at ';' and ',', then search for the
                  name of the enum. If we find duplicates, signal an error.
            '''
            raise DdgException("ENUM_CONST")    # not implemented

        if debug.enabled:
            debug.debug_abstracts_file.write("--------------\n")
            debug.debug_abstracts_file.write(item_ident + '\n')
            debug.debug_abstracts_file.write(abstract + '\n')

        # title
        line = item_ident + '\t'
        # type
        line += 'A\t'
        # redirect, otheruses, categories, references, see_also,
        # further_reading, external links, disambiguation, images
        line += '\t\t\t\t\t\t\t\t\t'
        # abstract
        abstract = abstract.replace('\n', '\\n')
        line += abstract + '\t'
        # source url
        line += 'http://en.cppreference.com/w/' + link + '\n'
        out.write(line)

        build_redirects(redirects, item_ident, item_type)

    except DdgException as err:
        if debug.enabled:
            line = '# error ({0}): {1}: {2}\n'.format(str(err), link,
                                                      item_ident)
            out.write(line)


def main():
    parser = argparse.ArgumentParser(prog='index2ddg.py')

    parser.add_argument(
        'index', type=str,
        help='The path to the XML index containing identifier data')

    parser.add_argument(
        'reference', type=str,
        help='The path to the downloaded reference (reference directory in '
             'the downloaded archive)')

    parser.add_argument(
        'output', type=str,
        help='The path to destination output.txt file')

    parser.add_argument(
        '--split_code_snippets', action='store_true', default=False,
        help='Puts each declaration into a separate code snippet.')

    parser.add_argument(
        '--max_code_lines', type=int, default=6,
        help='Maximum number of lines of code to show in abstract')

    parser.add_argument(
        '--max_sentences', type=int, default=1,
        help='Maximum number of sentences to use for the description')

    parser.add_argument(
        '--max_characters', type=int, default=200,
        help='Maximum number of characters to use for the description')

    parser.add_argument(
        '--max_paren_chars', type=int, default=40,
        help='Maximum size of parenthesized text in the description. '
             'Parenthesized chunks longer than that is removed, unless they '
             'are within <code>, <b> or <i> tags')

    parser.add_argument(
        '--debug', action='store_true', default=False,
        help='Enables debug mode.')

    parser.add_argument(
        '--debug_ident', type=str, default=None,
        help='Processes only the identifiers that match debug_ident')

    parser.add_argument(
        '--debug_abstracts_path', type=str, default=None,
        help='Path to print the abstracts before newline stripping occurs')
    args = parser.parse_args()

    # If a the second argument is 'debug', the program switches to debug mode
    # and prints everything to stdout. If the third argument is provided, the
    # program processes only the identifiers that match the provided string

    debug = DDGDebug(args.debug, args.debug_ident, args.debug_abstracts_path)

    index_file = args.index
    output_file = args.output

    # a map that stores information about location and type of identifiers
    # it's two level map: full_link maps to a dict that has full_name map to
    # ITEM_TYPE_* value
    ident_map = {}

    # get a list of pages to analyze
    tr = Index2DuckDuckGoList(ident_map)
    tr.transform_file(index_file)

    # get a mapping between titles and pages
    # linkmap = dict { title -> filename }
    link_map = build_link_map(args.reference)

    # create a list of processing instructions for each page
    proc_ins = get_processing_instructions(ident_map, link_map)

    # sort proc_ins to produce ordered output.txt
    proc_ins = list(proc_ins.values())
    proc_ins = sorted(proc_ins, key=lambda x: x['link'])

    for page in proc_ins:
        idents = page['idents']
        idents = list(idents.values())
        idents = sorted(idents, key=lambda x: x['ident'])
        page['idents'] = idents

    redirects = []

    out = open(output_file, 'w', encoding='utf-8')

    # i=1
    for page in proc_ins:
        idents = page['idents']
        link = page['link']
        fn = page['fn']

        if debug.should_skip_ident([i['ident'] for i in idents]):
            continue

        # print(str(i) + '/' + str(len(proc_ins)) + ': ' + link)
        # i+=1

        root = e.parse(os.path.join(args.reference, fn),
                       parser=html.HTMLParser(encoding='utf-8'))

        for ident in idents:

            item_ident = ident['ident']
            item_type = ident['type']

            process_identifier(out, redirects, root, link, item_ident,
                               item_type, args, debug=debug)

    output_redirects(out, redirects)

    if debug.enabled:
        print('=============================')
        print('Numbers of lines used:')
        for i, l in enumerate(debug.stat_line_nums):
            print(str(i) + ': ' + str(l) + ' result(s)')


if __name__ == "__main__":
    main()
