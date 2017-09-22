pack = 7z a -mx=9
docs = COPYING README.md Changelog
basename = flibrowser
arcx = .7z
arcname = $(basename)$(arcx)
arcsrc = $(basename)-src$(arcx)
configs = genrelist.json banned-authors banned-tags #config
srcs = flibrowser.py flibcrutch.py fbcommon.py fbsettings.py fbtemplates.py fbconfig.py fbabout.py fbgenlistimport.py __main__.py
main = $(configs) $(docs) flibrowser.svg
backupdir = ~/shareddocs/pgm/python/
zipname = flibrowser.zip

app:
	zip -9 $(zipname) $(srcs)
	@echo '#!/usr/bin/env python3' >$(basename)
	@cat $(zipname) >> $(basename)
	chmod 755 $(basename)
	rm $(zipname)
install:
	make app
	mv $(basename) ~/bin/
archive:
	$(pack) $(arcsrc) $(main) $(config) *.py Makefile *.geany book_age.png
distrib:
	make app
	$(pack) $(arcname) $(basename) $(main)
	rm $(basename)
backup:
	make archive
	mv $(arcsrc) $(backupdir)
update:
	7z x -y $(backupdir)$(arcsrc)
