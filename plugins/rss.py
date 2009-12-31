# -*- coding: utf8 -*-

u'''A RSS reader for the Lalita IRC bot.'''

__author__ = 'rbistolfi'
__date__ = '12/28/2009'
__mail__ = 'moc.liamg@iflotsibr'[::-1]
__version__ = '0.1'
__license__ = 'GPLv3'


import urllib2
import feedparser
import sqlite3
from sqlite3 import IntegrityError
from md5 import md5

from twisted.internet import task

try:
    from lalita import Plugin
except ImportError:
    from core import Plugin


#TODO
TRANSLATION_TABLE = {}


class Rss(Plugin):
    u'''Rss reader for lalita.'''

    def init(self, config):
        u'''Plugin initialization'''

        self.register_translation(self, TRANSLATION_TABLE)
        self.register(self.events.COMMAND, self.rss, ['rss'])
        self.register(self.events.COMMAND, self.rss_add, ['rss_add'])
        self.register(self.events.COMMAND, self.rss_delete, ['rss_del'])
        self.register(self.events.COMMAND, self.rss_list, ['rss_list'])
        self.register(self.events.COMMAND, self.announce, ['announce'])
      
        # TODO? replace multiple rss commands with a dispatch
        # Ex: @rss_del would be replaced by @rss del
        self.subcommands = {
                'add': self.rss_add,
                'del': self.rss_delete,
                'list': self.rss_list, }

        # TODO: get data from config file
        # config
        self.max = 20
        self.tinyurl = True
       
        # db connection
        self.conn = sqlite3.connect('db/rss.db')
        self.cursor = self.conn.cursor()
        self._init_db()

        # schedule announces
        # this does not work atm
        announce = task.LoopingCall(self.announce, "lalita", "#lalita", \
                u"announce", None)
        announce.start(300.0, now=False) # call every 5 mins
        
    ##
    ## Commands
    ##

    # TODO: Move sql stuff into their own methods to the database section

    def rss(self, user, channel, command, *args):
        u'''@rss [url|alias]. Read RSS from url or from a registered feed unedr
        the given alias. See @rss_add.'''

        #from pudb import set_trace; set_trace()

        for arg in args:
            # arg is an url
            if arg.startswith('http://') or arg.startswith('https://'):
                for item in self._get_items(arg):
                    self.logger.debug(item)
                    text = "News from %s: " % self.feed_title + \
                            " || ".join(item) 
                    self.say(channel, text)
            
            # we asume arg is an alias
            else:
                self.cursor.execute("SELECT url FROM feeds WHERE alias == ?",
                        (arg,))
                try:
                    url = self.cursor.fetchone()[0]
                except TypeError:
                    self.say(channel, '%s: Feed is not registered.' % user)
                for item in self._get_items(url):
                    self.logger.debug(item)
                    text = "News from %s: " % self.feed_title + \
                            " || ".join(item) 
                    self.say(channel, text)

    def rss_add(self, user, channel, command, *args):
        u'''@rss_add <alias> <url>. Adds a RSS feed to the database. <alias> is
        a single word that can be used as a shortcut for the url with the @rss
        command.'''

        #from pudb import set_trace; set_trace()
        try:
            alias, url = args
        except ValueError:
            self.say(channel, 'Usage: @rss_add <alias> <url>')
        self._add_rss(alias, url, channel)

    def rss_delete(self, user, channel, command, *args):
        '''@rss_del <alias>. Removes the feed referenced by <alias> from the
        database.'''
        
        #from pudb import set_trace; set_trace()
        if len(args) != 1:
            self.say(channel, '%s: Usage: @rss_del <alias>' % (user,))
            return
        self._del_rss(args[0])

    def rss_list(self, user, channel, command, *args):
        u'''Returns a list of registered RSS feeds.'''

        #from pudb import set_trace; set_trace()
        self.cursor.execute('SELECT alias, url FROM feeds')
        for feed in self.cursor.fetchall():
            self.say(channel, '%s: %s, %s' % (user, feed[0], feed[1]))

    def announce(self, user, channel, command, *args):
        u'''@announce. Shows unread RSS entries.'''

        #from pudb import set_trace; set_trace()

        # get registered feeds for the current channel
        self.cursor.execute('SELECT rowid, url, channel FROM feeds')

        # for each url, announce entries that are not in the "entries"
        # table, those have been announced already
        for rowid, url, channel in self.cursor.fetchall():
            self.logger.info("Looking for news in %s." % (url,))
            # twisted complains if this is unicode
            channel = str(channel)
            
            for item in self._get_items(url):
                dash = md5(''.join(item).encode("utf8"))
                try:
                    self.cursor.execute("INSERT INTO entries VALUES(?, ?)",
                            (rowid, dash.hexdigest()))
                    self.conn.commit()
                    text = "News from %s: " % self.feed_title + \
                            " || ".join(item) 
                    self.logger.debug([text, self, user, channel, command,
                        args])
                    self.say(channel, text)
                except IntegrityError:
                    self.logger.debug("Skiping %s, already announced." %
                            (item,))

    ##
    ## Database
    ##

    def _add_rss(self, alias, url, channel):
        '''Adds a new entry into the rss database.'''

        self.cursor.execute("INSERT INTO feeds(channel, alias, url) "\
                "VALUES(?, ?, ?)", (channel, alias, url))
        self.conn.commit()

    def _del_rss(self, alias):
        '''Removes a feed from the database'''

        self.cursor.execute("DELETE FROM feeds WHERE alias == ?", (alias,))
        self.conn.commit()

    def _init_db(self):
        '''Creates the rss database.'''
        self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS feeds
                (channel TEXT, alias TEXT, url TEXT)''')

        self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS entries
                (feed TEXT, hash TEXT UNIQUE)''')
        self.conn.commit()

    ##
    ## Rss
    ##

    def _get_items(self, url, tinyurl=None):
        '''Gets a feed from a url.'''

        if tinyurl is None:
            tinyurl = self.tinyurl

        # TODO: handle the various RSS (non)standards
        # feed data
        feed = feedparser.parse(url)
        self.feed_title = feed['feed'].get('title', None)
       
        # items
        for entry in feed['entries'][:self.max]:
            if tinyurl:
                link = self._tinyurl(entry['link'])
            else:
                link = entry['link']
                title = entry.get('title', None)
            yield title, link

    ##
    ## Helpers
    ##

    def _tinyurl(self, url):
        '''Returns a tinyurl from url.'''

        return urllib2.urlopen( \
                "http://tinyurl.com/api-create.php?url=%s" % url).read()
