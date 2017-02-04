#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" flibwatch.py

    Copyright 2013 mc6312.dreamwidth.org

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


from sys import argv, getfilesystemencoding, stderr
from os.path import exists as file_exists, expanduser, join as path_join
from os import rename as file_rename, remove as file_remove
from urllib2 import urlopen, URLError
from urlparse import urlsplit
from codecs import open
from hashlib import md5
from collections import namedtuple
import re

cfgFSEncoding = getfilesystemencoding()
cfgHTTPTimeout = 20

cfgUrlRoot = u'http://flibusta.net'

RE_PARAMS = re.IGNORECASE|re.UNICODE|re.MULTILINE|re.DOTALL
rx_html_encoding = re.compile(ur'<meta.+?text\/html;\s+charset=(.+?)"', RE_PARAMS)
rx_book_entry = re.compile(ur"""<a\s+href=["]?\/\w\/\d+["]?>(.+?)<\/a>.*?<a\s+href=["]?(\/\w+?\/\d+\/fb2)["]?>""", RE_PARAMS)

cfgConfigDir = u'.' #expanduser(u'~/config/flibwatch')
cfgUrlListPath = path_join(cfgConfigDir, u'urls')

BOOK_DICT_SEP = u';'
MAX_FEED_FNAME_SIZE = 64
_FNAME_HASH_EDGE = MAX_FEED_FNAME_SIZE - 8


def url_to_file_name(url):
    """Преобразует URL в строку, состоящую только из символов ASCII,
    допустимых для имен файлов, и не длиннее MAX_FEED_FNAME_SIZE символов"""

    def url_char(c):
        o = ord(c)

        if (c not in '.-_=@') and (not c.isalnum()):
            return u'_'
        elif (o >= 33) and (o <= 127):
            return c
        else:
            return u'%x' % o

    p = urlsplit(url)

    s = u''.join(map(url_char, u''.join(filter(None, (p.netloc, p.path, p.query)))))
    if len(s) > MAX_FEED_FNAME_SIZE:
        s = s[:_FNAME_HASH_EDGE] + u'%x' % hash(s)

    return s


def extract_book_dict(url):
    """Скачивает страницу, выковыривает названия и URL книг,
    возвращает словарь, где ключи - URL, а значения - названия."""

    print >>stderr, u'  downloading...'
    try:
        dld = urlopen(url, timeout=cfgHTTPTimeout)
        rawpage = dld.read()

        enc = rx_html_encoding.search(rawpage)
        if enc:
            cp = enc.groups()[0]
        else:
            cp = 'utf-8'

        html = rawpage.decode(cp, 'replace')

        #print u'searching'
        rawbooks = rx_book_entry.findall(html)
        if rawbooks:
            return dict(map(lambda b: (b[1], b[0]), rawbooks))
        else:
            return {}

    except URLError, msg:
        return {}


def load_url_dict(fname):
    """Загружает из файла с именем fname словарь,
    где ключи - url'ы, а значения - названия."""

    ret = {}

    if file_exists(fname):
        with open(fname, 'r', encoding=cfgFSEncoding) as srcf:
            for lix, srcl in enumerate(srcf):
                lix += 1
                srcl = srcl.strip()
                if not srcl:
                    continue

                srcl = filter(None, srcl.partition(BOOK_DICT_SEP))
                if len(srcl) <> 3:
                    raise ValueError, u'invalid number of fields in line #%d of file "%s"' % (lix, fname)

                ret[srcl[0]] = srcl[2]

    return ret


def save_url_dict(fname, bd):
    """Сохраняет файле с именем fname словарь bd,
    где ключи - url'ы, а значения - названия."""

    tmpfn = fname + u'.$$$'
    with open(tmpfn, 'w+', encoding=cfgFSEncoding) as dstf:
        for burl in bd.iterkeys():
            dstf.write(u'%s;%s\n' % (burl, bd[burl]))

    if file_exists(fname):
        file_remove(fname)
    file_rename(tmpfn, fname)


def watch_page(url):
    """Скачивает и разгребает страницу с адресом url,
    ищет там ссылки на новые книги."""

    book_lst_fn = path_join(cfgConfigDir, url_to_file_name(url) + '.lst')

    books = load_url_dict(book_lst_fn)
    dldbooks = extract_book_dict(url)
    delta = set(dldbooks.keys()) - set(books.keys())
    if delta:
        books.update(dldbooks)
        save_url_dict(book_lst_fn, books)

        print >>stderr, u'  new books: %d' % len(delta)
        for du in delta:
            print cfgUrlRoot + du
    else:
        print >>stderr, u'  no new books'


def main():
    urls = load_url_dict(cfgUrlListPath)

    for url in urls.iterkeys():
        print >>stderr, urls[url]
        watch_page(url)

    return 0


if __name__ == '__main__':
    main()

