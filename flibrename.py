#!/usr/bin/env python
# -*- coding: utf-8 -*-

from codecs import open
import re, sys, os, os.path

"""<img src="ru_files/znak.gif" border="0"><select onchange="setrate(75210)" id="rate75210"><option selected="selected" value="0">  </option><option value="1">нечитаемо</option><option value="2">плохо</option><option value="3">неплохо</option><option value="4">хорошо</option><option value="5">отлично!</option></select><input id="13-1472" name="75210" type="checkbox"> - 72.  <a href="http://www.flibusta.net/b/75210">Дело сварливого свидетеля</a> (пер. <a href="http://www.flibusta.net/a/38771">П В Рубцов</a>)  <span style="size">35K (473)</span> &nbsp; <a href="http://www.flibusta.net/b/75210/read">(читать)</a> &nbsp;  <a href="http://www.flibusta.net/b/75210/download">(скачать)</a> <br>"""

rx_book = re.compile(ur'^.+?<a href="http:\/\/www\.flibusta\.net.+?">(.+?)<\/a>.+?flibusta\.net\/b\/(\d+?)\/download.+?$', re.IGNORECASE|re.UNICODE|re.MULTILINE)
rx_cyclepart = re.compile(ur'^(.+?_\d+?_).*$', re.UNICODE)

FIOENC = sys.getfilesystemencoding()

if len(sys.argv) <> 3:
	print u'flibrename.py saved_page.html workdir'
	exit(1)

# load saved page

with open(sys.argv[1].decode(FIOENC), 'r', encoding=FIOENC) as srcf:
	rawbooks = rx_book.findall(srcf.read())

books = {}
if rawbooks:
	books = dict(map(lambda book: (book[1], book[0]), rawbooks))

# search and rename files


workdir = sys.argv[2].decode(FIOENC)
for fname in os.listdir(workdir):
	fpath = os.path.join(workdir, fname)
	fext = os.path.splitext(fname)[1].lower()
	if (os.path.isfile(fpath)) and (fext == u'.fb2'):
		npart = fname.split(u'.')[-2]
		if npart in books:
			fnewname = books[npart] + fext
			fnprefix = rx_cyclepart.search(fname)
			if fnprefix:
				fnewname = fnprefix.group(1) + fnewname

			fnewpath = os.path.join(workdir, fnewname)
			print fname, u'->', fnewname

			if os.path.exists(fnewpath):
				print u'  can not rename'
			else:
				os.rename(fpath, fnewpath)

