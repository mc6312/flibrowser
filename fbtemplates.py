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


class BookFileNameTemplate():
    MAX_LENGTH = 32 # ибо нефиг

    VALID_FN_CHARS = ' ().,;!-_#@' + os.sep

    TF_AUTHOR, TF_BOOKID, TF_FILENAME, TF_TITLE, TF_SERNAME, TF_SERNO, TF_SERNAMENO = range(7)

    __tpfld = namedtuple('__tpfld', 'description fldid')

    TEMPLATE_FIELDS = {'a': __tpfld(u'имя автора', TF_AUTHOR),
        'i': __tpfld(u'идентификатор книги', TF_BOOKID),
        'f': __tpfld(u'оригинальное имя файла', TF_FILENAME),
        't': __tpfld(u'название книги', TF_TITLE),
        'n': __tpfld(u'номер в серии', TF_SERNO),
        's': __tpfld(u'название серии', TF_SERNAME),
        'r': __tpfld(u'(название серии - номер в серии)', TF_SERNAMENO)}

    def __init__(self, library, ts):
        """Разбирает строку шаблона ts.
        Строка может быть пустой (см. описание ф-и get_book_fname).
        Шаблон складывается в поле template.
        library - экземпляр Library.
        В случае ошибок в формате шаблона генерируется исключение ValueError."""

        if len(ts) > self.MAX_LENGTH:
            raise ValueError(u'Строка шаблона длиннее %d символов' % self.MAX_LENGTH)

        self.library = library

        ts = ts.strip() # пробелы в начале и в конце всегда убираем!
        self.templatestr = ts

        if not self.templatestr:
            # раз шаблон пустой - делаем из него умолчальный
            self.template = [self.TF_BOOKID, self.TF_TITLE]
            return

        self.template = []
        # список элементов шаблона
        # может содержать строки (которые потом используются "как есть"),
        # или цельночисленные значения TF_xxx

        slen = len(ts)
        six = 0

        while six < slen:
            sstart = six
            while (six < slen) and (ts[six] != '%'): six += 1

            if six > sstart:
                self.template.append(ts[sstart:six])

            if six >= slen:
                break

            six += 1 # проходим мимо %
            if six >= slen:
                raise ValueError(u'Ошибка в шаблоне (символ %d): преждевременное завершение шаблона (нет имени поля)' % six)

            tv = ts[six]
            six += 1

            if tv not in self.TEMPLATE_FIELDS:
                raise ValueError(u'Ошибка в шаблоне (символ %d): неподдерживаемое имя поля - "%s"' % (six, tv))

            self.template.append(self.TEMPLATE_FIELDS[tv].fldid)

    def get_book_fname(self, bnfo):
        """Генерирует не содержащее недопустимых для ФС символов имя файла
        вида 'bookid title (cycle - no).ext' из полей bnfo (экземпляра BookInfo).
        Имя может содержать разделители путей (для подкаталогов).
        Возвращает кортеж из двух элементов - пути и собственно имени файла.
        Расширение добавляется всегда (из поля bnfo.format).
        Если шаблон (self.template) пустой - возвращаем "стандартное" имя файла
        из bookid и format.
        Путь может быть пустой строкой, если шаблон не содержал
        разделителей путей."""

        if not self.template:
            return ('', u'%s.%s' % (bnfo.filename, bnfo.format))

        fname = []

        def get_sername_str():
            return '' if not bnfo.series else self.library.series[bnfo.series]

        def get_serno_str():
            return str(bnfo.serno) if bnfo.series and bnfo.serno else ''

        for tfld in self.template:
            if isinstance(tfld, str):
                fname.append(tfld)
            # иначе считаем, что шаблон правильно сгенерен конструктором, и значение цельночисленное
            elif tfld == self.TF_AUTHOR:
                fname.append(bnfo.author.shortname)
            elif tfld == self.TF_BOOKID:
                fname.append(str(bnfo.bookid))
            elif tfld == self.TF_FILENAME:
                fname.append(bnfo.filename)
            elif tfld == self.TF_TITLE:
                fname.append(bnfo.title)
            elif tfld == self.TF_SERNAME:
                fname.append(get_sername_str())
            elif tfld == self.TF_SERNO:
                fname.append(get_serno_str())
            elif tfld == self.TF_SERNAMENO:
                sname = get_sername_str()

                if sname:
                    sno = get_serno_str()
                    fname.append('(%s%s)' % (sname, '' if not sno else ' - %s' % sno))

        fname = '%s.%s' % ((''.join(fname)).strip(), bnfo.format)
        # расширение файла добавляем всегда

        # выкидываем недопустимые для имен файла символы
        return os.path.split(u''.join(filter(lambda c: c.isalnum() or c in self.VALID_FN_CHARS, fname)))


BookFileNameTemplate.TEMPLATE_HELP = u'''Шаблон - строка с полями вида %%N.
Поддерживаются поля:
%s

В случае пустого шаблона будет использоваться оригинальное имя файла.
Шаблон может содержать символы "%s" - в этом случае будут создаваться подкаталоги.''' % \
(u'\n'.join(map(lambda k: u'%s\t- %s' % (k, BookFileNameTemplate.TEMPLATE_FIELDS[k].description), sorted(BookFileNameTemplate.TEMPLATE_FIELDS.keys()))),
# ибо непосредственно в описании класса лямбда с какого-то хрена не видит ранее заданные переменные класса,
# а создавать такой хелповник динамически вызовом метода класса - не интересно, т.к. он нужен до создания экземпляра класса
os.sep)


if __name__ == '__main__':
    print('[%s test]' % __file__)
    from fbfakelib import fill_fake_library
    from os.path import join as path_join

    library = Library()
    fill_fake_library(library)

    template = BookFileNameTemplate(library, '%a/%t %z%r')
    for bid in library.books:
        bnfo = library.books[bid]
        #print(bnfo)
        bdir, bname = template.get_book_fname(bnfo)
        print(path_join(bdir, bname))
