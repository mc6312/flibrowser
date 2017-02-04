#!/usr/bin/env python
# -*- coding: utf-8 -*-

#  genrelist_update.py

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


from tempfile import TemporaryFile
import os.path
from gzip import open as gzip_open
import sqlparse

from fbcommon import *
from gi.repository import Gtk, GObject, Pango


# 'lib.libgenrelist.sql.gz'


def import_genre_list_sql(fname):
    """Импорт списка жанров (тэгов) из SQL-файла fname.
    Возвращает кортеж из двух элементов.
    В случае успеха:
    - первый элемент - словарь с жанрами,
    - второй элемент - None.
    В случае ошибки:
    - первый элемент - None,
    - второй элемент - строка с сообщением об ошибке."""

    gdict = dict()

    LEVEL_NONE, LEVEL_INSERT, LEVEL_LIBGEN, LEVEL_VALUES = range(4)

    level = LEVEL_NONE

    def clean_string(s):
        if s.startswith('\'') or s.startswith('"'):
            s = s[1:-1]
        return s

    if not os.path.exists(fname):
        return (None, u'Файл "%s" отсутствует или недоступен' % fname)

    fext = os.path.splitext(fname)[1]

    if fext == u'.gz':
        file_open = gzip_open
        file_mode = 'rt'
    elif fext == u'.sql':
        file_open = open
        file_mode = 'r'
    else:
        return (None, u'Формат файла "%s" не поддерживается' % fname)

    try:
        with file_open(fname, file_mode, encoding='utf-8') as srcf:
            for sr in srcf:
                parsed = sqlparse.parse(sr)

                # гавнина is beginning...
                for stmt in parsed:
                    if stmt.get_type() == 'INSERT':
                        level = LEVEL_INSERT
                        for token in stmt.tokens:
                            if token.ttype == sqlparse.tokens.Token.Keyword:
                                if token.value == 'VALUES':
                                    if level == LEVEL_LIBGEN:
                                        level = LEVEL_VALUES
                            elif token.ttype is None:
                                if level == LEVEL_INSERT:
                                    if str(token.value) == '`libgenrelist`':
                                        level = LEVEL_LIBGEN
                                elif level == LEVEL_VALUES:
                                    for t0 in token.tokens:
                                        if t0.ttype is None:
                                            l = list(map(lambda v: v.value, filter(lambda t: t.ttype != sqlparse.tokens.Token.Punctuation, t0.tokens)))[1:]
                                            if len(l) != 3:
                                                continue # влом полностью проверять
                                            gdict[clean_string(l[0])] = u'%s: %s' % (clean_string(l[1]), clean_string(l[2]))

                    else:
                        level = LEVEL_NONE

    except Exception as ex:
        return (None, str(ex))

    return (gdict, None)


def import_genre_list(parentwnd):
    """Предлагает выбрать файл для импорта,
    импортирует его и в случае успеха возвращает словарь с названиями
    жанров. В случае ошибки показывает сообщение об ошибке возвращает None."""

    _IGLT = u'Импорт списка жанров'

    fcdlg = Gtk.FileChooserDialog(_IGLT, parentwnd, Gtk.FileChooserAction.OPEN)
    try:
        fcdlg.add_buttons(Gtk.STOCK_OPEN, Gtk.ResponseType.OK, Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)

        flt = Gtk.FileFilter()
        flt.add_pattern(u'lib.libgenrelist.sql')
        flt.add_pattern(u'lib.libgenrelist.sql.gz')
        flt.set_name(u'Списки жанров в формате SQL')

        fcdlg.add_filter(flt)

        if fcdlg.run() == Gtk.ResponseType.OK:
            fname = fcdlg.get_filename()

            gdict, serr = import_genre_list_sql(fname)
            if serr is not None:
                msg_dialog(parentwnd, _IGLT, serr, Gtk.MessageType.ERROR)
                return None
            else:
                return gdict
    finally:
        fcdlg.destroy()


def main():
    print(import_genre_list(None))
    return 0


if __name__ == '__main__':
    main()
