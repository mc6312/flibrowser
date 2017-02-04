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


import flibrowser
import sys
from traceback import format_exception

from gi.repository import Gtk


def main(args):
    try:
        #raise ValueError(u'debug exception')
        flibrowser.main()
    except SystemExit:
        return 0
    except Exception:
        # пытаемся показать ошибку
        etype, evalue, etrace = sys.exc_info()

        etext = u''.join(format_exception(etype, evalue, etrace))

        dlg = Gtk.MessageDialog(None, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, etext)

        dlg.set_title(u'Ошибка')
        dlg.run()
        dlg.destroy()
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))
