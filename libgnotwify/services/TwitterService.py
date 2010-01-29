#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Gnotwify - Copyright (c) 2009 Pablo Seminario
# This software is distributed under the terms of the GNU General
# Public License
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import time
import urllib2
import ConfigParser
import logging

import twitter

from libgnotwify import CONFIG_DIR, CONFIG_FILE
from libgnotwify import Message
from libgnotwify import Service, ServiceError
from libgnotwify import Logger

class TwitterService(Service):
    """Class to implement notifications through Twitter API."""

    SRV_NAME = 'twitter'

    def __init__(self):
        Service.__init__(self,self.SRV_NAME)

    def load_config(self):
        """Load configuration settings from the twitter section in CONFIG_FILE."""
        Service._load_config(self)

        config = ConfigParser.ConfigParser()

        config.read(CONFIG_FILE)
        self.username = config.get('main', "username")
        self.password = config.get('main', "password")
        self.interval = int(config.get('main', "interval"))

        # if doesn't exist make a directory to store cached profile images
        if not os.path.exists(CONFIG_DIR + "/" + self.SRV_NAME):
            os.mkdir(CONFIG_DIR + "/" + self.SRV_NAME)

    def _get_updates(self):
        """Retrieves updates from Twitter API and return an array of entries."""
        statuses = []
        api = twitter.Api(self.username, self.password)

        try:
            statuses = api.GetFriendsTimeline()
        except:
            raise ServiceError('Update error')
        else:
            self.logger.debug("Updated")
        
        return statuses

    def _normalize_entries(self, entries):
        """Normalizes and sorts an array of entries and returns an array of messages."""
        messages = []

        for entry in self._reverse(entries):

            icon = os.path.join(CONFIG_DIR, self.SRV_NAME, str(entry.user.id))
            if not os.path.exists(icon):
                try:
                    avatar = urllib2.urlopen(entry.user.profile_image_url)
                    self.logger.debug("Fetching image profile for " + entry.user.screen_name)
                except:
                    self.logger.error("Error fetching image profile for " + entry.user.screen_name)
                    icon = os.path.join(os.path.realpath(os.path.dirname(sys.argv[0])), 'icons', 'twitter.png')
                else:
                    avatar_file = open(os.path.join(CONFIG_DIR, self.SRV_NAME, str(entry.user.id)), 'wb')
                    avatar_file.write(avatar.read())
                    avatar_file.close()
                    icon = os.path.join(self.configdir, self.SRV_NAME,
                           str(entry.user.id))

            m = Message(entry.id, 
                        '%s (%s)' % (entry.user.name, entry.user.screen_name),
                        entry.text,
                        'http://twitter.com/%s/status/%u' % (entry.user.screen_name, entry.id),
                        icon)

 
            messages.append(m)

        return messages


