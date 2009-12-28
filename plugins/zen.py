# -*- coding: utf8 -*-

# Copyright 2009 laliputienses
# License: GPL v3
# For further info, see LICENSE file

from lalita import Plugin
from this import *
from random import randint

TRANSLATION_TABLE = {}


class Zen(Plugin):
    u'''Rss reader for lalita'''

    def init(self, config):
        self.register_translation(self, TRANSLATION_TABLE)
        self.register(self.events.COMMAND, self.zen, ['zen'])

    def zen(self, user, channel, command, *args):
        u'''A verse from The Zen of Python by Tim Peters.'''

        d = {}
        for c in 65,97:
            for i in range(26):
                d[chr(i+c)] = chr((i+13) % 26 + c)
        
        zen = "".join([d.get(c, c) for c in s if c]).split("\n")[2:]
        text = u"%s: %s" % (user, zen[randint(0,18)])
        self.say(channel, text)
