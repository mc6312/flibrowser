#!/usr/bin/env python3
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


import sys, os, os.path
from collections import namedtuple
from time import time
import zipfile
import json
import re
import datetime
from fnmatch import fnmatch
from locale import getdefaultlocale
from platform import system as system_name
from fbconfig import *


# файлы банлиста, жанров и прочего, что НЕ должно зависеть от закидонов ОС
DATABASE_ENCODING = 'utf-8'

# кодировка файла .inpx - приколочена внутре гвоздями!
INPX_INDEX_ENCODING = 'utf-8'
INPX_REC_SEPARATOR = '\x04'


INPX_REC_AUTHOR     = 0
INPX_REC_GENRE      = 1
INPX_REC_TITLE      = 2
INPX_REC_SERIES     = 3
INPX_REC_SERNO      = 4
INPX_REC_FILE       = 5
INPX_REC_SIZE       = 6
INPX_REC_LIBID      = 7
INPX_REC_DEL        = 8
INPX_REC_EXT        = 9
INPX_REC_DATE       = 10
INPX_REC_LANG       = 11
INPX_REC_KEYWORDS   = 12


"""Структура записи файла .inp:

AUTHOR;GENRE;TITLE;SERIES;SERNO;FILE;SIZE;LIBID;DEL;EXT;DATE;LANG;KEYWORDS;<CR><LF>
Разделитель полей записи (вместо ';') - 0x04
Завершают запись символы <CR><LF> - 0x0D,0x0A
--------------------------------------------------------------------------

Все поля записи представлены в символьном виде. Поле может быть 'пустым',
т.е. иметь нулевую длину.

Идентификаторы полей записи файла inpx:

AUTHOR      [текст]         Один или несколько авторов книги в формате <Ф,И,О:> подряд без пробелов.
GENRE       [текст]         Один или несколько жанров в формате <genre_id:> подряд без пробелов.
TITLE       [текст]         Заголовок книги.
SERIES      [текст]         Название серии в которую входит книга.
SERNO       [целое]         Номер книги в серии.
FILE        [целое/текст]   Номер книги/имя файла в архиве ххх-хххх.zip
SIZE        [целое]         Размер файла в байтах
LIBID       [целое]         BookId
DEL         [целое]         флаг удаления:
                            Пустое поле - для существующей книги
                            1 - для удалённой книги.
EXT         [текст]         Тип файла - fb2, doc, pdf, ...
DATE        [текст]         YYYY-MM-DD. Дата занесения книги в библиотеку
LANG        [текст]         Язык книги - ru, en, ...
KEYWORDS    [текст]         тэги"""


def str_to_regex(s):
    return re.compile(s, re.UNICODE|re.IGNORECASE)


def comma_separated_str_to_set(s):
    return set(filter(None, map(lambda t: t.lower().strip(), s.split(','))))


class BookInfo():
    def __init__(self, bookid, authorid, filename, title, series, serno, _format, fsize, lang, tags, bundle, date):
        # bookid    - целое; id книги в БД Flibusta/LibRusEc/совместимых
        self.bookid = bookid
        # authorid  - целое; id автора (тут у нас группа авторов пока что считается за одного)
        self.authorid = authorid
        # ссылка на экземпляр AuthorInfo
        self.author = None
        # filename  - строка; имя файла книги, обычно "bookid.fb2"
        self.filename = filename
        # title     - строка; название книги
        self.title = title
        # series    - целое; серия книг (если есть). хранится как хэш от нормализованного названия, сами названия - в словаре Library.series
        self.series = series
        # serno     - целое; номер в серии (еслиесть)
        self.serno = serno
        # format    - строка; формат файла книги (он же расширение файла)
        self.format = _format
        # fsize     - целое; размер файла книги
        self.fsize = fsize
        # lang      - строка; язык книги
        self.lang = lang
        # tags      - множество; содержит id's тэгов
        self.tags = tags
        # bundle    - целое; хэш нормализованного названия файла архива с книгами, сами названия - в словаре Library.bundles
        self.bundle = bundle
        # date      - datetime.date
        self.date   = date


class AuthorInfo():
    def __init__(self, aid, aname, books):
        # aid   - хэш нормализованного имени автора
        self.aid = aid
        # aname - имя автора в человекочитаемом виде
        self.aname = aname
        # books - множество bookid
        self.books = books


def inpx_date_to_date(s, defval):
    """Преобразование строки вида YYYY-MM-DD в datetime.date.
    Возвращает результат преобразования в случае успеха.
    Если строка не содержит правильной даты - возвращает значение defval."""

    try:
        d = datetime.datetime.strptime(s, '%Y-%m-%d')
        return d.date()
    except ValueError:
        return defval


class BookFileNameTemplate():
    VALID_FN_CHARS = ' ().,;!-_#@' + os.sep

    TF_AUTHOR, TF_BOOKID, TF_FILENAME, TF_TITLE, TF_SERNAME, TF_SERNO = range(6)

    TEMPLATE_FIELDS = {'a': (u'имя автора', TF_AUTHOR),
        'i': (u'идентификатор книги', TF_BOOKID),
        'f': (u'оригинальное имя файла', TF_FILENAME),
        't': (u'название книги', TF_TITLE),
        'n': (u'номер в серии', TF_SERNAME),
        's': (u'название серии', TF_SERNO)}

    def __init__(self, library, ts):
        """Разбирает строку шаблона ts.
        Строка может быть пустой (см. описание ф-и get_book_fname).
        Шаблон складывается в поле template.
        library - экземпляр Library.
        В случае ошибок в формате шаблона генерируется исключение ValueError."""

        self.library = library

        ts = ts.strip() # пробелы в начале и в конце всегда убираем!
        self.templatestr = ts

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
                raise ValueError(u'Ошибка в шаблоне: преждевременное завершение шаблона (нет имени поля)')

            tv = ts[six]
            six += 1

            if tv not in self.TEMPLATE_FIELDS:
                raise ValueError(u'Ошибка в шаблоне: неподдерживаемое имя поля - "%s"' % tv)

            self.template.append(self.TEMPLATE_FIELDS[tv][1])

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

        for tfld in self.template:
            if isinstance(tfld, str):
                fname.append(tfld)
            # иначе считаем, что шаблон правильно сгенерен конструктором, и значение цельночисленное
            elif tfld == self.TF_AUTHOR:
                fname.append(bnfo.author.aname)
            elif tfld == self.TF_BOOKID:
                fname.append(str(bnfo.bookid))
            elif tfld == self.TF_FILENAME:
                fname.append(bnfo.filename)
            elif tfld == self.TF_TITLE:
                fname.append(bnfo.title)
            elif tfld == self.TF_SERNAME:
                fname.append('' if not bnfo.series else self.library.series[bnfo.series])
            elif tfld == self.TF_SERNO:
                fname.append(str(bnfo.serno) if bnfo.series and bnfo.serno else '')

        fname.append('.%s' % bnfo.format) # расширение файла добавляем всегда

        # выкидываем недопустимые для имен файла символы
        return os.path.split(u''.join(filter(lambda c: c.isalnum() or c in self.VALID_FN_CHARS, ''.join(fname))))


BookFileNameTemplate.TEMPLATE_HELP = u'''Шаблон - строка с полями вида %%N.
Поддерживаются поля:
%s

В случае пустого шаблона будет использоваться оригинальное имя файла.
Шаблон может содержать символы "%s" - в этом случае будут создаваться подкаталоги.''' % \
(u'\n'.join(map(lambda k: u'%s\t- %s' % (k, BookFileNameTemplate.TEMPLATE_FIELDS[k][0]), sorted(BookFileNameTemplate.TEMPLATE_FIELDS.keys()))),
# ибо непосредственно в описании класса лямбда с какого-то хрена не видит ранее заданные переменные класса,
# а создавать такой хелповник динамически вызовом метода класса - не интересно, т.к. он нужен до создания экземпляра класса
os.sep)


class Library():
    """Класс для библиотеки"""

    GENRE_NAMES_FNAME = u'genrelist.json'

    class LibSettings(Settings):
        V_LIBROOT = 'library_root_directory'
        V_LIBINDEX = 'library_index_file'
        V_EXTDIR = 'extract_directory'
        V_LANGS = u'languages'

        DEF_LANGS = {u'ru'} # патамушто я шовинистЪ

        VALID_KEYS = {V_LIBROOT:str, V_LIBINDEX:str,
            V_EXTDIR:str, V_LANGS:str}
        DEFAULTS = {V_LIBROOT:None, V_LANGS:u' '.join(list(DEF_LANGS))}

        def languages_to_str(self, langs):
            """Преобразует множество кодов языков в строку, разделённую пробелами"""

            return u' '.join(langs)

        def languages_from_str(self, s):
            """Преобразует строку, разделённую пробелами, во множество языков"""

            ls = set(s.lower().split(None))
            ls.update(self.DEF_LANGS)
            return ls

    def __init__(self):
        self.authors = {}   # ключи - aid (хэши нормализованных имен авторов), а значения - экземпляры AuthorInfo.
        self.books = {}     # ключи - bookid's, значения - экземпляры BookInfo
        self.bundles = {}   # ключи - хэши имен файлов, значения - имена файлов
        self.series = {}    # ключи - хэши нормализованных названий серий, значения - сами названия
        self.tags = {}      # ключи - хэши тэгов, значения - сами тэги
        self.genrenames = {}# ключи - хэши тэгов, значения - названия (человекочитаемые)

        self.languages = self.LibSettings.DEF_LANGS # допустимые языки

        # настройки (изменяются вручную или вызовом load_settings)
        # каталог самого поделия
        self.appDir = os.path.split(os.path.abspath(__file__))[0]
        if not os.path.isdir(self.appDir):
            # похоже, мы в жо... в зипе
            self.appDir = os.path.split(self.appDir)[0]

        # каталог со всеми настройками
        self.cfgDir = self.appDir

        self.libraryRootDir = self.appDir
        self.libraryIndexFile = ''
        self.dataDirectory = self.appDir # каталог со служебными файлами (banned* и др.)
        self.genreNamesFile = None
        self.extractDir = os.path.abspath(u'./')

        self.config = self.LibSettings()

    def __str__(self):
        # для отладки

        return u'''%s:
  appDir:           "%s"
  cfgDir:           "%s"
  libraryRootDir:   "%s"
  libraryIndexFile: "%s"
  dataDirectory:    "%s"
  genreNamesFile:   "%s"
  extractDir:       "%s"
  authors:          %d item(s)
  books:            %d item(s)
  bundles:          %d item(s)
  series:           %d item(s)
  tags:             %d item(s)
  genrenames:       %d item(s)
  languages:        %d item(s)''' % (self.__class__.__name__,
        self.appDir, self.cfgDir, self.libraryRootDir,
        self.libraryIndexFile, self.dataDirectory, self.genreNamesFile, self.extractDir,
        len(self.authors), len(self.books), len(self.bundles), len(self.series), len(self.tags),
        len(self.genrenames), len(self.languages))

    def parse_author_name(self, rawname):
        """Приведение списка имён авторов к виду "Фамилия Имя Отчество[, Фамилия Имя Отчество]"."""

        rawnames = filter(None, rawname.split(u':'))
        tmpn = []

        for rawname in rawnames:
            # потому что в индексных файлах кривожопь
            tmpn.append((u' '.join(map(lambda s: s.strip(), rawname.split(u',')))).strip())

        return u', '.join(tmpn)

    def name_hash(self, s):
        return hash(s.lower()) if s else None

    def get_series_name(self, serid):
        if serid in self.series:
            return self.series[serid]
        else:
            return u''

    def get_book_tags(self, bnfo):
        """Возвращает строку с тэгами, разделёнными запятыми.
        bnfo - экземпляр BookInfo."""

        return u', '.join(sorted(map(self.tag_display_name, bnfo.tags)))

    def parse_inpx_file(self, fpath, callback=None):
        """Разбор файла .inpx и загрузка его в словарь self.authors.
        callback(fraction) - (если не None) функция для отображения прогресса,
        передаваемое значение fraction - в диапазоне 0.0-1.0."""

        print(u'Загрузка общего файла индекса...')

        try:
            with zipfile.ZipFile(fpath, 'r', allowZip64=True) as zf:
                indexFiles = []

                # сначала ищем все индексные файлы, кладем в список

                for nfo in zf.infolist():
                    if nfo.file_size != 0:
                        fname = os.path.splitext(nfo.filename)

                        if fname[1].lower() == u'.inp':
                            bundle = fname[0] + u'.zip'

                            indexFiles.append((bundle, nfo.filename))

                numindexes = len(indexFiles)
                print(u'  индексных файлов: %d' % numindexes)

                # ...потому что дальше нужно работать с _отсортированным_ списком файлов: новое затирает старое

                rejected = 0
                ixindex = 0
                for bundle, fname in sorted(indexFiles, key=lambda a: a[0]):
                    ixindex += 1

                    znfo = zf.getinfo(fname)
                    defdate = datetime.date(znfo.date_time[0], znfo.date_time[1], znfo.date_time[2]) # могли бы поганцы и константы для индексов сделать, или namedtuple

                    with zf.open(fname, 'r') as f:
                        for recix, recstr in enumerate(f):
                            srcrec = [u'<not yet parsed>']
                            try:
                                srcrec = recstr.decode(INPX_INDEX_ENCODING, 'replace').split(INPX_REC_SEPARATOR)

                                if not srcrec[INPX_REC_LIBID].isdigit():
                                    raise ValueError(u'Book id is invalid: "%s"' % srcrec[INPX_REC_LIBID])

                                bookid = int(srcrec[INPX_REC_LIBID])

                                author = self.parse_author_name(srcrec[INPX_REC_AUTHOR])
                                aid = self.name_hash(author)

                                if srcrec[INPX_REC_DEL] != u'1':
                                    # пока валим без учета даты добавления

                                    # проверяем на допустимость языка
                                    if srcrec[INPX_REC_LANG].lower() not in self.languages:
                                        rejected += 1
                                        continue

                                    taglist = list(filter(None, srcrec[INPX_REC_GENRE].lower().split(u':')))
                                    #print(taglist)

                                    # тэги
                                    btags = set()

                                    # тэги обрабатываем ДО фильтрации - в общий список self.tags должны попасть ВСЕ
                                    for tag in taglist:
                                        tid = hash(tag)

                                        if tid not in self.tags:
                                            self.tags[tid] = tag

                                        btags.add(tid)

                                    #print(btags)

                                    # добавляем автыря в список
                                    if aid not in self.authors:
                                        anfo = AuthorInfo(aid, author, set())
                                        self.authors[aid] = anfo
                                    else:
                                        anfo = self.authors[aid]

                                    # добавляем книжку
                                    sername = srcrec[INPX_REC_SERIES]
                                    serid = self.name_hash(sername)
                                    if serid is not None:
                                        self.series[serid] = sername

                                    # здесь имена жрем как есть, т.к. они могут быть регистрозависимыми!
                                    bunid = hash(bundle)
                                    self.bundles[bunid] = bundle

                                    anfo.books.add(bookid)

                                    serno = int(srcrec[INPX_REC_SERNO]) if srcrec[INPX_REC_SERNO].isdigit() else 0
                                    nbfsize = int(srcrec[INPX_REC_SIZE]) if srcrec[INPX_REC_SIZE].isdigit() else 0

                                    bnfo = BookInfo(bookid, aid,
                                        u'%s.%s' % (srcrec[INPX_REC_FILE], srcrec[INPX_REC_EXT]),
                                        srcrec[INPX_REC_TITLE], serid, serno,
                                        srcrec[INPX_REC_EXT], nbfsize,
                                        srcrec[INPX_REC_LANG], btags, bunid,
                                        inpx_date_to_date(srcrec[INPX_REC_DATE], defdate))
                                    bnfo.author = anfo
                                    self.books[bookid] = bnfo

                                else:
                                    if aid in self.authors:
                                        anfo = self.authors[aid]
                                        if bookid in anfo.books:
                                            anfo.books.remove(bookid)

                                    if bookid in self.books:
                                        del self.books[bookid]

                            except Exception as ex:
                                # вот ниибет, что квыво
                                raise Exception(u'Error in record #%d of file "%s" - %s\n* record: %s' % (recix + 1, fname, str(ex), u';'.join(srcrec)))
                    if callback is not None:
                        callback(float(ixindex) / numindexes)
        except Exception as ex:
            raise Exception(u'Error parsing file "%s",\n%s' % (fpath, str(ex)))

        included = len(self.books)

        print(u'  обработано записей: %d\n  отброшено: %d\n  доступно: %d' % (included+rejected, rejected, included))

    def print_exec_time(self, todo, *arg):
        t0 = time()
        r = todo(*arg)
        t0 = time() - t0
        print(u'  время работы: %.1f сек' % t0)
        return r

    def tag_display_name(self, tid):
        if tid in self.genrenames:
            return self.genrenames[tid]
        elif tid in self.tags:
            return self.tags[tid]
        else:
            return u'?' #!!!

    def load_genre_names(self):
        self.genrenames.clear()

        if os.path.exists(self.genreNamesFile):
            with open(self.genreNamesFile, 'r', encoding=DATABASE_ENCODING) as f:
                srcdict = json.load(f)

                if not isinstance(srcdict, dict):
                    raise TypeError(u'Содержимое файла "%s" не является словарём' % self.genreNamesFile)

                for k in srcdict:
                    if not isinstance(k, str):
                        raise TypeError(u'Ключ "%s" словаря в файле "%s" не является строкой' % (repr(k), self.genreNamesFile))

                    v = srcdict[k]
                    if not isinstance(v, str):
                        raise TypeError(u'Значение по ключу "%s" словаря в файле "%s" не является строкой' % (k, self.genreNamesFile))

                    self.genrenames[hash(k)] = v

    def save_genre_names(self):
        tmpdict = {}
        for gen in self.genrenames.keys():
            tmpdict[self.tags[gen]] = self.genrenames[gen]

        with open(self.genreNamesFile, 'w+', encoding=DATABASE_ENCODING) as f:
            json.dump(tmpdict, f, ensure_ascii=False, indent=' ')

    def load(self, callback=None):
        """Загрузка библиотеки.
        callback(fraction) - (если не None) функция для отображения прогресса,
        передаваемое значение fraction - в диапазоне 0.0-1.0."""

        self.books.clear()

        if not self.libraryRootDir:
            print(u'Корневой каталог библиотеки не указан')
            return

        if not os.path.exists(self.libraryRootDir):
            print(u'Корневой каталог библиотеки "%s" не найден' % rootDir)
            return

        if self.dataDirectory:
            print(u'Загрузка названий жанров...')
            self.load_genre_names()
            print(u'  жанров: %d' % len(self.genrenames))

        self.authors.clear()

        if not self.libraryIndexFile:
            print(u'Файл общего индекса не указан')
            return

        if not os.path.exists(self.libraryIndexFile):
            print(u'Файл общего индекса "%s" не найден' % self.libraryIndexFile)
            return
        else:
            self.print_exec_time(self.parse_inpx_file, self.libraryIndexFile, callback)

    def extract_books(self, bookids, template, pack=False, callback=None):
        """Извлекает книги.
        bookids         - список идентификаторов книг в БД
        template        - экземпляр BookFileNameTemplate;
                          если генерируемые им имена файлов содержат разделители путей,
                          будут созданы соотв. подкаталоги в self.extractDir
        pack            - булевское значение; если True - файлы будут упакованы ZIPом
        callback        - (если не None) функция для отображения прогресса,
                          получает параметр fraction - вещественное число в диапазоне 0.0-1.0
        В случае успеха возвращает пустую строку или None, в случае ошибки
        (одну или несколько книг извлечь не удалось) - возвращает строку
        с сообщением об ошибке."""

        if not bookids:
            return None # ибо пустой список ошибкой не считаем

        if not os.path.exists(self.extractDir):
            return u'Каталог для извлекаемых книг не найден.'

        # выбираем книги и группируем по архивам (т.к. в одном архиве может быть несколько книг)
        xbundles = {}

        extractedbooks = 0
        totalbooks = 0

        for bookid in bookids:
            bnid = self.books[bookid].bundle
            totalbooks += 1

            if bnid not in xbundles:
                bupath = os.path.join(self.libraryRootDir, self.bundles[bnid])
                bubooks = set((bookid,))
                xbundles[bnid] = (bupath, bubooks)
            else:
                xbundles[bnid][1].add(bookid)

        em = []

        ixbook = 0

        createddirs = set()

        for bupath, bubooks in xbundles.values():
            if not os.path.exists(bupath):
                em.append(u'Файл архива "%s" не найден.' % bupath)
            else:
                try:
                    with zipfile.ZipFile(bupath, 'r', allowZip64=True) as zf:
                        missingbooks = 0

                        znames = zf.namelist()

                        for bookid in bubooks:
                            ixbook += 1

                            bnfo = self.books[bookid]

                            if bnfo.filename not in znames:
                                missingbooks += 1
                            else:
                                try:
                                    znfo = zf.getinfo(bnfo.filename)
                                    if znfo.file_size == 0:
                                        em.append(u'Файл "%s" в архиве "%s" имеет нулевой размер. Нечего распаковывать.' % (bnfo.filename, bupath))
                                        continue

                                    BLOCKSIZE = 1*1024*1024

                                    with zf.open(znfo, 'r') as srcf:
                                        if template:
                                            dstsubdir, dstfname = template.get_book_fname(bnfo)
                                        else:
                                            dstsubdir = u''
                                            dstfname = u'%s.%s' % (bnfo.filename, bnfo.format)

                                        dstfpath = os.path.join(self.extractDir, dstsubdir)

                                        if dstsubdir and dstsubdir not in createddirs:
                                            os.makedirs(dstfpath)
                                            createddirs.add(dstsubdir)

                                        dstfpath = os.path.join(dstfpath, dstfname)

                                        with open(dstfpath, 'wb+') as dstf:
                                            remain = znfo.file_size
                                            while remain > 0:
                                                iosize = BLOCKSIZE if remain >= BLOCKSIZE else remain
                                                dstf.write(srcf.read(iosize))
                                                remain -= iosize

                                        if pack:
                                            with zipfile.ZipFile(dstfpath + u'.zip', 'w', zipfile.ZIP_DEFLATED) as dstarcf:
                                                dstarcf.write(dstfpath, dstfname)
                                            os.remove(dstfpath)

                                    extractedbooks += 1

                                except zipfile.BadZipfile as ex:
                                    em.append(u'Ошибка при извлечении файла "%s" из архива "%s" - %s.' % (bfname, bupath, str(ex)))

                            if callback is not None:
                                callback(float(ixbook) / totalbooks)

                        if missingbooks > 0:
                            em.append(u'В архиве "%s" не нашлось несколько файлов (%d из %d).' % (bupath, missingbooks, len(bubooks)))

                except zipfile.BadZipfile as ex:
                    em.append(u'Ошибка при работе с архивом "%s" - %s.' % (bupath, str(ex)))

        if extractedbooks < totalbooks:
            em.append(u'Не извлечено ни одной книги.' if extractedbooks == 0 else u'Извлечено книг: %d из %d.' % (extractedbooks, totalbooks))

        return u'\n'.join(em) if em else None

    def languages_to_str(self):
        """Возвращает строку с кодами допустимых языков (self.languages), разделенных пробелами"""

        return self.config.languages_to_str(self.languages)

    def languages_from_str(self, s):
        """Заполняет self.languages кодами языков из строки s"""

        self.languages = self.config.languages_from_str(s)

    def load_settings(self):
        """Загрузка файла настроек.
        При успешной загрузке возвращает None, иначе - строку с сообщением об ошибке."""

        # в первую очередь ищем в стандартном расположении
        sysname = system_name()
        if sysname == 'Windows':
            self.cfgDir = os.path.join(os.environ['APPDATA'], u'flibrowser')
        else:
            if sysname != 'Linux':
                print('Warning! Unsupported platform!', file=sys.stderr)

            self.cfgDir = os.path.expanduser(u'~/.config/flibrowser')

        #print('config directory:', self.cfgDir)

        if not os.path.exists(self.cfgDir):
            # ...во вторую - в каталоге, где расположен скрипт
            self.cfgDir = self.appDir

        # а у нас ваще файл настроек-то есть?
        self.config.cfgPath = os.path.join(self.cfgDir, u'config')

        if not os.path.exists(self.config.cfgPath):
            return u'Файл настроек не найден.'
        #else:
        #    print(u'Файл настроек: %s' % self.config.cfgPath)

        try:
            self.config.load()
        except SettingsError as ex:
            return str(ex)

        self.libraryRootDir = self.config.get_value(self.LibSettings.V_LIBROOT, self.libraryRootDir)
        self.libraryIndexFile = self.config.get_value(self.LibSettings.V_LIBINDEX, self.libraryIndexFile)
        self.dataDirectory = self.cfgDir # нефиг разводить х.з. что. self.config.get_value(self.LibSettings.V_DATADIR, self.cfgDir)
        self.extractDir = self.config.get_value(self.LibSettings.V_EXTDIR, self.extractDir)

        #print('self.libraryRootDir: %s\nself.libraryIndexFile: %s\nself.dataDirectory: %s\nself.extractDir: %s' % (self.libraryRootDir, self.libraryIndexFile, self.dataDirectory, self.extractDir))

        self.languages_from_str(self.config.get_value(self.LibSettings.V_LANGS))

        return None

    def validate_settings(self):
        if not self.libraryRootDir:
            self.libraryRootDir = u'.'

        self.libraryRootDir = os.path.abspath(os.path.expanduser(self.libraryRootDir))
        if not os.path.exists(self.libraryRootDir):
            return u'Каталог "%s" не найден' % self.libraryRootDir

        def validate_path(what, path, relativeto=self.cfgDir):
            """Проверярт, существует ли путь.
            В случае успеха возвращает кортеж вида (path, None),
            в случае ошибки - (None, error_string)."""

            if not path:
                return (None, u'%s: путь не задан' % what)

            if path.startswith(u'~'):
                path = os.path.expanduser(path)
            else:
                ixdir = os.path.split(path)[0]
                if not ixdir:
                    if not relativeto:
                        return (None, u'%s: должен быть указан абсолютный или относительный путь' % what)

                    path = os.path.join(relativeto, path)

            if not os.path.exists(path):
                return (None, u'%s "%s" не найден' % (what, path))

            return (path, None)

        self.libraryIndexFile, errs = validate_path(u'Файл общего индекса', self.libraryIndexFile, self.libraryRootDir)
        #print(self.libraryIndexFile, errs)
        if errs:
            return errs

        """if self.dataDirectory:
            self.banListFile, errs = validate_path(u'Предупреждение: файл списка исключений', self.dataDirectory)
            if errs:
                print(errs)
            #if not self.banListFile:
            #    return"""

        self.genreNamesFile = os.path.join(self.dataDirectory, self.GENRE_NAMES_FNAME)

        if self.extractDir:
            self.extractDir, errs = validate_path(u'Каталог для извлечения книг', self.extractDir, None)
            if errs:
                return errs
        else:
            self.extractDir = os.path.abspath(u'./')

        # debug
        #print('cfgdir', self.cfgDir)
        #print('root', self.libraryRootDir)
        #print('index', self.libraryIndexFile)
        #print('datadir', self.dataDirectory)
        #print('genres', self.genreNamesFile)
        #print('extractdir', self.extractDir)

        return None

    def save_settings(self):
        self.config.set_value(self.LibSettings.V_LIBROOT, self.libraryRootDir)
        self.config.set_value(self.LibSettings.V_LIBINDEX, self.libraryIndexFile)
        self.config.set_value(self.LibSettings.V_EXTDIR, self.extractDir)
        self.config.set_value(self.LibSettings.V_LANGS, self.languages_to_str())

        self.config.save()

    def filter(self, filterfunc=None, progressfunc=None):
        """Фильтрует список книг.

        filterfunc      - если не None - функция, получающая на входе экземпляр BookInfo,
                          и возвращающая булевское значение.
                          если None - ничего не ищем!

        progressfunc    - если не None - функция для отображения прогресса,
                          получающая на входе значение в диапазоне 0.0-1.0.

        Возвращает список bookid (или пустой список, если ничего не находит)."""

        if progressfunc is not None and not callable(progressfunc):
            raise TypeError(u'%s.filter: progressfunc is not callable' % self.__class__.__name__)

        if not callable(filterfunc):
            return [] # потому что нефиг

        ret = set()

        #print u'Library.filter rxauthors="%s"' % rxauthors.pattern

        nbooks = len(self.books)
        PBAR_RATE = 1000

        for ixbook, bnfo in enumerate(self.books.values()):
            if (progressfunc) and (ixbook % PBAR_RATE) == 0:
                progressfunc(float(ixbook) / nbooks)

            if not filterfunc(bnfo):
                continue

            ret.add(bnfo.bookid)

        return list(ret)


# debug
def main():
    print(BookFileNameTemplate.TEMPLATE_HELP)
    return

    library = Library()
    lse = library.load_settings()
    if lse:
        print(lse)
        return

    lse = library.validate_settings()
    if lse:
        print(lse)
        return

    print(library.libraryIndexFile)

    #library.save_settings()
    #return

    print('loading library')
    library.load()
    print('  loaded')

    #print(library.tags)

    t = BookFileNameTemplate(library, '%a/%i - %s (%n) - %t (shit)')
    #print(t.template)

    print('* template test *')

    maxk = 30
    for bookid in library.books:
        bnfo = library.books[bookid]

        print('name:', t.get_book_fname(bnfo))

        maxk -= 1
        if maxk <= 0:
            break

    return #!!!

    print(u'* поиск')
    t0 = time()

    if library.authors:
        #sf = lambda s: True, lambda s: re.search(u'эйзенхорн', s, re.UNICODE|re.IGNORECASE)
        sf = lambda nfo: nfo.filename.find('666') >= 0
        f = library.filter(filterfunc=sf)
        print('found', len(f))

    t0 = time() - t0
    print('time: %.2g sec.' % t0)

    return 0

    n = 40
    for bnfo in library.books.values():
        if n <= 0:
            break
        n -= 1
        print(library.get_book_fs_name(bnfo, (EXTRACTPARAM_RENAME, EXTRACTPARAM_AUTHORNAME, EXTRACTPARAM_ZIPFILE)))

    return 0


if __name__ == '__main__':
    main()

