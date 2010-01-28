# -*- coding: utf8 -*-

u'''A RSS reader for the Lalita IRC bot.'''

#TODO: Remember what entries have been announced already


from __future__ import with_statement

__author__ = 'rbistolfi'
__license__ = 'GPLv3'

import urllib2
import feedparser
import sqlite3
import md5
from sqlite3 import IntegrityError

from twisted.web import client
from twisted.internet import task, defer, reactor

from lalita import Plugin

TIMEOUT = 30
TRANSLATION_TABLE = {}

class Rss(Plugin):
    u"""A RSS reader for Lalita."""

    def init(self, config):
        """Plugin intitalization."""
        
        self.register_translation(self, TRANSLATION_TABLE)
        self.register(self.events.COMMAND, self.rss, ['rss'])
      
        # dispatch for rss subcommands
        self.dispatch = {
                'add': self.add,
                'del': self.delete,
                'list': self.list, }

        self.messages = []

        # TODO: get data from config file
        # config
        self.max = 3
        self.use_tinyurl = True # set it to True for blocking the process ;)

        # database
        self.db = RssDatabase('db/rss.db')
        self.db.init_db()
        
        # announce schedule
        feeds = self.db.get_feeds()
        self.to_announce = [ (channel, alias, RSSConditionalGetter(url,
            self.logger)) for channel, alias, url in feeds ]
        announce = task.LoopingCall(self.announce)
        announce.start(1800.0, now=False) # call every X seconds

    ##
    ## Comands
    ##

    def rss(self, user, channel, command, *args):
        u"""@rss [url|alias|list|add|del]: Reads RSS entries from <url> or 
        <alias>. <alias> is a RSS feed registered with the add command. 
        @rss list: List the registered feeds. @rss add <alias> <url>: 
        register <url> with <alias>. @rss del <alias>: removes <alias> from 
        the database."""

        usage = u'Usage: @rss [url|alias|list|add|del]'

        if not args:
            self.say(channel, u'%s: %s', user, usage)
            return 0
        
        # arg is a command - dispatch
        if args[0] in self.dispatch:
            self.dispatch.get(args[0])(user, channel, command, *args)
            return 1
        # arg is an url
        elif args[0].startswith("http"):
            url = args[0]        
        # arg is an alias
        else:
            alias = args[0]
            try:
                url = self.db.get_feed_byalias(alias, channel)
            except TypeError, e:
                self.say(channel, u"%s: '%s' is not a registered feed", user,
                        alias)

        format = "%s || %s"

        deferred = self.get(url)
        deferred.addCallback(self.feed_parser)
        deferred.addErrback(self.feed_parser_error, user, channel)
        #deferred.addCallbacks(self.tinyurl)
        deferred.addCallback(self.say_feed, format, user, channel, command, *args)
        return deferred
        
    def add(self, user, channel, command, *args):
        """Add a RSS url to the database under certain alias."""
        
        usage = u"Usage: @rss add <alias> <url>"

        try:
            alias, url = args[1:]
        except ValueError:
            self.say(channel, u'%s: %s', user, usage)
            return 0

        if not url.startswith(u'http'):
            self.say(channel, u'%s: Second argument should be an url.', 
                    user)
        else:
            self.db.add_feed(channel, alias, url)
            self.to_announce.append((channel, alias, RSSConditionalGetter(url,
                self.logger)))
            self.say(channel, u'%s: RSS feed added to the database.', user)

    def delete(self, user, channel, command, *args):
        """Remove a RSS from the database."""
        
        usage = u"Usage: @rss del <alias>"

        try:
            alias = args[1]
        except IndexError:
            self.say(channel, u'%s: %s', user, usage)
        self.logger.debug("Deleting RSS feed %s", alias)
        self.db.delete_feed(alias)
        self.say(channel, '%s: %s removed from te database', user, alias)

    def list(self, user, channel, command, *args):
        """List the registered feeds."""
        
        usage = u"Usage: @rss list"
    
        rss_list = self.db.get_feeds_bychannel(channel)
        self.logger.debug(rss_list)

        for feed in rss_list:
            alias, url = feed
            self.say(channel, "%s: %s", alias, url)

    ##
    ## Non interactive announce
    ##

    def announce(self):
        """Announce news in registered feeds."""
        self.logger.debug(self.to_announce)
        for channel, alias, instance in self.to_announce:
            self.logger.info("Looking for news in %s" % alias)
            channel = str(channel)
            alias = str(alias)
            format = "News from " + alias + ": %s || %s" 

            deferred = instance.get_rss()
            deferred.addCallback(self.feed_parser)
            deferred.addErrback(self.feed_parser_error, None, channel)
            #deferred.addCallbacks(self.tinyurl) # this blocks the process :(
            deferred.addCallback(self.msg_filter, alias)
            deferred.addCallback(self.say_feed, format, None, channel, None)
            deferred.addErrback(self.logger.debug)
            #return

    def msg_filter(instance, entries, feed_alias):
        """Add announced RSS items to database and pass only what it is not
        already there."""
        filtered = []
        for item in entries:
            dash = md5.md5(''.join(repr(item))).hexdigest()
            try:
                instance.db.add_entry(feed_alias, dash)
                filtered.append(item)
            except IntegrityError:
                instance.logger.debug("Skiping %s, already announced." %
                        (item,))
        return filtered

    ##
    ## RSS callback chain
    ##

    def get(self, url):
        """Get the contents of url."""
        return client.getPage(str(url))

    def feed_parser(self, feed):
        """Parse RSS feed."""
        fp = feedparser.parse(feed)
        entries = []
        for i in fp.get('entries'):
            title = i.get('title')
            url = i.get('link')
            entries.append((title, url))
        return entries

    def feed_parser_error(self, error, user, channel, *args):
        """Error callback for feed_parser."""
        self.logger.error("Error parsing rss feed: %s", error)
        self.say(channel, '%s: Error parsing RSS feed', user)

    def say_feed(self, messages, format, user, channel, command, *args):
        """Say message in channel to user."""
        for title, url in messages:
            self.say(channel, unicode(format), title, url)

    ##
    ## tinyurl
    ##

    def tinyurl(self, data):
        '''Returns a tinyurl from url.'''
        d = defer.Deferred()
        shortened = []
        for title, link in data:
            url = urllib2.urlopen( \
                    "http://tinyurl.com/api-create.php?url=%s" %
                    str(link)).read()
            shortened.append((title, url))
            #url.addCallback(self.append_tinyurl, title, shortened)
            #url.addErrback(self.append_tinyurl, link, title, shortened)
        d.callback(shortened)
        return d

    def append_tinyurl(instance, url, title, data_container):
        '''Append data containing a tinyurl to a list.'''
        instance.logger.debug("Building tinyurl %s for %s" % (url, title))
        data_container.append((title, url))


class SQLiteConnection(object):
    """A connection handler SQLite database."""

    def __init__(self, dbfile):
        """Initialize connection arguments."""
        self.dbfile = dbfile
        self.conn = None

    def __enter__(self):
        """Stablish the connection and return the database cursor."""
        self.conn = sqlite3.connect(self.dbfile)
        return self.conn.cursor()

    def __exit__(self, *args):
        """Close the connection after rollback unclean queries if any."""
        
        # if there is no TraceBack, we commit
        if args[-1] is None:
            self.conn.commit()
        # if there is TraceBack, we better rollback
        else:
            self.conn.rollback()
        self.conn.close()


class RssDatabase(object):
    """A data handler for Lalita RSS plugin."""

    def __init__(self, dbfile):
        """Connection initialization."""
        self.dbfile = dbfile

    def init_db(self):
        """Creates a new database if it does not exist already."""
        
        with SQLiteConnection(self.dbfile) as db:
            db.execute('''
                CREATE TABLE IF NOT EXISTS feeds
                (channel TEXT, alias TEXT, url TEXT)''')

            db.execute('''
                CREATE TABLE IF NOT EXISTS entries
                (feed TEXT, hash TEXT UNIQUE)''')

    def add_feed(self, channel, alias, url):
        """Insert a new feed in the database. The feed will be automatically
        announced in the given channel by Lalita."""
        
        with SQLiteConnection(self.dbfile) as db:
            db.execute("INSERT INTO feeds(channel, alias, url) " \
                "VALUES(?, ?, ?)", (channel, alias, url))

    def delete_feed(self, alias):
        """Removes the feed with the given alias from the database."""
        
        with SQLiteConnection(self.dbfile) as db:
            db.execute("DELETE FROM feeds WHERE alias == ?", (alias,))

    def get_feed_byalias(self, alias, channel):
        """Returns a RSS feed matching the given alias and channel."""
        
        with SQLiteConnection(self.dbfile) as db:
            db.execute("SELECT url FROM feeds WHERE alias == ? AND \
                    channel == ?", (alias, channel))
            return db.fetchone()[0]

    def get_feeds_bychannel(self, channel):
        """Get all the registered RSS feeds for a given channel."""
       
        with SQLiteConnection(self.dbfile) as db:
            db.execute('SELECT alias, url FROM feeds WHERE channel == ?',
                    (channel,))
            return db.fetchall()

    def get_feeds(self):
        """Get all the registered RSS feeds."""
       
        with SQLiteConnection(self.dbfile) as db:
            db.execute('SELECT channel, alias, url FROM feeds')
            return db.fetchall()

    def add_entry(self, feed, entry_id):
        """Adds a Rss entry to the database so Lalita can remember what has
        been announced already. The column has the UNIQUE attribute, so this
        will raise an IntegrityError if entry already exists. The entry_id
        argument is whatever you consider to be a unique identifier for an Rss
        entry"""
        
        with SQLiteConnection(self.dbfile) as db:
            db.execute("INSERT INTO entries VALUES(?, ?)", (feed, entry_id))


# This is shamelessly taken from the Twisted network programming essentials book
class ConditionalGetClient(client.HTTPClientFactory):
    """An HTTP client for RSSConditionalGetter."""
    
    def __init__(self, url, headers=None, postdata=None, 
            agent="Twisted RSSConditionalGetter", timeout=TIMEOUT, cookies=None):
        """Class initialization."""

        client.HTTPClientFactory.__init__(self, url, headers=headers)
        self.status = None
        self.deferred.addCallback(
                lambda data: (data, self.status, self.response_headers))

    def noPage(self, reason):
        """Overwrites superclass method for stop interpreting 304 response code
        as an error."""

        if self.status == '304':
            client.HTTPClientFactory.page(self, '')
        else:
            client.HTTPClientFactory.noPage(self, reason)


class RSSConditionalGetter(object):
    """Performs a GET request only if there is updated content.
    Stores the Last-Modified and ETag headers when receiving a RSS file and
    uses them to check the If-Modified-Since and If-None-Match headers the next
    time it visits the same feed. 
    What you want is to run the get_rss method, it returns a deferred that you
    can use for something else, like parsing the feed.
   
    >>> def parse(feed): print feedparser.parse(feed)['entries'][0]['title']
    >>> def on_error(reason): print "Error parsing RSS feed: %s" % reason,
    >>> url = "http://python-history.blogspot.com/feeds/posts/default?alt=rss"
    >>> rss = RSSConditionalGetter(url)
    >>> deferred = rss.get_rss()
    >>> deferred.addCallback(parse)
    >>> deferred.addErrback(on_error)
    """

    def __init__(self, url, logger=None):
        """Class initializations."""
        
        self.url = str(url)
        self.cache = {}
        self.deferred = defer.succeed(url)
        self.logger = logger
        
    def connect(self, contextFactory=None, headers=None, *args, **kwargs):
        """Creates a connection with the host using the appropriate transport
        and headers."""
        url = self.url
        self.logger.debug("Connecting to %s" % url)
        headers = self.cache.get(url)
        scheme, host, port, path = client._parse(url)
 
        factory = ConditionalGetClient(url, headers=headers, *args, **kwargs)
        if scheme == 'https':
            from twisted.internet import ssl
            if contextFactory is None:
                contextFactory = ssl.ClientContextFactory()
            reactor.connectSSL(host, port, factory, contextFactory)
        else:
            reactor.connectTCP(host, port, factory)
        return factory.deferred

    def request(self, result):
        """Requests handler."""
   
        url = self.url
        data, status, headers = result

        self.logger.debug("-"*40)
        self.logger.debug("HEADERS: %s" % headers)
        self.logger.info("Status: %s => %s" % (url, status))
        self.logger.debug("CACHE: %s" % self.cache.get(url))
 
        nextRequestHeaders = {}
        eTag = headers.get("etag")
        if eTag:
            nextRequestHeaders['If-None-Match'] = eTag[0]
        else:
            nextRequestHeaders['If-None-Match'] = headers.get('If-None-Match')

        modified = headers.get('last-modified')
        if modified:
            nextRequestHeaders['If-Modified-Since'] = modified[0]
        else:
            nextRequestHeaders['If-Modified-Since'] = \
                    headers.get('If-Modified-Since')

        self.cache[url] = nextRequestHeaders
        self.logger.debug("NEXT HEADERS: %s" % nextRequestHeaders)
        self.logger.debug("-"*40)
        return data

    def handleError(self, failure):
        """Error handler triggered when response code is not 200 or 304."""
        self.logger.debug("Error %s: " % failure.getErrorMessage())

    def get_rss(self):
        deferred = self.deferred
        deferred.addCallback(self.connect)
        deferred.addCallback(self.request)
        deferred.addErrback(self.handleError)
        return deferred
