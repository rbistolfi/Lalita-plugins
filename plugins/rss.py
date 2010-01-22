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
import simplejson as json

from twisted.web import client
from twisted.internet import task, defer, reactor, threads

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
        #self.register(self.events.COMMAND, self.announce, ['announce'])
      
        # TODO? replace multiple rss commands with a dispatch
        # Ex: @rss_del would be replaced by @rss del
        self.subcommands = {
                'add': self.rss_add,
                'del': self.rss_delete,
                'list': self.rss_list, }

        self.messages = []

        # TODO: get data from config file
        # config
        self.max = 3
        self.tinyurl = True
       
        # db connection
        self.conn = sqlite3.connect('db/rss.db')
        self.cursor = self.conn.cursor()
        self._init_db()

        # schedule announces
        # this does not work atm
        announce = task.LoopingCall(self.announce)
        announce.start(300.0, now=False) # call every 5 mins
        
    ##
    ## Commands
    ##

    # TODO: Move sql stuff into their own methods to the database section
    
    def rss(self, user, channel, commands, *args):
        u'''@rss [url|alias]. Read RSS from url or from a registered feed unedr
        the given alias. See @rss_add.'''
 
        # find url
        url = self._get_url(args[0])
        d = threads.deferToThread(self._rss_handler, user, channel, url)
        d.addCallback(self._rss_callback)
        return d

    def rss_add(self, user, channel, command, *args):
        u'''@rss_add <alias> <url>. Adds a RSS feed to the database. <alias> is
        a single word that can be used as a shortcut for the url with the @rss
        command.'''

        #from pudb import set_trace; set_trace()
        try:
            alias, url = args
        except ValueError:
            self.say(channel, u'Usage: @rss_add <alias> <url>')
        self._add_rss(alias, url, channel)

    def rss_delete(self, user, channel, command, *args):
        '''@rss_del <alias>. Removes the feed referenced by <alias> from the
        database.'''
        
        #from pudb import set_trace; set_trace()
        if len(args) != 1:
            self.say(channel, u'%s: Usage: @rss_del <alias>', user)
            return
        self._del_rss(args[0])

    def rss_list(self, user, channel, command, *args):
        u'''Returns a list of registered RSS feeds.'''

        #from pudb import set_trace; set_trace()
        self.cursor.execute('SELECT alias, url FROM feeds')
        for feed in self.cursor.fetchall():
            self.say(channel, '%s: %s, %s', user, feed[0], feed[1])

    def announce(self):
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
                self.logger.info(item)
                try:
                    dash = hash(''.join(item))
                except TypeError:
                    pass
                try:
                    self.cursor.execute("INSERT INTO entries VALUES(?, ?)",
                            (rowid, dash))
                    self.conn.commit()
                    text = "News from %s: " % self.feed_title + \
                            " || ".join(item) 
                    self.say(channel, text)
                except IntegrityError:
                    self.logger.debug("Skiping %s, already announced." %
                            (item,))

    ##
    ## Rss
    ##

    ## Get rss ##

    def _get_items(self, url, tinyurl=None):
        '''Gets RSS feed from url and yields a tuple containing the title and
        link for each RSS entry. If the keyword argument tinyurl is True, links
        will be processed through the tinyurl api to get a short url.'''
        
        if tinyurl is None:
            tinyurl = self.tinyurl

        # TODO: handle the various RSS (non)standards
        # feed data
        try:
            feed = feedparser.parse(url)
            self.feed_title = feed['feed'].get('title', url)
       
            # items
            for entry in feed['entries']:
                link = entry.get('link', u'No link')
                title = entry.get('title', u'No title')
                if tinyurl:
                    if 'No link' not in link:
                        link = self._biturl(link)
                yield title, link
        except Exception, e:
            self.logger.error("Can't parse RSS feed: %s" % e)
            pass

    ## RSS command ##
        
    def _rss_callback(self, args):
        '''Callback called when RSS entries retrieving is done.
        args is the return value of the deferred thread (_rss_handler).'''

        self.logger.debug("Executing RSS callback.")
        user, channel, msgs = args
        for msg in msgs:
            self.say(channel, msg)

    def _rss_handler(self, *args):
        '''This method is ran in a deferred thread when the rss command is
        called.'''

        user, channel, url = args
        messages = []
        for item in self._get_items(url):
            if item is not None:
                self.logger.debug(item)
                text = "News from %s: " % self.feed_title + \
                        " || ".join(item) 
                messages.append(text)
            else:
                messages.append("%s: Error parsing RSS feed." % user)
        return user, channel, messages

    def _get_url(self, arg):
        '''Takes the argument passed to the rss command and queries the db for
        getting an url if needed.'''

        # arg is an url
        if "http://" in arg or "https://" in arg:
            return arg

        # if it is not an url, we assume it is an alias
        else:
            self.cursor.execute("SELECT url FROM feeds WHERE alias == ?",
                    (arg,))
            try:
                url = self.cursor.fetchone()[0]
                return url
            except TypeError:
                return None

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
    ## Helpers
    ##

    def _tinyurl(self, url):
        '''Returns a tinyurl from url.'''
        try:
            return urllib2.urlopen( \
                    "http://tinyurl.com/api-create.php?url=%s" % url).read()
        except Exception, e:
            self.logger.debug("Error shortening url %s" % url)
            return url

    def _biturl(self, url):
        data = urllib2.urlopen("http://api.bit.ly/shorten?version=2.0.1&" \
                "longUrl=%s&login=rbistolfi&" \
                "apiKey=R_6d75b2bcf16ae38c39c8ebbb89e2c152" % url).read()
        try:
            return json.loads(data)['results'][url]['shortUrl']
        except Exception, e:
            self.logger.debug("Error shortening %s" % url)
            return url.replace("%", "%%")
