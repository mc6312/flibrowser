#!/usr/bin/python3
# -*- coding: utf-8 -*-

""" flibrowser.py

    Copyright 2014..2017 MC-6312 <mc6312@gmail.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>."""

from fbcommon import *
from gi.repository import Gtk, Gdk, GObject, Pango, GLib
from gi.repository.GdkPixbuf import Pixbuf
from flibcrutch import *
from fbtemplates import *
from fbsettings import SettingsDialog, InitialSettingsDialog
import fbabout
import re, random
import os.path, sys


# для отладки, чтоб не грузить БД в 100500 книжек (которой может и нет вовсе на момент отладки)
USEFAKELIBRARY = True


# нашевсё
library = Library()


if USEFAKELIBRARY:
    from fbfakelib import fill_fake_library
    print(u'Вынимательно! Отладка с фальшивой библиотекой!')

    fill_fake_library(library)


DATE_FORMAT = u'%x'


class FilterEntry():
    """Свалка виджетов для ввода регекспа фильтрации.
    Умеет показывать иконками правильность ввода регулярного
    выражения.

    entry   - виджет поля ввода
    image   - виджет отображения иконки
    regex   - скомпилированное регулярное выражение
              (если выражение введено и правильное),
              иначе None"""

    EMPTY = 'dialog-question'
    VALID = 'gtk-yes'
    INVALID = 'gtk-no'

    ICON_SIZE = Gtk.IconSize.BUTTON

    def search_regexp(self, s):
        """если выражение не указано - возвращаем True, т.к. отсутствие
        выражения соответствует выражению .*"""

        return True if not self.pattern else bool(self.regex.search(s))

    def search_text(self, s):
        #print(u'"%s", %d' % (s, s.lower().find(self.pattern)))
        return s.lower().find(self.pattern) >= 0

    def set_status_icon(self, iconname):
        #print('set_status_icon', iconname)
        if not iconname:
            iconname = self.EMPTY

        self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, iconname)

    def chkisregexp_toggled(self, cb, data=None):
        self.isregex = self.chkisregexp.get_active()

    def entry_icon_pressed(self, entry, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            self.validate_pattern()

    def __init__(self, grid, rowlabel):
        """grid - экземпляр LabeledGrid,
        rowlabel - самый левый виджет в строке grid, в которую пихаем остальное."""

        def ttwg(w, ttt):
            w.set_tooltip_text(ttt)
            return w

        #
        self.entry = Gtk.Entry()
        self.entry.set_activates_default(True) # чтоб дефолтная кнопка в окне работала
        self.entry.connect('icon_release', self.entry_icon_pressed)
        grid.append_col(self.entry, True)

        rowlabel.set_mnemonic_widget(self.entry)

        #
        self.set_status_icon(self.EMPTY)

        #
        """self.btnclear = ttwg(Gtk.Button.new_from_icon_name('edit-clear', self.ICON_SIZE), u'Очистить поле')
        self.btnclear.connect('clicked', lambda w: self.entry.set_text(''))
        grid.append_col(self.btnclear)"""

        #
        self.chkisregexp = ttwg(Gtk.CheckButton(u'RE'), u'В поле регулярное выражение')
        self.chkisregexp.connect('toggled', self.chkisregexp_toggled)
        grid.append_col(self.chkisregexp)

        self.isregex = False
        self.pattern = None
        self.regex = None
        self.searchfunc = self.search_text

    def reset(self):
        """Сброс полей"""

        self.entry.set_text(u'')
        self.set_status_icon(None)
        self.regex = None

    def filter_pattern(self, s):
        """Фильтрация строки-шаблона (напр. от нежелательных символов).
        Вызывается из validate_pattern(), если шаблон - обычная строка
        (для регулярных выражений НЕ вызывается).
        Метод при необходимости перекрывается классом-потомком."""

        return s

    def validate_pattern(self):
        """Компиляция выражения из поля ввода, установка
        иконки в зависимости от результата компиляции."""

        t = self.entry.get_text().strip()
        self.pattern = None
        self.searchfunc = None

        if not t:
            # выражения нет
            self.regex = None
            self.pattern = None
            sti = self.EMPTY
            rok = True
        else:
            try:
                if self.isregex:
                    self.regex = re.compile(t, re.UNICODE|re.IGNORECASE)
                    self.pattern = t
                    self.searchfunc = self.search_regexp
                else:
                    self.regex = None
                    self.pattern = self.filter_pattern(t.lower())
                    #print self.pattern
                    self.searchfunc = self.search_text

                sti = self.VALID
                rok = True
            except re.error:
                self.regex = None
                sti = self.INVALID
                rok = False

        self.set_status_icon(sti)

        return rok


class AuthorFilterEntry(FilterEntry):
    def filter_pattern(self, s):
        """Для поля ввода имени автора - удаление некоторых нежелательных
        символов."""

        return ''.join(filter(lambda c: c not in ',;', s))


class DateChooser():
    def __init__(self, labtxt):
        self.date = None
        self.oncheckboxtoggled = None

        self.container = Gtk.HBox(spacing=WIDGET_SPACING)

        self.checkbox = Gtk.CheckButton.new_with_label(labtxt)
        self.container.pack_start(self.checkbox, False, False, 0)

        # дабы было для чего set_sensitive() вызывать
        self.ctlbox = Gtk.HBox(spacing=WIDGET_SPACING // 2)
        self.ctlbox.set_border_width(WIDGET_SPACING // 2)
        self.container.pack_start(self.ctlbox, False, False, 0)

        self.display = Gtk.Label()
        self.display.set_width_chars(10)
        #set_widget_style(self.display, b'GtkWidget { border-style:inset; border-width:2px; border-radius:3 }')
        #set_widget_style(self.display, b'GtkWidget { border:1pt inset }')
        self.ctlbox.pack_start(self.display, False, False, 0)

        self.dropbtn = Gtk.Button('...')
        set_widget_style(self.dropbtn, b'GtkWidget { padding:4pt }')

        self.ctlbox.pack_end(self.dropbtn, False, False, 0)

        self.chooserwnd = Gtk.Popover.new(self.dropbtn)
        self.chooserwnd.set_transitions_enabled(False)

        cwvbox = Gtk.VBox(spacing=WIDGET_SPACING)
        self.chooserwnd.add(cwvbox)

        self.dropbtn.connect('clicked', self.drop_chooser)

        self.calendar = Gtk.Calendar()
        self.calendar.connect('day-selected-double-click', self.day_selected)

        cwvbox.pack_start(self.calendar, False, False, 0)

        self.checkbox.connect('toggled', self.__checkbox_toggled)

        #
        self.calendar.connect('key-release-event', self.key_released)

        # !!
        self.day_selected(None)
        self.checkbox_toggled()

    def key_released(self, widget, event, data=None):
        if event.keyval == Gdk.KEY_Return:
            self.day_selected(None)
            return True
        elif event.keyval == Gdk.KEY_Escape:
            self.chooserwnd.hide()
            return True

        return False

    def set_sensitive(self, v):
        self.container.set_sensitive(v)

    def checkbox_toggled(self):
        self.ctlbox.set_sensitive(self.checkbox.get_active())

    def __checkbox_toggled(self, chk, data=None):
        self.checkbox_toggled()

        if callable(self.oncheckboxtoggled):
            self.oncheckboxtoggled()

    def day_selected(self, cln, data=None):
        d, m, y = self.calendar.get_date()
        # вынимание - месяц тут от 0!
        self.date = datetime.date(d, m + 1, y)
        self.display.set_text(self.date.strftime(DATE_FORMAT))
        self.chooserwnd.hide()

    def drop_chooser(self, btn, data=None):
        self.chooserwnd.show_all()


class MainWndSettings(Settings):
    WINDOW_X = 'window.x'
    WINDOW_Y = 'window.y'
    WINDOW_W = 'window.w'
    WINDOW_H = 'window.h'
    WINDOW_MAX = 'window.max'

    EXTRACT_FNAME_TEMPLATE = 'extract.filename_template'
    EXTRACT_PACK = 'extract.pack'

    FILTER_IS_REGEXP = 'filter.%s.is_regexp'

    FILTER_AUTHOR = 'author'
    FILTER_TITLE = 'title'
    FILTER_SERIES = 'series'
    FILTER_FNAMES = 'filenames'

    FILTER_AUTHOR_REGEXP = FILTER_IS_REGEXP % FILTER_AUTHOR
    FILTER_TITLE_REGEXP = FILTER_IS_REGEXP % FILTER_TITLE
    FILTER_SERIES_REGEXP = FILTER_IS_REGEXP % FILTER_SERIES
    FILTER_FNAMES_REGEXP = FILTER_IS_REGEXP % FILTER_FNAMES

    VALID_KEYS = {WINDOW_X:int, WINDOW_Y:int, WINDOW_W:int, WINDOW_H:int, WINDOW_MAX:bool,
        EXTRACT_FNAME_TEMPLATE:str, EXTRACT_PACK:bool,
        FILTER_AUTHOR_REGEXP:bool, FILTER_TITLE_REGEXP:bool, FILTER_SERIES_REGEXP:bool,
        FILTER_FNAMES_REGEXP:bool}

    DEFAULTS = {WINDOW_X:None, WINDOW_Y:None, WINDOW_W:800, WINDOW_H:600, WINDOW_MAX:False,
        EXTRACT_FNAME_TEMPLATE:'', EXTRACT_PACK:False,
        FILTER_AUTHOR_REGEXP:False, FILTER_TITLE_REGEXP:False, FILTER_SERIES_REGEXP:False,
        FILTER_FNAMES_REGEXP:False}


class MainWnd():
    """Основное междумордие"""

    COL_BOOKID, COL_AUTHOR, COL_TITLE, COL_SERIES, COL_SERNO, COL_GENRES, COL_SIZE, COL_FORMAT, COL_DATE = range(9)

    COLID_TO_TTCOLID = {COL_AUTHOR:COL_AUTHOR,
        COL_TITLE:COL_TITLE,
        COL_SERIES:COL_SERIES,
        COL_SERNO:COL_SERIES,
        COL_GENRES:COL_GENRES,
        COL_SIZE:COL_GENRES,
        COL_FORMAT:COL_FORMAT,
        COL_DATE:COL_GENRES}

    def load_ui_state(self):
        self.uistate.load()

        #print(self.uistate.cfg)

        # window pos/size
        if self.uistate.cfg[self.uistate.WINDOW_X] is not None:
            self.window.move(self.uistate.cfg[self.uistate.WINDOW_X], self.uistate.get_value(self.uistate.WINDOW_Y))

        self.window.resize(self.uistate.cfg[self.uistate.WINDOW_W], self.uistate.get_value(self.uistate.WINDOW_H))

        #if self.uistate.cfg[self.uistate.WINDOW_MAX]:
        #    self.window.maximize()
        """Так как window.is_maximized() возвращает прошлогоднее значение, а не актуальное,
        то хрен его знает, как _правильно_ сохранять состояние развёрнутости окна.
        А потому - при загрузке это значение пока не используем.
        Кому сильно надо - окошко руками отмасштабирует."""

        # extract controls
        self.bookfntemplate.set_text(self.uistate.get_value(self.uistate.EXTRACT_FNAME_TEMPLATE))
        self.bookunpzipchk.set_active(self.uistate.get_value(self.uistate.EXTRACT_PACK))

        # search field parameters
        for fevname in self.filters.keys():
            self.filters[fevname].chkisregexp.set_active(self.uistate.get_value(self.uistate.FILTER_IS_REGEXP % fevname))

        # загружаем шаблоны имени файла
        self.load_book_fn_templates()

    def update_ui_state(self, pos=False, ctrls=False):
        """Запоминает текущее состояние окна и/или виджетов.
        pos     - bool  запомнить размер и положение,
        ctrls   - bool  запомнить состояние кнопок."""

        # window pos/size
        if pos:
            wm = self.window.is_maximized()
            self.uistate.cfg[self.uistate.WINDOW_MAX] = wm
            # состояние maximized сохраняем, но не используем. см. load_ui_state()

            #if not wm: # см. там же
            wx, wy = self.window.get_position()
            self.uistate.cfg[self.uistate.WINDOW_X] = wx
            self.uistate.cfg[self.uistate.WINDOW_Y] = wy

            ww, wh = self.window.get_size()
            self.uistate.cfg[self.uistate.WINDOW_W] = ww
            self.uistate.cfg[self.uistate.WINDOW_H] = wh

        if ctrls:
            # extract controls
            self.uistate.cfg[self.uistate.EXTRACT_FNAME_TEMPLATE] = self.bookfntemplate.get_text().strip()
            self.uistate.cfg[self.uistate.EXTRACT_PACK] = self.bookunpzipchk.get_active()

            # search field parameters
            for fevname in self.filters.keys():
                self.uistate.cfg[self.uistate.FILTER_IS_REGEXP % fevname] = self.filters[fevname].chkisregexp.get_active()

    def save_ui_state(self):
        #print(self.uistate.cfg)

        self.uistate.save()

        #
        # сохраняем шаблоны имени файла
        #
        self.save_book_fn_templates()

    def load_book_fn_templates(self):
        if self.templatesFileName and os.path.exists(self.templatesFileName):
            self.bookfntemplatecbox.remove_all()

            with open(self.templatesFileName, 'r', encoding=IOENCODING) as f:
                for ixl, s in enumerate(f, 1):
                    s = s.strip()
                    if s:
                        if len(s) > BookFileNameTemplate.MAX_LENGTH:
                            print(u'Слишком длинная строка #%d в файле "%s", пропускаем...' % (ixl, self.templatesFileName))
                            continue

                        self.bookfntemplatecbox.append_text(s)

    def save_book_fn_templates(self):
        def __save_template_str(model, path, itr, fobj):
            s = model.get(itr, 0)
            fobj.write(u'%s\n' % s[0])

            return False

        if self.templatesFileName:
            with open(self.templatesFileName, 'w+', encoding=IOENCODING) as f:
                self.bookfntemplatecbox.get_model().foreach(__save_template_str, f)

    def append_book_fn_template(self, tplstr):
        # внимание! проверку на повтор присобачу потом!
        if tplstr:
            self.bookfntemplatecbox.append_text(tplstr)

    def destroy(self, widget, data=None):
        self.update_ui_state(ctrls=True) # только состояние кнопок - потому что размер окна здесь уже неправильный
        self.save_ui_state()
        Gtk.main_quit()

    def update_book_list(self, lstbookids=[]):
        """Заполнение TreeView отсортированным списком найденных книг
        (если список не пуст.)"""

        #print u'update_book_list: start'

        self.booklist.clear()

        def book_sort_key(bookid):
            bnfo = library.books[bookid]

            # порядок сортировки: цикл, номер в цикле, автор, название

            #print('series: %s, serno: %s, aname: %s, title: %s' % (type(library.get_series_name(bnfo.series)),
            #    type(bnfo.serno), type(library.authors[bnfo.authorid].aname), type(bnfo.title)))

            return (u'%s%.5d%s%s' % (library.get_series_name(bnfo.series), bnfo.serno,
                library.authors[bnfo.authorid].aname, bnfo.title)).upper()

        #print u'update_book_list: sort and update'
        #print(type(lstbookids))

        now = datetime.datetime.now().date()

        filterbymindate = self.mindatechooser.checkbox.get_active()
        filtermindate = self.mindatechooser.date
        filterbymaxdate = self.maxdatechooser.checkbox.get_active()
        filtermaxdate = self.maxdatechooser.date

        if lstbookids:
            self.booklistview.set_model(None)

            # т.к. в пыхтоне 3 cmp оторвато, сортируем через жопу:
            # 1. создаём временный список из кортежей (bookid, 'нормализованная строка сортировки')
            # 2. сортируем временный список
            # 3. забираем из него взад bookids

            for bookid, _tmpkey in sorted(map(lambda bookid: (bookid, book_sort_key(bookid)), lstbookids), key=lambda r: r[1]):
                bnfo = library.books[bookid]

                # вот тут - вкрячиваем фильтрацию по дате
                # по уму надо бы ее вставлять в основную фильтрацию, но тогда придется громоздить костыли в ф-и случайного выбора
                if filterbymindate:
                    if bnfo.date < filtermindate:
                        continue

                    if filterbymaxdate:
                        if bnfo.date > filtermaxdate:
                            continue

                # COL_BOOKID, COL_AUTHOR, COL_TITLE, COL_SERIES, COL_SERNO, COL_GENRES, COL_SIZE, COL_FORMAT, COL_DATE

                self.booklist.append((bnfo.bookid, library.authors[bnfo.authorid].aname, bnfo.title,
                    library.get_series_name(bnfo.series),
                    str(bnfo.serno) if bnfo.serno else u'',
                    library.get_book_tags(bnfo),
                    kilobytes_str(bnfo.fsize),
                    '?' if not bnfo.format else bnfo.format.upper(),
                    u'%s <span color="%s">●</span>' % (bnfo.date.strftime(DATE_FORMAT), get_book_age_color(now, bnfo.date))))

            self.booklistview.set_model(self.booklist)
            self.booklistview.set_search_column(2)
            self.booklistcount = len(lstbookids)
        else:
            self.booklistcount = 0

        #print u'update_book_list: finalize'
        self.labbookcount.set_label(u'%d' % self.booklistcount)

        self.btnrandomchoicefnd.set_sensitive(self.booklistcount != 0)

        self.update_book_panel()

    def update_book_panel(self):
        """Обновление содержимого панели информации о выбранной в списке
        книги. Подробная информация (на текущий момент - только список
        жанров, ибо индекс от MyHomeLib ничего особо полезного не содержит)
        отображается только в случае, если выбрана _одна_ книга,
        иначе показываем только кол-во выбранных книг."""

        if self.bookids:
            #bnfo = library.authors[self.aid].books[self.bookid]
            #btt = u'%s:%s' % (library.bundles[bnfo.bundle], bnfo.filename)

            bcnt = len(self.bookids)

            tags = set()
            for bookid in self.bookids:
                tags.update(library.books[bookid].tags)

            bupk = True
        else:
            bcnt = 0
            bupk = False

        self.selbookcount.set_text(str(bcnt) if bcnt else u'ни одной')

        for widget in (self.bookextractbtn, self.mnuitemextract,
                       self.mnuitemfoundauthortosearch, self.mnuitemfoundtitletosearch, self.mnuitemfoundseriestosearch):
            widget.set_sensitive(bupk)

    def blistview_selected(self, sel, data=None):
        """Обработка события выбора элемента(ов) в списке книг"""

        rows = self.booklistviewsel.get_selected_rows()[1]

        if rows:
            self.bookids = list(map(lambda ix: self.booklist.get_value(self.booklist.get_iter(ix), 0), rows))
        else:
            self.bookids = []

        self.update_book_panel()

    def btnunpkdir_clicked(self, data=None):
        """Выбор каталога, куда извлекать книги"""

        dlg = Gtk.FileChooserDialog(u'Выбор каталога', self.window, Gtk.FileChooserAction.SELECT_FOLDER,
             (Gtk.STOCK_CANCEL, Gtk.ResponseType.REJECT, Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT))
        dlg.set_current_folder(library.extractDir)

        if dlg.run() == Gtk.ResponseType.ACCEPT:
            library.extractDir = dlg.get_current_folder()
            self.txtextractpath.set_text(library.extractDir)

        dlg.destroy()

    def filter_reset(self):
        """Сброс фильтра поиска"""

        for en in self.filters.values():
            en.reset()

        self.update_book_list()

    def filter_apply(self):
        """Поиск книг фильтром"""

        badpat = 0 # кол-во недопустимых шаблонов
        emptypat = 0
        totalpat = len(self.filters)

        for en in self.filters.values():
            if not en.validate_pattern():
                badpat += 1
            elif not en.pattern:
                emptypat += 1

        #print en.pattern #.encode('cp866') #wantuz!

        if emptypat == totalpat:
            self.show_task(u'Не указаны образцы для поиска')
            return

        # запускаем фильтрацию только если нет неправильных шаблонов
        # в остальных случаях просто ничего не делаем
        #print 'badpat', badpat

        def _filterfunc(bnfo):
            if self.fltrauthorentry.searchfunc and not self.fltrauthorentry.searchfunc(library.authors[bnfo.authorid].aname):
                return False

            if self.fltrtitleentry.searchfunc and not self.fltrtitleentry.searchfunc(bnfo.title):
                return False

            if self.fltrseriesentry.searchfunc:
                if not bnfo.series:
                    if not self.fltrseriesentry.searchfunc(u''):
                        # потому что в условиях поиска может быть регексп '.*'
                        # и в этом случае "нет названия сериала" как бы с таким регекспом совпадает
                        # а при поиске по простой строке пустое название правильно отбросится
                        return False
                elif not self.fltrseriesentry.searchfunc(library.series[bnfo.series]):
                    return False

            if self.fltrfnamesentry.searchfunc and not self.fltrfnamesentry.searchfunc(bnfo.filename):
                return False

            return True

        if badpat:
            msg_dialog(self.window, u'Поиск книг', u'Неправильный шаблон поиска')
        else:
            self.filter_books(_filterfunc)

    def filter_books(self, filterfunc):
        """Подготавливает междумордие и фильтрует книги.
        filterfunc - функция отбора (см. flibcrutch.Library.filter)."""

        em = u''

        self.begin_task(u'Поиск книг...')
        try:
            blist = library.filter(filterfunc, self.progress_callback)

            #print(type(blist))
            if not blist:
                em = u'По указанным признакам ничего не нашлось'
            else:
                self.show_task(u'Сортировка...')
                self.update_book_list(blist)
                em = u''

        finally:
            self.end_task(em)

    def extract_books(self):
        """Извлечение выбранных в списке книг"""

        self.begin_task(u'Извлечение книг...')
        try:
            em = u''
            ei = Gtk.MessageType.WARNING
            try:
                #raise KeyError, u'проверка'
                tplstr = self.bookfntemplate.get_text().strip()
                fntemplate = BookFileNameTemplate(library, tplstr)
                # шаблонилка не рухнула, шаблон не пустой и правильный - добавляем его в комбобокс
                if tplstr:
                    self.append_book_fn_template(tplstr)

                pkzip = self.bookunpzipchk.get_active()

                em = library.extract_books(self.bookids, fntemplate, pkzip, callback=self.progress_callback)
                #print(em)
                #raise Exception('test')

            except Exception as ex:
                if em:
                    em += u'\n'
                elif em is None:
                    em = u''

                exs = str(ex)
                em += exs if exs else ex.__class__.__error__
                ei = Gtk.MessageType.ERROR

            if em:
                msg_dialog(self.window, u'Извлечение книг', em, ei)
        finally:
            self.end_task()

    def select_book(self, ix):
        """Выбор строки ix в списке найденных книг"""

        self.booklistviewsel.unselect_all() # ибо у списка установлен режим множественного выделения!
        self.booklistviewsel.select_path(ix)

    def random_choice_from_all(self):
        if library.books:
            bookid = random.choice(list(library.books.keys())) # вот блин спасибо афтарам пыхтона, что dict.keys() нельзя использовать как список...
            self.update_book_list([bookid])
            self.select_book(0)
        else:
            msg_dialog(self.window, u'Опаньки...', u'Выбирать-то не из чего. Библиотека пустая.')

    def random_choice_from_found(self):
        if self.booklistcount == 0:
            self.random_choice_from_all()
        else:
            self.select_book(random.randrange(self.booklistcount))

    def random_choice_from_authors(self):
        if library.authors:
            author = random.choice(list(library.authors.values()))
            self.update_book_list(author.books)
        else:
            self.random_choice_from_all()

    def task_events(self):
        # даем прочихаться междумордию
        while Gtk.events_pending():
            Gtk.main_iteration()#False)

    def begin_task(self, msg):
        self.ctlvbox.set_sensitive(False)
        self.show_task(msg)

    def show_task(self, msg):
        self.labmsg.set_text(msg)
        self.task_events()

    def end_task(self, msg=None):
        if not msg:
            msg = u' '

        self.labmsg.set_text(msg)
        self.progbar.set_fraction(0.0)
        self.ctlvbox.set_sensitive(True)

    def progress_callback(self, fraction):
        self.progbar.set_fraction(fraction)
        self.task_events()
        #print(fraction)

    def library_load(self):
        self.begin_task(u'Загрузка библиотеки...')
        em = None
        try:
            try:
                #raise KeyError, u'проверка'
                if not USEFAKELIBRARY:
                    library.load(self.progress_callback)

                self.labbooktotal.set_text(u'(всего в библиотеке - %d)' % len(library.books))

            except Exception as ex:
                msg_dialog(self.window, u'Загрузка библиотеки',
                    u'%s\n\nВероятно, библиотека повреждена или в настройках указан неправильный путь к библиотеке' % ex.args[0] if ex.args[0] else ex.__class__.__name,
                    Gtk.MessageType.ERROR)
                #exit(1)
        finally:
            self.end_task(em)

    def wnd_configure_event(self, wnd, event):
        """Сменились размер/положение окна"""

        self.update_ui_state(pos=True)

    def about_dialog(self, data=None):
        self.dlgabout.run()

    def settings_dialog(self, data=None):
        if self.dlgsettings.run():
            self.filter_reset()
            self.library_load()

    def setup_window_icon(self):
        LOGO_SIZE = 128

        iconpath = os.path.join(library.appDir, u'flibrowser.svg')

        try:
            self.window.set_icon_from_file(iconpath)
            self.logotype = Pixbuf.new_from_file_at_size(iconpath, LOGO_SIZE, LOGO_SIZE)
        except GLib.GError:
            print(u'Не удалось загрузить файл изображения "%s"' % iconpath)
            self.window.set_icon_name('gtk-find')
            self.logotype = self.window.render_icon_pixbuf(Gtk.STOCK_FIND, Gtk.IconSize.DIALOG)

    def blv_mouse_moved(self, lv, event):
        r = self.booklistview.get_path_at_pos(event.x, event.y)
        if r is not None:
            mcolid = self.COLID_TO_TTCOLID[self.colrefs[r[1]]]

            if self.booklistview.get_tooltip_column() != mcolid:
                self.booklistview.set_tooltip_column(mcolid)

        return False

    def blv_mouse_pressed(self, tv, event, data=None):
        if event.button == 3: # right button
            self.mnuBLVContext.popup(None, None, None, None, event.button, event.time)

        return False

    def field_to_search(self, filterentry, fieldfunc):
        fs = set()

        for bookid in self.bookids:
            s = fieldfunc(bookid)
            if s:
                fs.add(s)

        fs = list(fs)

        if fs:
            if len(fs) == 1:
                s = fs[0]
                isre = False
            else:
                s = u'(%s)' % u'|'.join(fs)
                isre = True

            filterentry.entry.set_text(s)
            filterentry.chkisregexp.set_active(isre)

    def found_author_to_search(self):
        self.field_to_search(self.fltrauthorentry, lambda bookid: library.authors[library.books[bookid].authorid].aname)

    def found_title_to_search(self):
        self.field_to_search(self.fltrtitleentry, lambda bookid: library.books[bookid].title)

    def found_series_to_search(self):
        self.field_to_search(self.fltrseriesentry, lambda bookid: library.series[library.books[bookid].series])

    def chkusedatefilter_toggled(self):
        self.maxdatechooser.set_sensitive(self.mindatechooser.checkbox.get_active())

    def bookfname_template_help(self, btn, data=None):
        msg_dialog(self.window, u'Шаблон имени файла', BookFileNameTemplate.TEMPLATE_HELP, msgtype=Gtk.MessageType.INFO)

    def __init__(self):
        """Инициализация междумордия и прочего"""

        self.uistate = MainWndSettings(os.path.join(library.cfgDir, u'uistate'))
        self.templatesFileName = os.path.join(library.cfgDir, u'templates')

        self.window = Gtk.ApplicationWindow(Gtk.WindowType.TOPLEVEL)
        #self.window.connect('delete_event', self.delete_event)
        self.window.connect('configure_event', self.wnd_configure_event)
        self.window.connect('destroy', self.destroy)

        self.window.set_title(u'%s v%s%s' % (TITLE, VERSION,
            u' [Внимание - отладочная версия]' if USEFAKELIBRARY else ''))

        self.logotype = None
        self.setup_window_icon()

        self.window.set_size_request(1024, 768)
        self.window.set_border_width(WIDGET_SPACING)

        #
        #
        self.dlgabout = fbabout.AboutDialog(self.window, library, self.logotype)
        self.dlgsettings = SettingsDialog(self.window, library)
        #
        #

        rootvbox = Gtk.VBox(spacing=WIDGET_SPACING)
        self.window.add(rootvbox)

        self.ctlvbox = Gtk.VBox(spacing=WIDGET_SPACING)
        rootvbox.pack_start(self.ctlvbox, True, True, 0)

        #
        # главное меню
        #
        actions = Gtk.ActionGroup('ui')
        actions.add_actions((('file', None, u'Файл', None, None, None),
            ('fileAbout', Gtk.STOCK_ABOUT, None, None, None, self.about_dialog),
            ('fileSettings', None, u'Настройки', None, None, self.settings_dialog),
            ('fileExit', Gtk.STOCK_QUIT, None, '<Control>q', None, self.destroy),
            #
            ('books', None, u'Книги', None, None, None),
            ('booksRandomFromAll', None, u'Выбрать случайную книгу', '<Control>1', None, lambda w: self.random_choice_from_all()),
            ('booksRandomFromAuthors', None, u'Выбрать случайного автора', '<Control>2', None, lambda w: self.random_choice_from_authors()),
            ('booksRandomFromFound', None, u'Выбрать случайную книгу из найденных', '<Control>3', None, lambda w: self.random_choice_from_found()),
            ('booksFind', Gtk.STOCK_FIND, None, '<Control>f', None, lambda w: self.filter_apply()),
            ('booksClear', Gtk.STOCK_CLEAR, None, '<Control>l', None, lambda w: self.filter_reset()),
            ('booksExtract', None, u'Извлечь выбранные', '<Control>e', None, lambda w: self.extract_books()),
            #
            ('blcontext', None, u'Дополнительно', None, None, None),
            ('foundAuthorToSearch', None, u'Искать этого автора', '<Control><Shift>a', None, lambda w: self.found_author_to_search()),
            ('foundTitleToSearch', None, u'Искать с таким же названием', '<Control><Shift>t', None, lambda w: self.found_title_to_search()),
            ('foundSeriesToSearch', None, u'Искать с таким же названием цикла', '<Control><Shift>s', None, lambda w: self.found_series_to_search()),
            ))

        uimgr = Gtk.UIManager()
        uimgr.insert_action_group(actions)
        uimgr.add_ui_from_string(u'''<ui>
    <menubar>
        <menu name="mnuFile" action="file">
            <menuitem name="mnuFileAbout" action="fileAbout"/>
            <menuitem name="mnuFileSettings" action="fileSettings"/>
            <separator/>
            <menuitem name="mnuFileExit" action="fileExit"/>
        </menu>
        <menu name="mnuBooks" action="books">
            <menuitem name="mnuBooksRandomFromAll" action="booksRandomFromAll"/>
            <menuitem name="mnuBooksRandomFromAuthors" action="booksRandomFromAuthors"/>
            <menuitem name="mnuBooksRandomFromFound" action="booksRandomFromFound"/>
            <separator/>
            <menuitem name="mnuBooksFind" action="booksFind"/>
            <menuitem name="mnuBooksClear" action="booksClear"/>
            <menuitem name="mnuBooksExtract" action="booksExtract"/>
            <menu name="mnuFoundToSearch" action="blcontext">
                <menuitem name="mnuFoundAuthorToSearch" action="foundAuthorToSearch"/>
                <menuitem name="mnuFoundTitleToSearch" action="foundTitleToSearch"/>
                <menuitem name="mnuFoundSeriesToSearch" action="foundSeriesToSearch"/>
            </menu>
        </menu>
    </menubar>
</ui>''')

        self.mnuitemextract = uimgr.get_widget('/ui/menubar/mnuBooks/mnuBooksExtract')
        self.mnuitemfoundauthortosearch = uimgr.get_widget('/ui/menubar/mnuBooks/mnuFoundToSearch/mnuFoundAuthorToSearch')
        self.mnuitemfoundtitletosearch = uimgr.get_widget('/ui/menubar/mnuBooks/mnuFoundToSearch/mnuFoundTitleToSearch')
        self.mnuitemfoundseriestosearch = uimgr.get_widget('/ui/menubar/mnuBooks/mnuFoundToSearch/mnuFoundSeriesToSearch')

        self.ctlvbox.pack_start(uimgr.get_widget('/ui/menubar'), False, False, 0)
        self.window.add_accel_group(uimgr.get_accel_group())
        #

        self.mnuBLVContext = uimgr.get_widget('/ui/menubar/mnuBooks/mnuFoundToSearch').get_submenu()

        #
        # фильтр
        #
        flfr = Gtk.Frame.new(u'Поиск')
        self.ctlvbox.pack_start(flfr, False, False, 0)

        flgr = LabeledGrid()
        flfr.add(flgr)

        self.filters = {} # для загрузки/сохранения настроек

        def add_filter_entry(txt, cfgvname, fclass=FilterEntry):
            fllab = flgr.append_row(txt)
            fe = fclass(flgr, fllab)
            self.filters[cfgvname] = fe
            return fe

        # фильтр по авторам
        self.fltrauthorentry = add_filter_entry(u'_1. Автор:', self.uistate.FILTER_AUTHOR, AuthorFilterEntry)

        # фильтр по названиям
        self.fltrtitleentry = add_filter_entry(u'_2. Названиe:', self.uistate.FILTER_TITLE)

        # фильтр по циклам
        self.fltrseriesentry = add_filter_entry(u'_3. Цикл:', self.uistate.FILTER_SERIES)

        # фильтр по названиям файлов
        self.fltrfnamesentry = add_filter_entry(u'_4. Имя файла:', self.uistate.FILTER_FNAMES)

        # фильтр по жанрам
        # потом когда-нито

        # кнопки поиска и сброса фильтра
        flhbox = Gtk.HBox(spacing=WIDGET_SPACING)
        flgr.append_row(u'Поиск')
        flgr.append_col(flhbox, True)

        btnfilter = Gtk.Button.new_from_stock(Gtk.STOCK_FIND)
        btnfilter.connect('clicked', lambda b: self.filter_apply())
        btnfilter.set_can_default(True)
        self.window.set_default(btnfilter)
        flhbox.pack_start(btnfilter, False, False, 0)

        btnfilterclear = Gtk.Button.new_from_stock(Gtk.STOCK_CLEAR)
        btnfilterclear.connect('clicked', lambda b: self.filter_reset())
        flhbox.pack_start(btnfilterclear, False, False, 0)

        flhbox.pack_start(Gtk.HSeparator(), False, False, WIDGET_SPACING * 4)

        flhbox.pack_start(Gtk.Label(u'Чего б почитать'), False, False, 0)

        btnrandomchoiceall = Gtk.Button.new_with_mnemonic(u'вообще')
        btnrandomchoiceall.connect('clicked', lambda b: self.random_choice_from_all())
        flhbox.pack_start(btnrandomchoiceall, False, False, 0)

        self.btnrandomchoiceauth = Gtk.Button.new_with_mnemonic(u'из авторов')
        self.btnrandomchoiceauth.connect('clicked', lambda b: self.random_choice_from_authors())
        flhbox.pack_start(self.btnrandomchoiceauth, False, False, 0)

        self.btnrandomchoicefnd = Gtk.Button.new_with_mnemonic(u'из найденного')
        self.btnrandomchoicefnd.connect('clicked', lambda b: self.random_choice_from_found())
        flhbox.pack_start(self.btnrandomchoicefnd, False, False, 0)

        # фильтрация по дате
        flhbox.pack_start(Gtk.HSeparator(), False, False, WIDGET_SPACING * 4)

        self.mindatechooser = DateChooser(u'не старше')
        self.mindatechooser.oncheckboxtoggled = self.chkusedatefilter_toggled
        flhbox.pack_start(self.mindatechooser.container, False, False, 0)

        self.maxdatechooser = DateChooser(u'и не новее')
        flhbox.pack_start(self.maxdatechooser.container, False, False, 0)

        self.maxdatechooser.set_sensitive(False) # возможно, будет изменено загрузкой настроек

        #
        # список найденных книг
        #
        self.bookids = []
        self.booklistcount = 0

        blfrhb = Gtk.HBox(spacing=WIDGET_SPACING)

        bltfrlab = Gtk.Label(u'_5. Книги:')
        bltfrlab.set_use_underline(True)
        blfrhb.pack_start(bltfrlab, False, False, 0)

        self.labbookcount = Gtk.Label()
        blfrhb.pack_start(self.labbookcount, False, False, 0)

        #blfrhb.pack_start(Gtk.VSeparator(), False, False, 0)

        self.labbooktotal = Gtk.Label()
        blfrhb.pack_start(self.labbooktotal, False, False, 0)

        booklistfr = Gtk.Frame()
        booklistfr.set_label_widget(blfrhb)
        self.ctlvbox.pack_start(booklistfr, True, True, 0)

        blvbox = Gtk.VBox(spacing=WIDGET_SPACING)
        blvbox.set_border_width(WIDGET_SPACING)
        booklistfr.add(blvbox)

        self.booklist = Gtk.ListStore(GObject.TYPE_INT64, # bookid
            GObject.TYPE_STRING, # author
            GObject.TYPE_STRING, # title
            GObject.TYPE_STRING, # series
            GObject.TYPE_STRING, # serno
            GObject.TYPE_STRING, # genres
            GObject.TYPE_STRING, # size
            GObject.TYPE_STRING, # format
            GObject.TYPE_STRING) # date

        self.booklistview = Gtk.TreeView(self.booklist)

        self.booklistview.set_grid_lines(Gtk.TreeViewGridLines.VERTICAL)
        self.booklistview.set_rules_hint(True)

        bltfrlab.set_mnemonic_widget(self.booklistview)

        self.colrefs = {} # костыль для определения столбца по координатам
        # ключи - экземпляры Gtk.TreeViewColumn, значения - номера столбцов в self.booklist

        def mktvcol(ctitle, ix, expand, align=0.0, markup=False):
            crt = Gtk.CellRendererText()
            crt.props.xalign = align
            crt.props.ellipsize = Pango.EllipsizeMode.END if expand else Pango.EllipsizeMode.NONE

            aname = 'markup' if markup else 'text'

            col = Gtk.TreeViewColumn(ctitle, crt)
            col.add_attribute(crt, aname, ix)
            #col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            col.set_sizing(Gtk.TreeViewColumnSizing.GROW_ONLY)
            col.set_resizable(expand)
            col.set_expand(expand)

            self.colrefs[col] = ix

            return col

        self.booklistview.append_column(mktvcol(u'Автор', self.COL_AUTHOR, True))
        self.booklistview.append_column(mktvcol(u'Название', self.COL_TITLE, True))
        self.booklistview.append_column(mktvcol(u'Цикл', self.COL_SERIES, True))
        self.booklistview.append_column(mktvcol(u'#', self.COL_SERNO, False, 1.0))
        self.booklistview.append_column(mktvcol(u'Жанры', self.COL_GENRES, True))
        self.booklistview.append_column(mktvcol(u'Размер', self.COL_SIZE, False, 1.0))
        self.booklistview.append_column(mktvcol(u'Формат', self.COL_FORMAT, False, 1.0))

        # date
        datecol = mktvcol(u'Дата', self.COL_DATE, False, 1.0, True)

        self.booklistview.append_column(datecol)

        self.booklistview.connect('motion-notify-event', self.blv_mouse_moved)
        self.booklistview.connect('button-press-event', self.blv_mouse_pressed)
        self.booklistview.set_tooltip_column(self.COL_GENRES)

        blscr = Gtk.ScrolledWindow()
        blscr.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        blscr.set_shadow_type(Gtk.ShadowType.IN)
        blscr.set_overlay_scrolling(False)
        blscr.add(self.booklistview)

        blvbox.pack_start(blscr, True, True, 0)

        self.booklistviewsel = self.booklistview.get_selection()
        self.booklistviewsel.set_mode(Gtk.SelectionMode.MULTIPLE)
        self.booklistviewsel.connect('changed', self.blistview_selected)

        # кол-во выбранных книг
        sbcountbox = Gtk.HBox(spacing=WIDGET_SPACING)
        blvbox.pack_start(sbcountbox, False, False, 0)

        def ltlabel():
            lab = Gtk.Label()
            lab.set_use_underline(False)
            lab.set_alignment(0.0, 0.0)
            lab.set_justify(Gtk.Justification.LEFT)
            lab.set_line_wrap(False)
            lab.set_ellipsize(Pango.EllipsizeMode.END)
            return lab

        sbcountbox.pack_start(Gtk.Label(u'Выбрано книг:'), False, False, 0)

        self.selbookcount = Gtk.Label('0')
        sbcountbox.pack_start(self.selbookcount, False, False, 0)

        # book extract path box
        bookpathbox = Gtk.HBox(spacing=WIDGET_SPACING)
        #bookpathbox.set_border_width(WIDGET_SPACING)
        blvbox.pack_start(bookpathbox, False, False,0)

        self.bookextractbtn = Gtk.Button.new_with_mnemonic(u'_9. Извлечь')
        self.bookextractbtn.set_image(Gtk.Image.new_from_icon_name('gtk-execute', Gtk.IconSize.BUTTON))
        self.bookextractbtn.connect('clicked', lambda w: self.extract_books())
        bookpathbox.pack_start(self.bookextractbtn, False, False, 0)

        btnunpkdir = Gtk.Button(u'в каталог')
        btnunpkdir.connect('clicked', self.btnunpkdir_clicked)
        bookpathbox.pack_start(btnunpkdir, False, False, 0)

        self.txtextractpath = Gtk.Entry()
        self.txtextractpath.set_editable(False)
        #self.txtextractpath.set_ellipsize(Pango.ELLIPSIZE_MIDDLE)
        #self.txtextractpath.set_alignment(0.0, 0.5)
        self.txtextractpath.set_text(library.extractDir)
        bookpathbox.pack_start(self.txtextractpath, True, True, 0)

        #
        # шаблон имени файла
        #
        self.bnftemplate = None

        bookpathbox.pack_start(Gtk.Label(u', назвав файл по шаблону'), False, False, 0)

        self.bookfntemplatecbox = Gtk.ComboBoxText.new_with_entry()
        self.bookfntemplate = self.bookfntemplatecbox.get_child()
        self.bookfntemplate.set_max_length(BookFileNameTemplate.MAX_LENGTH)
        self.bookfntemplate.set_width_chars(25)
        bookpathbox.pack_start(self.bookfntemplatecbox, False, False, 0)

        btnbfntplovr = Gtk.Button('...')
        bookpathbox.pack_start(btnbfntplovr, False, False, 0)

        self.bookfntemplateovr = Gtk.Overlay()
        self.bookfntemplateovr.add_overlay(btnbfntplovr)

        btnbfntemplatehelp = Gtk.Button(u'?')
        btnbfntemplatehelp.connect('clicked', self.bookfname_template_help)
        bookpathbox.pack_start(btnbfntemplatehelp, False, False, 0)

        self.bookunpzipchk = Gtk.CheckButton(u'и сжать ZIP', False)
        self.bookunpzipchk.set_active(False)
        bookpathbox.pack_start(self.bookunpzipchk, False, False, 0)

        #
        self.labmsg = Gtk.Label()
        self.labmsg.set_ellipsize(Pango.EllipsizeMode.END)

        self.progbar = Gtk.ProgressBar()
        #self.progbar.set_show_text(True)
        #self.progbar.set_text(u' ') # шобы высота была с текстовую строку
        rootvbox.pack_end(self.progbar, False, False, 0)

        rootvbox.pack_end(self.labmsg, False, False, 0)

        #!!!
        #self.bookids = [library.books.keys()[0]]
        self.update_book_list()

        self.window.show_all()

        self.load_ui_state()
        self.library_load()

        #!!!
        self.fltrauthorentry.entry.grab_focus()

    def main(self):
        Gtk.main()


#
#
#

def process_command_line():
    global USEFAKELIBRARY

    for arg in sys.argv[1:]:
        if arg == '--fake-library':
            USEFAKELIBRARY = True

#
#
#
def main():
    print('%s %s' % (TITLE, VERSION))
    process_command_line()

    loadSettingsError = library.load_settings()

    if loadSettingsError:
        if InitialSettingsDialog(library).run():
            pass
        else:
            msg_dialog(None, TITLE, loadSettingsError, Gtk.MessageType.ERROR)
            exit(1)

    loadSettingsError = library.validate_settings()
    if loadSettingsError:
        msg_dialog(None, TITLE, loadSettingsError, Gtk.MessageType.ERROR)
        exit(1)

    wndmain = MainWnd()
    wndmain.main()
    return 0


if __name__ == '__main__':
    exit(main())
