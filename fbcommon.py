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


TITLE = u'Flibrowser'
VERSION = u'1.7.3'
COPYRIGHT = u'Copyright 2014..2017 MC-6312'


GTK_VERSION = '3.0'
from gi import require_version
require_version('Gtk', GTK_VERSION) # извращенцы


# отступы между виджетами, дабы не вырвало от пионерского вида гуя
# когда-нибудь надо будет их считать от размеров шрифта, а пока так сойдет
WIDGET_SPACING = 4

# Вынимание! GTK желает юникода!
UI_ENCODING = 'utf-8'


from locale import getdefaultlocale
from sys import getfilesystemencoding


# кодировка файла настроек (и прочего, зависящего от ОС)
# спасибо гнойной венде, где до сих пор 3 кодировки одновременно...
IOENCODING = getdefaultlocale()[1]
if not IOENCODING:
    IOENCODING = getfilesystemencoding()


from gi.repository import Gtk, GObject, Pango
from gi.repository.GdkPixbuf import Pixbuf, Colorspace as GdkPixbuf_Colorspace


BOOK_AGE_COLORS = ('#00FF00',
    '#A8FF00',
    '#B8FF00',
    '#FFFF00',
    '#FFF400',
    '#FFD700',
    '#FFB900',
    '#FF9C00',
    '#FF7A00',
    '#FF5A00',
    '#FF3A00',
    '#FF1B00',
    '#EE2D1A',
    '#E03C2F',
    '#D34A43',
    '#C55958',
    '#B8676D',
    '#AA7681',
    '#9D8496',
    '#8F93AA')

BOOK_AGE_MAX = len(BOOK_AGE_COLORS) - 1



def get_book_age_color(nowdate, bookdate):
    """Возвращает цвет в виде "#RRGGBB", соответствующий "свежести" книги.
    Готовой функции, считающей в месяцах, в стандартной библиотеке нет,
    возиться с точными вычислениями, учитывающими месяцы разной длины
    и високосные года, а также обвешивать софтину зависимостями на
    сторонние библиотеки мне влом, а потому "свежесть" считается
    в четырёхнедельных промежутках от текущей даты (nowdate)."""

    delta = (nowdate - bookdate).days // 28

    if delta < 0:
        # нет гарантии, что в БД лежала правильная дата
        delta = 0
    elif delta > BOOK_AGE_MAX:
        delta = BOOK_AGE_MAX

    return BOOK_AGE_COLORS[delta]

#print(create_book_age_icons())
#exit(0)


def set_widget_style(widget, css):
    dbsp = Gtk.CssProvider()
    dbsp.load_from_data(css) # убейте гномосексуалистов кто-нибудь!
    dbsc = widget.get_style_context()
    dbsc.add_provider(dbsp, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def create_scwindow():
    """Создает и возвращает экземпляр Gtk.ScrolledWindow"""

    scwindow = Gtk.ScrolledWindow()
    scwindow.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scwindow.set_shadow_type(Gtk.ShadowType.IN)

    return scwindow


def create_aligned_label(title, halign=0.0, valign=0.0):
    label = Gtk.Label(title)
    label.set_alignment(halign, valign)
    #label.set_justify(Gtk.Justification.LEFT)
    return label


def create_listview(coltypes, coldefs):
    """Создает и возвращает экземпляры Gtk.TreeView, Gtk.ListStore,
    Gtk.ScrolledWindow и список экземпляров Gtk.CellRenderer*.

    coltypes    - типы данных для столбцов ListStore,
    coldefs     - кортежи вида (индекс, 'название', editable, expand, align), где:
        название    - отображаемое в заголовке название,
        индекс      - номер столбца в coltypes,
        editable    - (булевское) запрет/разрешение редактирования ячейки,
        expand      - (булевское) фиксированная/автоматическая ширина,
        align       - (0.0..1.0) выравнивание содержимого ячейки."""

    liststore = Gtk.ListStore(*coltypes)
    listview = Gtk.TreeView(liststore)
    listview.set_border_width(WIDGET_SPACING)

    scwindow = create_scwindow()
    scwindow.add(listview)

    renderers = []
    #
    for ctitle, ix, editable, expand, align in coldefs:
        ctype = coltypes[ix]
        if ctype == GObject.TYPE_BOOLEAN:
            crt = Gtk.CellRendererToggle()
            crtpar = 'active'
        elif ctype == GObject.TYPE_STRING:
            crt = Gtk.CellRendererText() #!!!
            crt.props.xalign = align
            crt.props.ellipsize = Pango.EllipsizeMode.END if expand else Pango.EllipsizeMode.NONE
            crt.props.editable = editable
            crtpar = 'text'
        elif ctype == Pixbuf:
            crt = Gtk.CellRendererPixbuf()
            crt.props.xalign = align
            crtpar = 'pixbuf'
        else:
            raise ValueError(u'неподдерживаемый тип данных столбца Gtk.ListStore')

        renderers.append(crt)

        col = Gtk.TreeViewColumn(ctitle, crt)
        col.add_attribute(crt, crtpar, ix)
        col.set_sizing(Gtk.TreeViewColumnSizing.GROW_ONLY)
        col.set_resizable(expand)
        col.set_expand(expand)

        listview.append_column(col)

    #
    return listview, liststore, scwindow, renderers


class LabeledGrid(Gtk.Grid):
    """Виджет для таблиц с несколькими столбцами (Label и что-то еще)"""

    def __init__(self):
        Gtk.Grid.__init__(self)

        self.set_row_spacing(WIDGET_SPACING)
        self.set_column_spacing(WIDGET_SPACING)
        self.set_border_width(WIDGET_SPACING)

        self.currow = None # 1й виджет в строке
        self.curcol = None # последний виджет в строке

        self.label_xalign = 0.0
        self.label_yalign = 0.5

    def append_row(self, labtxt):
        """Добавление строки с виджетами.
        labtxt - текст для Label в левом столбце;
        mnemonic - виджет, который должен получать фокус при нажатии
               хоткея, указанного в labtxt (если есть).
        Возвращает экземпляр Label, дабы можно было его скормить grid.attach_next_to()."""

        lbl = Gtk.Label(labtxt)
        lbl.set_alignment(self.label_xalign, self.label_yalign)
        lbl.set_use_underline(True)

        self.attach_next_to(lbl, self.currow, Gtk.PositionType.BOTTOM, 1, 1)
        self.currow = lbl
        self.curcol = lbl

        return lbl

    def append_col(self, widget, expand=False, cols=1, rows=1):
        widget.props.hexpand = expand
        self.attach_next_to(widget, self.curcol, Gtk.PositionType.RIGHT, cols, rows)
        self.curcol = widget


def kilobytes_str(n):
    return u'%gk' % round(n / 1024.0, 1)


def msg_dialog(parent, title, msg, msgtype=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK):
    dlg = Gtk.MessageDialog(parent, 0, msgtype, buttons, msg)
    dlg.set_title(title)
    r = dlg.run()
    dlg.destroy()
    return r

