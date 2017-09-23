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


import os.path

from fbcommon import *

from gi.repository import Gtk, GLib
from gi.repository.GdkPixbuf import Pixbuf


LOGO_SIZE = 256


class AboutDialog():
    def __init__(self, parentwnd, library):
        """Создание и первоначальная настройка.

        parentwnd   - экземпляр Gtk.Window или None
        library     - экземпляр flibcrutch.Library"""

        iconpath = os.path.join(library.appDir, u'flibrowser.svg')

        self.dlgabout = Gtk.AboutDialog(parent=parentwnd)

        try:
            logotype = Pixbuf.new_from_file_at_size(iconpath, LOGO_SIZE, LOGO_SIZE)

            r = Gtk.IconSize.lookup(Gtk.IconSize.DIALOG)
            self.windowicon = Pixbuf.new_from_file_at_size(iconpath, r.width, r.height)
        except GLib.GError:
            print(u'Не удалось загрузить файл изображения "%s"' % iconpath)
            logotype = self.dlgabout.render_icon_pixbuf('gtk-find', Gtk.IconSize.DIALOG)
            self.windowicon = logotype

        self.dlgabout.set_icon(self.windowicon)

        self.dlgabout.set_size_request(-1, 600)
        self.dlgabout.set_copyright(COPYRIGHT)
        self.dlgabout.set_version(VERSION)
        self.dlgabout.set_program_name(TITLE)
        self.dlgabout.set_logo(logotype)

        pathLicense = os.path.join(library.appDir, u'COPYING') # патамушто

        if os.path.exists(pathLicense):
            try:
                with open(pathLicense, 'r') as f:
                    slicense = f.read().strip()
            except OSError:
                slicense = None
        else:
            slicense = None

        self.dlgabout.set_license_type(Gtk.License.GPL_3_0_ONLY)
        self.dlgabout.set_license(slicense if slicense else u'Файл с текстом GPL не найден.\nЧитайте https://www.gnu.org/licenses/gpl.html')

        self.dlgabout.add_credit_section(u'Сляпано во славу', [u'Азатота', u'Йог-Сотота', u'Ктулху', u'Шаб-Ниггурат', u'и прочей кодлы Великих Древних'])
        self.dlgabout.add_credit_section(u'Особая благодарность', [u'Левой ноге автора'])

    def run(self):
        self.dlgabout.show_all()
        self.dlgabout.run()
        self.dlgabout.hide()


def main():
    print('[%s test]' % __file__)
    from flibcrutch import Library
    library = Library()
    er = library.load_settings()
    if er:
        print('load settings:', er)
        return

    AboutDialog(None, library).run()

if __name__ == '__main__':
    exit(main())
