# -*- coding: utf8 -*-

u'''A RSS reader for the Lalita IRC bot.'''

__author__ = 'rbistolfi'
__date__ = '12/28/2009'
__mail__ = 'moc.liamg@iflotsibr'[::-1]
__version__ = '0.1'
__license__ = 'GPLv3'


from lalita import Plugin
import feedparser
import urllib2
import sqlite3


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
        
        #config
        self.max = 10
        self.tinyurl = True
       
        #db connection
        self.conn = sqlite3.connect('db/rss.db')
        self.cursor = self.conn.cursor()
        self._init_db()

    ##
    ## Commands
    ##

    def rss(self, user, channel, command, *args):
        '''@rss [url|alias]. Read RSS from url or from a registered feed unedr
        the given alias. See @rss_add.'''

        #from pudb import set_trace; set_trace()

        for arg in args:
            # arg is an url
            if arg.startswith('http://') or arg.startswith('https://'):
                for item in self._get_items(arg):
                    self.logger.debug(item)
                    text = "News from %s: " % self.feed_title + ": ".join(item) 
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
                    text = "News from %s: " % self.feed_title + ": ".join(item) 
                    self.say(channel, text)

    def rss_add(self, user, channel, command, *args):
        u'''@rss_add <alias> <url>. Adds a RSS feed to the database. <alias> is
        a single word that can be used as a shortcut for the url with the @rss
        command.'''
        try:
            alias, url = args
        except ValueError:
            self.say(channel, 'Usage: @rss_add <alias> <url>')
        self._add_rss(channel, alias, url)
        self.logger.debug(self.cursor.execute('select * from feeds').fetchall())

    def rss_delete(self, user, channel, command, *args):
        '''@rss_del <alias>. Removes the feed referenced by <alias> from the
        database.'''
        
        if len(args) != 1:
            self.say(channel, '%s: Usage: @rss_del <alias>' % (user,))
            return
        self._del_rss(args[0])

    def rss_list(self, user, channel, command, *args):
        u'''Returns a list of registered RSS feeds.'''
        from pudb import set_trace; set_trace()

        self.cursor.execute('SELECT alias, url FROM feeds')
        for feed in self.cursor.fetchall():
            self.say(channel, '%s: %s, %s' % (user, feed[0], feed[1]))

    ##
    ## Database
    ##

    def _add_rss(self, alias, url):
        '''Adds a new entry into the rss database.'''

        self.cursor.execute("INSERT INTO feeds VALUES(?, ?, ?)", (channel, alias, url))
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
                (feed TEXT, hash TEXT, title TEXT, url TEXT)''')
        self.conn.commit()

    ##
    ## Rss
    ##

    def _get_items(self, url, tinyurl=None):
        '''Gets a feed from a url.'''

        if tinyurl is None:
            tinyurl = self.tinyurl

        # feed data
        feed = feedparser.parse(url)
        self.feed_title = feed['feed']['title']
        
        # items
        for entry in feed['entries'][:self.max]:
            if tinyurl:
                link = self._tinyurl(entry['link'])
            else:
                link = entry['link']
            yield entry['title'], link

    ##
    ## Helpers
    ##

    def _tinyurl(self, url):
        '''Returns a tinyurl from url.'''

        return urllib2.urlopen( \
                "http://tinyurl.com/api-create.php?url=%s" % url).read()
