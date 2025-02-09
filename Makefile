#   Copyright (C) 2011-2014  Povilas Kanapickas <povilas@radix.lt>
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

SHELL := /usr/bin/env bash

#Common prefixes

prefix = /usr
datarootdir = $(prefix)/share
docdir = $(datarootdir)/cppreference/doc
bookdir = $(datarootdir)/devhelp/books

qhelpgenerator = qhelpgenerator

#Version

VERSION=20250209

#STANDARD RULES

all: doc_html doc_devhelp doc_qch doc_doxygen

DISTFILES= \
		commands/                   \
		gadgets/                    \
		headers/                    \
		images/                     \
		index_transform/            \
		reference/                  \
		skins/                      \
		tests/                      \
		build_link_map.py           \
		ddg_parse_html.py           \
		devhelp2qch.py              \
		export.py                   \
		fix_devhelp-links.py        \
		index2autolinker.py         \
		index2browser.py            \
		index2ddg.py                \
		index2devhelp.py            \
		index2doxygen-tag.py        \
		index2highlight.py          \
		index2search.py             \
		index-chapters-c.xml        \
		index-chapters-cpp.xml      \
		index-cpp-search-app.txt    \
		index-functions.README      \
		index-functions-c.xml       \
		index-functions-cpp.xml     \
		link_map.py                 \
		preprocess.py               \
		preprocess-css.css          \
		preprocess_qch.py           \
		test.sh                     \
		xml_utils.py                \
		requirements.txt            \
		requirements-ci.txt         \
		Makefile                    \
		LICENSE                     \
		README.md

CLEANFILES= \
		output

TAR_FORMAT := gz
TAR_OPTION := z
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
	TAR_FORMAT := xz
	TAR_OPTION := J
endif

clean:
	rm -rf $(CLEANFILES)

check:

dist: clean
	mkdir -p "cppreference-doc-$(VERSION)"
	cp -r $(DISTFILES) "cppreference-doc-$(VERSION)"
	tar c$(TAR_OPTION)f "cppreference-doc-$(VERSION).tar.$(TAR_FORMAT)" "cppreference-doc-$(VERSION)"
	rm -rf "cppreference-doc-$(VERSION)"

install: install_html install_qch install_devhelp install_doxygen

install_html: doc_html
	pushd "output/reference" > /dev/null; \
	find . -type f \
		-exec install -DT -m 644 '{}' "$(DESTDIR)$(docdir)/html/{}" \; ; \
	popd > /dev/null

install_devhelp: doc_devhelp
	install -DT -m 644 "output/cppreference-doc-en-c.devhelp2" \
		"$(DESTDIR)$(bookdir)/cppreference-doc-en-c/cppreference-doc-en-c.devhelp2"
	install -DT -m 644 "output/cppreference-doc-en-cpp.devhelp2" \
		"$(DESTDIR)$(bookdir)/cppreference-doc-en-cpp/cppreference-doc-en-cpp.devhelp2"

install_qch: doc_qch
	install -DT -m 644 "output/cppreference-doc-en-cpp.qch" \
		"$(DESTDIR)$(docdir)/qch/cppreference-doc-en-cpp.qch"

install_doxygen: doc_doxygen
	install -DT -m 644 "output/cppreference-doxygen-local.tag.xml" \
		"$(DESTDIR)$(bookdir)/cppreference-doxygen-local.tag.xml"
	install -DT -m 644 "output/cppreference-doxygen-web.tag.xml" \
		"$(DESTDIR)$(bookdir)/cppreference-doxygen-web.tag.xml"

uninstall:
	rm -rf "$(DESTDIR)$(docdir)"
	rm -rf "$(DESTDIR)$(bookdir)"

release: all
	rm -rf release
	mkdir -p release

	# zip the distributable
	mkdir -p "cppreference-doc-$(VERSION)"
	cp -r $(DISTFILES) "cppreference-doc-$(VERSION)"
	tar c$(TAR_OPTION)f "release/cppreference-doc-$(VERSION).tar.$(TAR_FORMAT)" "cppreference-doc-$(VERSION)"
	zip -qr "release/cppreference-doc-$(VERSION).zip" "cppreference-doc-$(VERSION)"
	rm -rf "cppreference-doc-$(VERSION)"

	# zip the html output
	pushd "output"; \
	tar c$(TAR_OPTION)f "../release/html-book-$(VERSION).tar.$(TAR_FORMAT)" "reference" \
		"cppreference-doxygen-local.tag.xml" "cppreference-doxygen-web.tag.xml" ; \
	zip -qr "../release/html-book-$(VERSION).zip" "reference" \
		"cppreference-doxygen-local.tag.xml" "cppreference-doxygen-web.tag.xml" ; \
	popd

	# zip qch
	pushd "output"; \
	tar c$(TAR_OPTION)f "../release/qch-book-$(VERSION).tar.$(TAR_FORMAT)" "cppreference-doc-en-cpp.qch"; \
	zip -qr "../release/qch-book-$(VERSION).zip" "cppreference-doc-en-cpp.qch"; \
	popd

#WORKER RULES
doc_html: output/reference

doc_devhelp: output/cppreference-doc-en-c.devhelp2 output/cppreference-doc-en-cpp.devhelp2

doc_qch: output/cppreference-doc-en-cpp.qch

doc_doxygen: output/cppreference-doxygen-web.tag.xml output/cppreference-doxygen-local.tag.xml

#builds the title<->location map
output/link-map.xml: output/reference
	./build_link_map.py

#build the .devhelp2 index
output/cppreference-doc-en-c.devhelp2: output/reference output/link-map.xml
	./index2devhelp.py $(docdir)/html index-chapters-c.xml  \
		"C Standard Library reference" "cppreference-doc-en-c" "c" \
		index-functions-c.xml "output/devhelp-index-c.xml"
	./fix_devhelp-links.py "output/devhelp-index-c.xml"  \
		"output/cppreference-doc-en-c.devhelp2"

output/cppreference-doc-en-cpp.devhelp2: output/reference output/link-map.xml
	./index2devhelp.py $(docdir)/html index-chapters-cpp.xml  \
		"C++ Standard Library reference" "cppreference-doc-en-cpp" "cpp" \
		index-functions-cpp.xml "output/devhelp-index-cpp.xml"
	./fix_devhelp-links.py "output/devhelp-index-cpp.xml" \
		"output/cppreference-doc-en-cpp.devhelp2"

#build the .qch (QT help) file
output/cppreference-doc-en-cpp.qch: output/qch-help-project-cpp.xml
	#qhelpgenerator only works if the project file is in the same directory as the documentation
	cp "output/qch-help-project-cpp.xml" "output/reference_cssless/qch.qhp"

	pushd "output/reference_cssless" > /dev/null; \
	$(qhelpgenerator) "qch.qhp" -o "../cppreference-doc-en-cpp.qch"; \
	popd > /dev/null

	rm -f "output/reference_cssless/qch.qhp"

output/qch-help-project-cpp.xml: output/cppreference-doc-en-cpp.devhelp2 output/reference_cssless
	#build the file list
	echo "<?xml version=\"1.0\" encoding=\"UTF-8\"?><files>" > "output/qch-files.xml"

	pushd "output/reference_cssless" > /dev/null; \
	find . -type f -not -iname "*.ttf" \
		-exec echo "<file>"'{}'"</file>" \; | LC_ALL=C sort >> "../qch-files.xml" ; \
	popd > /dev/null

	echo "</files>" >> "output/qch-files.xml"

	#create the project (copies the file list)
	./devhelp2qch.py --src=output/cppreference-doc-en-cpp.devhelp2 \
		--dst=output/qch-help-project-cpp.xml \
		--virtual_folder=cpp --file_list=output/qch-files.xml

# build doxygen tag file
output/cppreference-doxygen-local.tag.xml: output/reference output/link-map.xml
	./index2doxygen-tag.py "output/link-map.xml" \
		"index-functions-cpp.xml" \
		"index-chapters-cpp.xml" \
		"output/cppreference-doxygen-local.tag.xml"

output/cppreference-doxygen-web.tag.xml: output/reference output/link-map.xml
	./index2doxygen-tag.py web \
		"index-functions-cpp.xml" \
		"index-chapters-cpp.xml" \
		"output/cppreference-doxygen-web.tag.xml"

#create preprocessed archive
output/reference:
	mkdir -p output
	./preprocess.py --src reference --dst output/reference

output/reference_cssless: output/reference
	./preprocess_qch.py --src output/reference --dst output/reference_cssless

# create indexes for the wiki
indexes:
	mkdir -p output/indexes
	./index2highlight.py index-functions-cpp.xml output/indexes/highlight-cpp
	./index2highlight.py index-functions-c.xml output/indexes/highlight-c
	./index2search.py index-functions-cpp.xml output/indexes/search-cpp
	./index2search.py index-functions-c.xml output/indexes/search-c
	cat index-cpp-search-app.txt >> output/indexes/search-cpp
	./index2autolinker.py index-functions-c.xml output/indexes/autolink-c
	./index2autolinker.py index-functions-cpp.xml output/indexes/autolink-cpp

#redownloads the source documentation directly from en.cppreference.com
source:
	rm -rf "reference"
	mkdir "reference"

	pushd "reference" > /dev/null; \
	regex=".*index\\.php.*|.*/Special:.*|.*/Talk:.*" \
	regex+="|.*/Help:.*|.*/File:.*|.*/Cppreference:.*" \
	regex+="|.*/WhatLinksHere:.*|.*/Template:.*|.*/Category:.*" \
	regex+="|.*action=.*|.*printable=.*|.*en.cppreference.com/book.*" ; \
	echo $$regex ; \
	wget --adjust-extension --page-requisites --convert-links \
		--force-directories --recursive --level=15 \
		--span-hosts --domains=en.cppreference.com,upload.cppreference.com \
		--reject-regex $$regex \
		--timeout=5 --tries=50 --no-verbose \
		--retry-connrefused --waitretry=10 --read-timeout=20 \
		https://en.cppreference.com/w/ ; \
	popd > /dev/null

	./export.py --url=https://en.cppreference.com/mwiki reference/cppreference-export-ns0,4,8,10.xml 0 4 8 10
