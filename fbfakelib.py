#!/usr/bin/env python2
# -*- coding: utf-8 -*-

""" This file is part of Flibrowser.

    Flibrowser is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Flibrowser is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Flibrowser.  If not, see <http://www.gnu.org/licenses/>."""


from flibcrutch import *
import datetime


def fill_fake_library(library):
    library.series = {1:u'Всё для дураков'}
    library.bundles = {1:u'1-100.zip', 2:u'101-200.zip'}
    library.tags = {1:u'бред', 2:u'шиза', 3:u'глюки'}

    library.authors = {1:AuthorInfo(1, u'Говнищер Мухаммед Чжанович', set((1, 2))),
        2:AuthorInfo(2, u'Брэдбери Рэй', set((3, 4, 5))),
        3:AuthorInfo(3, u'Франсиско-Каэтано-Августин-Лусия-и-Мануэль-и-Хосефа-и-Мигель-Лука-Карлос-Педро Тринидад', set((6,))),
        4:AuthorInfo(4, u'Больной Йожыг', set((7,))),
        }

    ddate = datetime.date(2017, 11, 7)
    ddate2 = datetime.date(2000, 1, 1)

    library.books = {1:BookInfo(1, 1, u'1.fb2.zip', u'Методы и приёмы освежевания летающих объектов', 1, 1, u'fb2', 666, u'ru', set((1,)), 1, ddate),
        2:BookInfo(2, 1, u'2.fb2', u'33 способа проедания насквозь', 1, 2, u'fb2', 666, u'ru', set((1, 2)), 1, ddate),
        3:BookInfo(3, 2, u'3.fb2', u'Венерианские ханурики', 0, 0, u'fb2', 666, u'ru', set((1,)), 1, ddate2),
        4:BookInfo(4, 2, u'4.fb2', u'Вино из мухоморчиков', 0, 0, u'fb2', 666, u'ru', set((1, 3)), 2, ddate2),
        5:BookInfo(5, 2, u'5.fb2', u'Были они бледные и косоглазые', 0, 0, u'fb2', 666, u'ru', set((1,)), 1, ddate2),
        6:BookInfo(6, 3, u'6.fb2', u'Автобиография анацефала', 0, 0, u'fb2', 666, u'ru', set((2,)), 2, ddate),
        7:BookInfo(7, 4, u'7.fb2', u'Как йа был фффтумани', 0, 0, u'fb2', 666, u'ru', set((3,)), 2, ddate),
        }

    for bid in library.books:
        bnfo = library.books[bid]
        bnfo.author = library.authors[bnfo.authorid]


if __name__ == '__main__':
    library = Library()
    fill_fake_library(library)
    print(library)
    for bid in library.books:
        print(library.books[bid])

