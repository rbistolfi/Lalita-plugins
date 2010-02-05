# -*- coding: utf8 -*-

u'''A RSS reader for the Lalita IRC bot.'''

from __future__ import with_statement


__author__ = 'rbistolfi'
__license__ = 'GPLv3'


import re
from lalita import Plugin
from time import gmtime
from twisted.internet import task


TRANSLATION_TABLE = {}


class Logger(Plugin):
    """A IRC channel Logguer for Lalita.
    Log what is said in a channel and upload the thing to github.
    """

    exclude = re.compile(r'^#')

    def init(self, config):
        """Plugin intitalization."""
        
        self.register_translation(self, TRANSLATION_TABLE)
        self.register.events.PUBLIC_MESSAGE(self.push)
        self.register.events.COMMAND(self.log, ['log'])

        self.messages = []
      
        # dispatch for subcommands
        self.dispatch = {
                'start': self.start,
                'stop': self.stop,
                'commit': self.commit,
                }

        # config
        self.base_dir = self.config.get('base_dir', ".")
        time_gap = self.config.get('time_gap', 3600.0)

        # schedule
        schedule = task.LoopingCall(self.commit)
        schedule.start(time_gap, now=False) # call every X seconds


    ## Methods implementing the user interface

    def log(self, user, channel, command, *args):

        u"""Upload the channel log to github. Usage: @log [start, stop, commit]"""
        usage = u'@log [start, stop, commit]'

        if args[0] in self.dispatch:
            self.dispatch[args[0]](user, command, channel, *args)

        else:
            self.say(channel, u'%s: Usage: %s', user, usage)

    def start(self, user, channel, command, *args):
        """Start logging the channel."""
        pass

    def stop(self, user, channel, command, *args):
        """Stop logging a channel."""
        pass

    def commit(self, user, channel, command, *args):
        """Force a commit to github right now. A user is able to save the log
        even at non scheduled time."""
        pass


    ## Methods implementing string handling

    def push(self, user, channel, message):
        """Push a message to the buffer."""

        date = "GMT %r-%r-%r %r:%r:%r" % gmtime()[:6]
        self.messages.get('channel', []).append((date, user, message))

    def format(self, message):
        """Gives format to a message."""

        return "[%s] %s: %s" % message


    ## Methods implementing git backend

    def git_init_repository(self):
        """Initializes a git repository. Checks if a .git directory exists in
        the configured location and creates a new repository if it doesnt."""
        pass

    def git_commit(self):
        """Executes git commit command."""
        pass

    def git_push(self):
        """Executes git push command."""
        pass

