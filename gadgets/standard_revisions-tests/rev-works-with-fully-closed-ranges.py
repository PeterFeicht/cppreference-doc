'''
    Copyright (C) 2017-2018  Povilas Kanapickas <povilas@radix.lt>

    This file is part of cppreference.com

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.
'''

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoAlertPresentException
import unittest, time, re
from base import *

class RevWorksWithFullyClosedRanges(CppTestCase):
    def test_rev_works_with_fully_closed_ranges(self):
        driver = self.driver
        self.get_page("test-gadget-stdrev/rev-works-with-fully-closed-ranges")
        self.assert_text_in_body("since-cxx03-until-none")
        self.assert_text_in_body("since-cxx11-until-none")
        self.assert_text_in_body("since-cxx14-until-none")
        self.assert_text_in_body("since-cxx17-until-none")
        self.assert_text_in_body("since-cxx20-until-none")
        self.assert_text_in_body("since-cxx03-until-cxx11")
        self.assert_text_in_body("since-cxx03-until-cxx14")
        self.assert_text_in_body("since-cxx11-until-cxx14")
        self.assert_text_in_body("since-cxx03-until-cxx17")
        self.assert_text_in_body("since-cxx11-until-cxx17")
        self.assert_text_in_body("since-cxx14-until-cxx17")
        self.assert_text_in_body("since-cxx03-until-cxx20")
        self.assert_text_in_body("since-cxx11-until-cxx20")
        self.assert_text_in_body("since-cxx14-until-cxx20")
        self.assert_text_in_body("since-cxx17-until-cxx20")
        self.assert_text_in_body("since-none-until-cxx03")
        self.assert_text_in_body("since-none-until-cxx11")
        self.assert_text_in_body("since-none-until-cxx14")
        self.assert_text_in_body("since-none-until-cxx17")
        self.assert_text_in_body("since-none-until-cxx20")

        self.select_cxx98()
        self.assert_text_in_body("since-cxx03-until-none")
        self.assert_text_not_in_body("since-cxx11-until-none")
        self.assert_text_not_in_body("since-cxx14-until-none")
        self.assert_text_not_in_body("since-cxx17-until-none")
        self.assert_text_not_in_body("since-cxx20-until-none")
        self.assert_text_in_body("since-cxx03-until-cxx11")
        self.assert_text_in_body("since-cxx03-until-cxx14")
        self.assert_text_not_in_body("since-cxx11-until-cxx14")
        self.assert_text_in_body("since-cxx03-until-cxx17")
        self.assert_text_not_in_body("since-cxx11-until-cxx17")
        self.assert_text_not_in_body("since-cxx14-until-cxx17")
        self.assert_text_in_body("since-cxx03-until-cxx20")
        self.assert_text_not_in_body("since-cxx11-until-cxx20")
        self.assert_text_not_in_body("since-cxx14-until-cxx20")
        self.assert_text_not_in_body("since-cxx17-until-cxx20")
        self.assert_text_not_in_body("since-none-until-cxx03")
        self.assert_text_in_body("since-none-until-cxx11")
        self.assert_text_in_body("since-none-until-cxx14")
        self.assert_text_in_body("since-none-until-cxx17")
        self.assert_text_in_body("since-none-until-cxx20")

        self.select_cxx11()
        self.assert_text_in_body("since-cxx03-until-none")
        self.assert_text_in_body("since-cxx11-until-none")
        self.assert_text_not_in_body("since-cxx14-until-none")
        self.assert_text_not_in_body("since-cxx17-until-none")
        self.assert_text_not_in_body("since-cxx20-until-none")
        self.assert_text_not_in_body("since-cxx03-until-cxx11")
        self.assert_text_in_body("since-cxx03-until-cxx14")
        self.assert_text_in_body("since-cxx11-until-cxx14")
        self.assert_text_in_body("since-cxx03-until-cxx17")
        self.assert_text_in_body("since-cxx11-until-cxx17")
        self.assert_text_not_in_body("since-cxx14-until-cxx17")
        self.assert_text_in_body("since-cxx03-until-cxx20")
        self.assert_text_in_body("since-cxx11-until-cxx20")
        self.assert_text_not_in_body("since-cxx14-until-cxx20")
        self.assert_text_not_in_body("since-cxx17-until-cxx20")
        self.assert_text_not_in_body("since-none-until-cxx03")
        self.assert_text_not_in_body("since-none-until-cxx11")
        self.assert_text_in_body("since-none-until-cxx14")
        self.assert_text_in_body("since-none-until-cxx17")
        self.assert_text_in_body("since-none-until-cxx20")

        self.select_cxx14()
        self.assert_text_in_body("since-cxx03-until-none")
        self.assert_text_in_body("since-cxx11-until-none")
        self.assert_text_in_body("since-cxx14-until-none")
        self.assert_text_not_in_body("since-cxx17-until-none")
        self.assert_text_not_in_body("since-cxx20-until-none")
        self.assert_text_not_in_body("since-cxx03-until-cxx11")
        self.assert_text_not_in_body("since-cxx03-until-cxx14")
        self.assert_text_not_in_body("since-cxx11-until-cxx14")
        self.assert_text_in_body("since-cxx03-until-cxx17")
        self.assert_text_in_body("since-cxx11-until-cxx17")
        self.assert_text_in_body("since-cxx14-until-cxx17")
        self.assert_text_in_body("since-cxx03-until-cxx20")
        self.assert_text_in_body("since-cxx11-until-cxx20")
        self.assert_text_in_body("since-cxx14-until-cxx20")
        self.assert_text_not_in_body("since-cxx17-until-cxx20")
        self.assert_text_not_in_body("since-none-until-cxx03")
        self.assert_text_not_in_body("since-none-until-cxx11")
        self.assert_text_not_in_body("since-none-until-cxx14")
        self.assert_text_in_body("since-none-until-cxx17")
        self.assert_text_in_body("since-none-until-cxx20")

        self.select_cxx17()
        self.assert_text_in_body("since-cxx03-until-none")
        self.assert_text_in_body("since-cxx11-until-none")
        self.assert_text_in_body("since-cxx14-until-none")
        self.assert_text_in_body("since-cxx17-until-none")
        self.assert_text_not_in_body("since-cxx20-until-none")
        self.assert_text_not_in_body("since-cxx03-until-cxx11")
        self.assert_text_not_in_body("since-cxx03-until-cxx14")
        self.assert_text_not_in_body("since-cxx11-until-cxx14")
        self.assert_text_not_in_body("since-cxx03-until-cxx17")
        self.assert_text_not_in_body("since-cxx11-until-cxx17")
        self.assert_text_not_in_body("since-cxx14-until-cxx17")
        self.assert_text_in_body("since-cxx03-until-cxx20")
        self.assert_text_in_body("since-cxx11-until-cxx20")
        self.assert_text_in_body("since-cxx14-until-cxx20")
        self.assert_text_in_body("since-cxx17-until-cxx20")
        self.assert_text_not_in_body("since-none-until-cxx03")
        self.assert_text_not_in_body("since-none-until-cxx11")
        self.assert_text_not_in_body("since-none-until-cxx14")
        self.assert_text_not_in_body("since-none-until-cxx17")
        self.assert_text_in_body("since-none-until-cxx20")

        self.select_cxx20()
        self.assert_text_in_body("since-cxx03-until-none")
        self.assert_text_in_body("since-cxx11-until-none")
        self.assert_text_in_body("since-cxx14-until-none")
        self.assert_text_in_body("since-cxx17-until-none")
        self.assert_text_in_body("since-cxx20-until-none")
        self.assert_text_not_in_body("since-cxx03-until-cxx11")
        self.assert_text_not_in_body("since-cxx03-until-cxx14")
        self.assert_text_not_in_body("since-cxx11-until-cxx14")
        self.assert_text_not_in_body("since-cxx03-until-cxx17")
        self.assert_text_not_in_body("since-cxx11-until-cxx17")
        self.assert_text_not_in_body("since-cxx14-until-cxx17")
        self.assert_text_not_in_body("since-cxx03-until-cxx20")
        self.assert_text_not_in_body("since-cxx11-until-cxx20")
        self.assert_text_not_in_body("since-cxx14-until-cxx20")
        self.assert_text_not_in_body("since-cxx17-until-cxx20")
        self.assert_text_not_in_body("since-none-until-cxx03")
        self.assert_text_not_in_body("since-none-until-cxx11")
        self.assert_text_not_in_body("since-none-until-cxx14")
        self.assert_text_not_in_body("since-none-until-cxx17")
        self.assert_text_not_in_body("since-none-until-cxx20")