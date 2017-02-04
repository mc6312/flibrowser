#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import MySQLdb

db = MySQLdb.connect(user=u'vsvm', passwd='yogsothoth', db='flibusta', use_unicode=True, charset='utf8')
try:
    bcur = db.cursor()
    try:
        print 'filtering...'
        '''r = bcur.execute(u"""SELECT lb.BookId,lb.Title
                            FROM libbook AS lb
                            WHERE lb.Deleted=0
                                AND lb.Lang="ru"
                                AND lb.BookId NOT IN (
                                    SELECT BookId FROM libgenre
                                    WHERE GenreId IN (
                                        SELECT GenreId
                                        FROM libgenrelist
                                        WHERE GenreId NOT IN (SELECT GenreId
                                            FROM bansetgenrelist)
                                            )
                                        )""")'''

        bcur.execute(u"""DECLARE @names VARCHAR(500)
                        SELECT @names = @names + ':' + LastName
                        FROM (
                            SELECT lan.LastName
                            FROM libavtorname as lan
                            WHERE lan.AvtorId IN (
                                SELECT la.AvtorId
                                FROM libavtor as la
                                WHERE la.BookId=1)
                            )""")


        tr = bcur.rowcount
        r = tr
        if r:
            while r > 0:
                name = bcur.fetchone()
                print name
                #bookId, bookTitle = bcur.fetchone()
                #print bookTitle

                '''acur = db.cursor()
                try:
                    acur.execute(u"""SELECT lan.FirstName,lan.LastName
                                    FROM libavtorname AS lan
                                    WHERE lan.AvtorId IN (
                                        SELECT la.AvtorId
                                        FROM libavtor AS la
                                        WHERE la.BookId=%s)""", (bookId,))

                    if acur.rowcount:
                        bookAuthor = u''

                        if bookAuthor:
                            bookAuthor += u', '
                        bookAuthor += u' '.join(map(lambda s: unicode(s, 'utf-8'), acur.fetchone()))
                    else:
                        bookAuthor = u'?'

                finally:
                    acur.close()

                print u'%s. %s' % (bookAuthor, bookTitle.decode('utf-8')) '''

                r -= 1
        print 'total:', tr

    finally:
        bcur.close()
finally:
    db.close()
