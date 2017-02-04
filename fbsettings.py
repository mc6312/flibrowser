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


from fbcommon import *
from gi.repository import Gtk
from gi.repository.GdkPixbuf import Pixbuf

import re
import os.path

from flibcrutch import str_to_regex, comma_separated_str_to_set
from fbgenlistimport import import_genre_list


class SettingsEditor():
    FIELD_NAME = None   # отображаемое название поля, должно быть задано в классе-потомке
    FIELD_COMMENT = u'' # строка примечания; если задана - будет отображаться под виджетом container
    CRITICAL = True     # если True - блокировать сохранение настроек в случае ошибки в этом редакторе,
                        # если False - только показывать предупреждение

    def __init__(self):
        self.container = None
        # потомок должен сюда пихать ссылку на виджет-контейнер, который содержит остальные

        self.parentwnd = None
        # окно-владелец для диалогов с сообщениями

    def set_data(self):
        """Заполняет виджеты данными из соот. куска БД"""

        raise NotImplementedError(u'%s.set_data() not implemented' % self.__class__.__name__)

    def validate_data(self):
        """Проверяет данные из виджетов.
        В случае правильных данных помещает их во временный буфер
        и возвращает None или пустую строку,
        в случае ошибки устанавливает фокус ввода на соотв. виджет
        и возвращает строку с сообщением об ошибке."""

        return u'%s.validate_data() not implemented' % self.__class__.__name__

    def get_data(self):
        """Копирует данные из временного буфера в БД."""

        raise NotImplementedError(u'%s.get_data() not implemented' % self.__class__.__name__)


class REListEditor(SettingsEditor):
    def __init__(self, relist):
        super().__init__()

        self.relist = relist
        self.tmprelist = []

        self.textview = Gtk.TextView()
        self.textview.set_border_width(WIDGET_SPACING)
        #self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR) # нене, там же регекспы, разделенные переводами строк

        self.textbuffer = self.textview.get_buffer()

        self.container = create_scwindow()
        self.container.add(self.textview)

    def set_data(self):
        self.textbuffer.set_text(u'\n'.join(map(lambda r: r.pattern, self.relist)))

    def validate_data(self):
        self.tmprelist.clear()

        bstart, bend = self.textbuffer.get_bounds()

        for lix, ts in enumerate(self.textbuffer.get_text(bstart, bend, False).splitlines()):
            ts = ts.strip()
            try:
                self.tmprelist.append(str_to_regex(ts))
            except re.error as ex:
                bstart.set_line(lix)
                self.textbuffer.place_cursor(bstart)
                self.textview.grab_focus()
                return u'Ошибка в строке #%d - %s' % (lix + 1, str(ex))

        return None

    def get_data(self):
        self.relist.clear()
        self.relist += self.tmprelist[:]


class TagNameEditor(SettingsEditor):
    FIELD_NAME = u'Тэги'
    ICON, TAG, TAGNAME, DISPNAME = range(4)
    CRITICAL = False # т.к. в библиотеке, сделанной другими людьми, могут быть хронические косяки

    def __init__(self, library):
        super().__init__()

        self.library = library
        self.tmpgenrenames = {}

        # значение тэга, строка тэга, отображаемая строка тэга
        self.listview, self.liststore, scrollwnd, renderers = create_listview((Pixbuf, GObject.TYPE_INT64, GObject.TYPE_STRING, GObject.TYPE_STRING),
            # индекс, 'название', editable, expand, align
            (('', self.ICON, False, False, 0), ('Тэг', self.TAGNAME, False, False, 0), (u'Название жанра', self.DISPNAME, True, True, 0)))
        self.listsel = self.listview.get_selection()

        self.container = Gtk.VBox(spacing=WIDGET_SPACING)
        self.container.pack_start(scrollwnd, True, True, 0)

        hbox = Gtk.HBox(spacing=WIDGET_SPACING)
        #hbox.set_border_width(WIDGET_SPACING)
        self.container.pack_end(hbox, False, False, 0)

        btnimport = Gtk.Button(u'Импорт списка жанров')
        btnimport.connect('clicked', lambda b: self.import_genre_names())
        hbox.pack_start(btnimport, False, False, 0)

        renderers[-1].connect('edited', self.name_edited)

        self.iconOk = None #self.listview.render_icon_pixbuf('gtk-yes', Gtk.IconSize.MENU)
        self.iconError = self.listview.render_icon_pixbuf(Gtk.STOCK_DIALOG_WARNING, Gtk.IconSize.MENU)

    def set_row_icon(self, itr, valid):
        """Установка значка правильности данных.
        itr     - Gtk.TreeIter,
        valid   - bool"""
        self.liststore.set_value(itr, self.ICON, self.iconOk if valid else self.iconError)

    def name_edited(self, crt, path, text):
        text = text.strip()

        itr = self.liststore.get_iter(path)
        self.liststore.set_value(itr, self.DISPNAME, text)
        self.set_row_icon(itr, text != '')

    def set_data(self):
        tmplst = []

        for tagid in self.library.tags:
            tagname = self.library.tags[tagid]

            if tagid in self.library.genrenames:
                dispname = self.library.genrenames[tagid]
                icon = self.iconOk
            else:
                dispname = u''
                icon = self.iconError

            tmplst.append((icon, tagid, tagname, dispname))

        self.update_listview(tmplst)

    def update_listview(self, data):
        """Кладёт в ListStore данные из списка с элементами вида
        (icon, tagid, tagname, dispname)"""

        self.listview.set_model(None)
        self.liststore.clear()

        for row in sorted(data, key=lambda r: r[self.TAGNAME]):
            self.liststore.append(row)

        self.listview.set_model(self.liststore)
        self.listview.set_tooltip_column(self.DISPNAME)
        self.listview.set_search_column(self.DISPNAME)

    def validate_data(self):
        self.tmpgenrenames.clear()

        errtags = []
        erritrs = []

        itr = self.liststore.get_iter_first()
        if itr:
            while True:
                tagname = self.liststore.get_value(itr, self.TAGNAME)
                dispname = self.liststore.get_value(itr, self.DISPNAME)
                if not dispname:
                    # отсутствие dispname - не критическая ошибка, потому продолжаем сгребать остальные
                    errtags.append(tagname)
                    erritrs.append(itr)

                self.tmpgenrenames[self.liststore.get_value(itr, self.TAG)] = dispname

                itr = self.liststore.iter_next(itr)
                if not itr:
                    break

        if errtags:
            lvpath = self.liststore.get_path(erritrs[0])
            self.listview.set_cursor(lvpath)
            self.listview.scroll_to_cell(lvpath)
            self.listview.grab_focus()

            return u'Не введёно название жанра для тэга "%s"' % errtags[0] # все пока пихать не будем - а то может диалоговое окно разнести

    def get_data(self):
        self.library.genrenames.clear()
        self.library.genrenames.update(self.tmpgenrenames)

    def import_genre_names(self):
        tagdict = import_genre_list(self.parentwnd)
        # ключи - тэги в виде строк, значения - детальные названия жанров

        # мержим с уже имеющимся:
        # если в БД есть тэги, которых нет в импортированном словаре,
        # добавляем их в словарь, ибо на них есть ссылки в БД книг
        ntagadded = 0

        #print(set(tagdict.keys()) - set(self.library.tags.keys()))

        for tagid, tagname in map(lambda k: (k, self.library.tags[k]), self.library.tags):
            #print(tagid, tagname)
            if tagname not in tagdict:
                if tagid in self.library.genrenames:
                    genname = self.library.genrenames[tagid]
                else:
                    genname = u''

                tagdict[tagname] = genname
            else:
                ntagadded += 1

        #print(u'Импортировано новых тэгов: %d' % ntagadded)

        if tagdict is not None:
            #print('%d genre(s) imported' % len(gdict))
            #(icon, tagid, tagname, dispname)

            tmplst = []

            for tagname in tagdict:
                dispname = tagdict[tagname]
                tagid = hash(tagname)

                if dispname:
                    icon = self.iconOk
                else:
                    icon = self.iconError

                tmplst.append((icon, tagid, tagname, dispname))

            self.update_listview(tmplst)


class LibSettingsEditor(SettingsEditor):
    FIELD_NAME = u'Основные параметры'
    FIELD_COMMENT = 'Внимание! Изменённые параметры будут использованы при следующем запуске программы.'
    CRITICAL = True

    def __init__(self, library):
        super().__init__()

        self.library = library

        self.tmpLangs = set()
        self.tmpLibraryRootDir = ''
        self.tmpLibraryIndexFile = ''

        self.grid = Gtk.Grid(column_spacing=WIDGET_SPACING, row_spacing=WIDGET_SPACING)
        self.grid.set_border_width(WIDGET_SPACING)
        self.container = self.grid

        def add_st_dir_field(title, action):
            lab = create_aligned_label(u'%s:' % title, valign=0.5)
            self.grid.attach_next_to(lab, None, Gtk.PositionType.BOTTOM, 1, 1)

            btn = Gtk.FileChooserButton.new(title, action)
            btn.props.hexpand = True
            self.grid.attach_next_to(btn, lab, Gtk.PositionType.RIGHT, 1, 1)

            return btn

        #self.library.libraryRootDir
        self.btnlibrootdir = add_st_dir_field(u'Каталог библиотеки', Gtk.FileChooserAction.SELECT_FOLDER)

        #self.library.libraryIndexFile
        self.btnlibindexfile = add_st_dir_field(u'Файл индекса библиотеки', Gtk.FileChooserAction.OPEN)

        self.libindexfilter = Gtk.FileFilter()
        self.libindexfilter.set_name(u'Индексные файлы MyHomeLib')
        self.libindexfilter.add_pattern(u'*.inpx')

        self.btnlibindexfile.set_filter(self.libindexfilter)

        #self.library.self.extractDir # а вот оно изменяется из основного междумордия

        #self.library.languages
        lab = create_aligned_label(u'Допустимые языки:', valign=0.5)
        self.grid.attach_next_to(lab, None, Gtk.PositionType.BOTTOM, 1, 1)

        self.entrylangs = Gtk.Entry()
        self.entrylangs.hexpand = True
        self.grid.attach_next_to(self.entrylangs, lab, Gtk.PositionType.RIGHT, 1, 1)

        self.grid.attach_next_to(create_aligned_label(u'Коды языков разделяются пробелами'), self.entrylangs, Gtk.PositionType.BOTTOM, 1, 1)

    def set_data(self):
        self.btnlibrootdir.set_current_folder(self.library.libraryRootDir)
        self.btnlibindexfile.select_filename(self.library.libraryIndexFile)

        self.tmpLangs = self.library.languages
        self.entrylangs.set_text(self.library.languages_to_str())

    def validate_data(self):
        self.tmpLibraryRootDir = self.btnlibrootdir.get_current_folder()
        #if self.tmpLibraryRootDir is not None:
        # пёс с ним, не будем ругаться

        #
        self.tmpLibraryIndexFile = self.btnlibindexfile.get_filename()
        if os.path.isfile(self.tmpLibraryIndexFile):
            self.btnlibindexfile.grab_focus()
            return None
        else:
            return u'Не выбран файл индекса библиотеки'

        #
        self.tmpLangs = self.library.config.languages_from_str(self.entrylangs.get_text())

    def get_data(self):
        """Возвращает None в случае успеха, иначе - строку с сообщением об ошибке"""
        self.library.libraryRootDir = self.tmpLibraryRootDir

        self.library.libraryIndexFile = self.tmpLibraryIndexFile

        self.library.languages = self.tmpLangs


class InitialSettingsDialog():
    def __init__(self, library):
        self.library = library
        self.dialog = Gtk.Dialog(parent=None, title=u'Первоначальная настройка %s' % TITLE)

        self.dialog.set_size_request(800, -1)
        self.dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK, Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.dialog.set_default_response(Gtk.ResponseType.OK)

        box = self.dialog.get_content_area()

        self.stgrid = LibSettingsEditor(library)
        box.pack_start(self.stgrid.grid, True, True, 0)

    def run(self):
        self.dialog.show_all()

        ret = False

        while True:
            r = self.dialog.run()

            if r == Gtk.ResponseType.OK:
                # settings
                es = self.stgrid.get_data()
                if not es:
                    break

                msg_dialog(self.dialog, u'Ошибка', es, msgtype=Gtk.MessageType.ERROR)
            else:
                break

        self.dialog.hide()

        if r == Gtk.ResponseType.OK:
            self.library.save_settings()
            return True
        else:
            return False


class SettingsDialog():
    PAGE_SETTINGS, PAGE_TAGS = range(2)

    def __init__(self, wparent, library):
        self.library = library
        self.dialog = Gtk.Dialog(parent=wparent, title=u'Настройки')

        self.dialog.set_size_request(800, 600)
        self.dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK, Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.dialog.set_default_response(Gtk.ResponseType.OK)

        box = self.dialog.get_content_area()

        self.pages = Gtk.Notebook()
        self.pages.set_border_width(WIDGET_SPACING)
        box.pack_start(self.pages, True, True, 0)

        self.editors = [] # (editor, pagenumber) !!!

        def add_editor_page(page, page_id):
            page.parentwnd = self.dialog
            self.editors.append((page, page_id))

            pagebox = Gtk.VBox(spacing=WIDGET_SPACING)
            pagebox.set_border_width(WIDGET_SPACING)
            pagebox.pack_start(page.container, True, True, 0)

            if page.FIELD_COMMENT:
                pagebox.pack_end(create_aligned_label(page.FIELD_COMMENT), False, False, 0)

            self.pages.append_page(pagebox, Gtk.Label(page.FIELD_NAME))

        #
        # settings
        #
        self.stgrid = LibSettingsEditor(library)
        add_editor_page(self.stgrid, self.PAGE_SETTINGS)

        #
        # tags
        #
        self.tageditor = TagNameEditor(self.library)
        add_editor_page(self.tageditor, self.PAGE_TAGS)

    def run(self):
        for editor, pagenum in self.editors:
            editor.set_data()

        self.dialog.show_all()
        while True:
            r = self.dialog.run()

            if r == Gtk.ResponseType.OK:
                errorstrs = []
                errorpages = []
                errorcritical = 0

                # settings
                es = self.stgrid.get_data()
                if es:
                    errorstrs.append(es)
                    errorpages.append(self.PAGE_SETTINGS)
                    errorcritical += 1

                # lists
                for editor, pagenum in self.editors:
                    es = editor.validate_data()
                    if es:
                        errorstrs.append(u'Поле "%s": %s' % (editor.FIELD_NAME, es))
                        errorpages.append(pagenum)
                        if editor.CRITICAL:
                            errorcritical += 1

                if errorstrs:
                    self.pages.set_current_page(errorpages[0])

                    if not errorcritical:
                        errorstrs.append(u'\n"ОК"\t\t- сохранить как есть\n"Отмена"\t- продолжить редактирование.')

                    msgt = u'\n'.join(errorstrs)

                    er = msg_dialog(self.dialog, self.dialog.get_title(), msgt,
                        Gtk.MessageType.ERROR if errorcritical else Gtk.MessageType.WARNING,
                        Gtk.ButtonsType.OK_CANCEL if not errorcritical else Gtk.ButtonsType.OK)

                    if er == Gtk.ResponseType.CANCEL:
                        continue

                if not errorcritical:
                    # пихаем данные в БД только если нет критических ошибок во ВСЕХ полях
                    for editor, pn in self.editors:
                        editor.get_data()

                    break
            else:
                break

        self.dialog.hide()

        if r == Gtk.ResponseType.OK:
            self.library.save_genre_names()
            self.library.save_settings()
            return True
        else:
            return False


def main():
    from flibcrutch import Library

    print('* init library')
    library = Library()
    lse = library.load_settings()
    if lse:
        print('library settings load error:', lse)

    lse = library.validate_settings()
    if lse:
        print('library validate settings error:', lse)

    print(library)

    """library.load()"""
    if InitialSettingsDialog(library).run():
        print(library.libraryRootDir)
        print(library.libraryIndexFile)
    #v = SettingsDialog(None, library).run()
    #print('settings dialog returns', v)

    print(library)
    return 0

if __name__ == '__main__':
    exit(main())
