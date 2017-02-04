#!/usr/bin/env python
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


import os.path, sys
from fbcommon import IOENCODING


# в жопу ConfigParser! в ём слишком много лишнего, а то, что есть - один фиг требует писания обёрток
class SettingsError(Exception):
    pass


class Settings():
    """Класс для простого файла настроек (без секций и т.п.).
    В случае ошибок его методы генерируют исключение SettingsError."""

    VALID_KEYS = None
    """Если не None: словарь допустимых переменных, где ключи -
       имена переменных, а значения - типы;
       если None: загрузка жрет всё без проверки, считая, что все
       значения - строки;"""

    DEFAULTS = None
    """Если не None: словарь значений по умолчанию."""

    def __init__(self, fpath=None):
        """Инициализация.
        fpath       - полное имя файла для загрузки/сохранения настроек;
        cfg         - значения настроек; если DEFAULTS!=None, заполняется оттуда."""

        self.cfgPath = fpath
        self.cfg = self.DEFAULTS if self.DEFAULTS else {}

    def load(self):
        """Загрузка с проверкой правильности имен и типов переменных."""

        if not os.path.exists(self.cfgPath):
            return

        def str_to_val(vt, vv):
            # костылинг для некоторых типов

            if vt is bool:
                return vv.lower() in (u'1', u'yes', u'true')
            else:
                return vt(vv)

        with open(self.cfgPath, 'r', encoding=IOENCODING) as cfgf:
            for ixl, rs in enumerate(cfgf):
                ixl += 1

                rs = rs.strip()
                if not rs or rs.startswith(u'#'):
                    continue

                rs = rs.split(None, 1)
                if len(rs) != 2:
                    raise SettingsError(u'Отсутствует значение переменной в строке #%d файла "%s"' % (ixl, self.cfgPath))

                kn, kv = rs

                if self.VALID_KEYS:
                    # жрём с некоторыми проверками

                    if kn not in self.VALID_KEYS:
                        print(u'Недопустимое имя переменной "%s" в строке #%d файла "%s"' % (kn, ixl, self.cfgPath), file=sys.stderr)
                        continue

                    try:
                        self.cfg[kn] = str_to_val(self.VALID_KEYS[kn], kv)
                    except ValueError as ex:
                        raise SettingsError(u'Недопустимое значение переменной "%s" в строке #%d файла "%s" (%s)' % (kn, ixl, self.cfgPath, ex.args[0]))
                else:
                    # жрём всё как есть

                    self.cfg[kn] = kv

    def save(self):
        """Сохранение настроек"""

        def val_to_str(v):
            if isinstance(v, str):
                return v
            else:
                return str(v)

        with open(self.cfgPath, 'w+', encoding=IOENCODING) as cfgf:
            for kv in sorted(self.cfg.keys()):
                cfgf.write(u'%s %s\n' % (kv, val_to_str(self.cfg[kv])))

    def get_value(self, vname, defv=None):
        if vname in self.cfg:
            return self.cfg[vname]
        elif defv is None:
            if vname in self.DEFAULTS:
                return self.DEFAULTS[vname]
        else:
            return defv

    def set_value(self, vname, vval):
        self.cfg[vname] = vval
        # правильность vname проверять пока смысла не вижу
