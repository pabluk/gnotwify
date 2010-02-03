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

"""Define classes related to notifier service."""

import os
import sys
import pickle
import urllib2
import logging
import ConfigParser
from threading import Thread, Event
import pygtk
pygtk.require("2.0")
import gtk
import webbrowser
import textwrap


import twitter

from libgnotwify import APP_NAME, SRV_NAME, CONFIG_DIR, CONFIG_FILE, \
                        CURRENT_DIR, LOG_LEVELS
from libgnotwify import Message

gtk.gdk.threads_init()

class Gnotwify(Thread):
    """Threading class base for services."""

    stopthread = Event()

    def __init__(self, status_icon):

        self.messages = []
        self.disable_libnotify = False
        self.logger = logging.getLogger(APP_NAME)

        Thread.__init__(self, name=SRV_NAME)
        self.logger.debug("Thread started")

        self._load_config()

        self.icon_locked = False
        self.status_icon = status_icon

        self.status_icon.set_from_file(os.path.join(CURRENT_DIR, 'icons', 
                                                    'twitter-inactive.png'))

        self.status_icon.connect('activate', self.on_status_icon_activate)
        self.status_icon.connect('popup-menu', self.on_status_icon_popup_menu)

        status_icon.set_visible(True)

    def _load_config(self):
        """Load configuration settings for NotifyAll."""
        config = ConfigParser.ConfigParser()

        config.read(CONFIG_FILE)
        self.disable_libnotify = config.getboolean("main",
                                                   "disable_libnotify")
        self.loglevel = config.get("main", "loglevel")
        self.logger.setLevel(LOG_LEVELS.get(self.loglevel, logging.INFO))
        self.username = config.get('main', "username")
        self.password = config.get('main', "password")
        self.interval = int(config.get('main', "interval"))

        # if doesn't exist make a directory to store cached profile images
        if not os.path.exists(CONFIG_DIR + "/" + SRV_NAME):
            os.mkdir(CONFIG_DIR + "/" + SRV_NAME)


    def _update_messages(self, new_messages):
        """Update the array of messages."""
        # Fixed: maybe this could be improved
        for new_message in new_messages:

            for message in self.messages:
                if new_message.id == message.id:
                    if message.viewed:
                        new_message.viewed = True
                    if message.displayed:
                        new_message.displayed = True
                    break

        self.messages = new_messages
        return

    def _showunseen_messages(self):
        """Shows the messages unseen."""
        for msg in self.messages:
            if not msg.viewed:
                if not self.disable_libnotify and \
                   os.environ.has_key('DISPLAY'):
                    if not msg.show():
                        break
                self.logger.info(msg.title + ": " + msg.summary)
                msg.viewed = True

    def unseen_messages(self):
        """Returns the number of unseen messages."""
        i = 0
        for message in self.messages:
            if not message.viewed:
                i += 1
        return i

    def _reset_messages_displayed(self):
        """Set messages not viewed as undisplayed."""
        for message in self.messages:
            if not message.viewed:
                message.displayed = False

    def _reverse(self, data):
        """Returns the same array in reverse order."""
        for index in range(len(data)-1, -1, -1):
            yield data[index]

    def _load_messages(self):
        """Load messages state."""
        filename = os.path.join(CONFIG_DIR, SRV_NAME + '.dat')
        if os.path.exists(filename):
            msgs_data = open(filename, 'r')
            self.messages = pickle.load(msgs_data)
            self.logger.debug("Loaded messages")
        else:
            self.logger.debug("Messages file does not exist")
        return

    def _save_messages(self):
        """Store messages state."""
        filename = os.path.join(CONFIG_DIR, SRV_NAME + '.dat')
        msgs_data = open(filename, 'w')
        pickle.dump(self.messages, msgs_data)
        self.logger.debug("Saved messages")
        return

    def _get_updates(self):
        """
        Retrieves updates from Twitter API and return an array of entries.
        """
        statuses = []
        api = twitter.Api(self.username, self.password)

        try:
            statuses = api.GetFriendsTimeline()
        except:
            raise GnotwifyError('Update error')
        else:
            self.logger.debug("Updated")
        
        return statuses

    def _normalize_entries(self, entries):
        """
        Normalizes and sorts an array of entries and returns
        an array of messages.
        """
        messages = []

        for entry in self._reverse(entries):

            icon = os.path.join(CONFIG_DIR, SRV_NAME, str(entry.user.id))
            if not os.path.exists(icon):
                try:
                    avatar = urllib2.urlopen(entry.user.profile_image_url)
                    self.logger.debug("Fetching image profile for %s" % 
                                     (entry.user.screen_name))
                except urllib2.URLError, urllib2.HTTPError:
                    self.logger.error("Error fetching image profile for %s" % 
                                     (entry.user.screen_name))
                    icon = os.path.join(CURRENT_DIR, 'icons', 'twitter.png')
                else:
                    avatar_file = open(os.path.join(CONFIG_DIR, SRV_NAME, 
                                                    str(entry.user.id)), 'wb')
                    avatar_file.write(avatar.read())
                    avatar_file.close()
                    icon = os.path.join(CONFIG_DIR, SRV_NAME,
                                        str(entry.user.id))

            msg = Message(entry.id, 
                          '%s (%s)' %
                          (entry.user.name, entry.user.screen_name),
                          entry.text,
                          'http://twitter.com/%s/status/%u' % 
                          (entry.user.screen_name, entry.id),
                          icon)
 
            messages.append(msg)

        return messages

    def run(self):
        """
        Start the loop to update the service and display their own messages.
        """
        self._load_messages()
        self._reset_messages_displayed()
        while not self.stopthread.isSet():
            if not self.icon_locked:
                try:
                    entries = self._get_updates()
                except GnotwifyError as error:
                    self.logger.error(error.description)
                else:
                    new_messages = self._normalize_entries(entries)
                    self._update_messages(new_messages)
                    self._save_messages()
                    if self.unseen_messages() > 0:
                        self.icon_activate(True)

            self.logger.debug("Unseen message(s): %d of %d" %
                             (self.unseen_messages(), len(self.messages)))
            self.stopthread.wait(self.interval)

    def stop(self):
        """Stop the current thread."""
        self.stopthread.set()

    def icon_activate(self, activate):
        """Change the status icon to indicate activity."""
        if activate:
            self.status_icon.set_from_file(os.path.join(CURRENT_DIR, 'icons',
                                                       'twitter.png'))
        else:
            self.status_icon.set_from_file(os.path.join(CURRENT_DIR, 'icons',
                                                       'twitter-inactive.png'))

    def mark_all_as_seen(self):
        """Mark all messages displayed and not seen as seen."""
        activity = False

        for message in self.messages:
            if message.displayed and not message.viewed:
                message.viewed = True
                activity = True

        if activity:
            self._save_messages()

        self.icon_activate(False)

    def on_status_icon_activate(self, widget, data=None):
        """On click action mark all messages as seen."""
        self.mark_all_as_seen()

    def on_status_icon_popup_menu(self, status_icon,
                                 button, timestamp, data=None):
        """Create and show the popup menu."""
        if button == 3:
            self.icon_locked = True

            def open_browser(item, url):
                """Open the message url in a default browser."""
                webbrowser.open(url)

            def quit(item, status_icon):
                """Exit application."""
                status_icon.set_visible(False)
                self.stop()
                gtk.main_quit()

            def mark_all_as_seen(item, data=None):
                """Mark all messages as seen."""
                self.mark_all_as_seen()

            def on_menu_deactivate(menu, data=None):
                """Enable icon status update on menu deactivate."""
                self.icon_locked = False

            menu = gtk.Menu()
            menu.connect('deactivate', on_menu_deactivate)
            item = gtk.ImageMenuItem('Twitter home')
            icon = gtk.Image()
            icon.set_from_file(os.path.join(CURRENT_DIR,
                                           'icons','browser.png'))
            item.set_image(icon)
            item.connect('activate', open_browser, 'http://twitter.com')
            menu.append(item)

            item = gtk.SeparatorMenuItem()
            menu.append(item)

            item = gtk.ImageMenuItem(gtk.STOCK_QUIT)
            item.connect('activate', quit, status_icon)
            menu.append(item)

            if self.unseen_messages() > 0:
                menu_item = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
                menu_item.set_name('GtkTweetMenuItem')
                menu_item.set_label('Mark all as seen')
                menu_item.connect('activate', mark_all_as_seen)
                menu.prepend(menu_item)

                menu_item = gtk.SeparatorMenuItem()
                menu_item.set_name('GtkTweetSeparatorMenuItem')
                menu.prepend(menu_item)

            for message in self.messages:
                if not message.viewed:
                    message.displayed = True
                    menu_item = gtk.ImageMenuItem(
                                            textwrap.fill(message.summary, 35))
                    for widget in menu_item.get_children():
                        if widget.get_name() == 'GtkAccelLabel':
                            widget.set_use_underline(False)
                            icon = gtk.Image()
                            icon.set_from_pixbuf(
                                gtk.gdk.pixbuf_new_from_file_at_size(
                                    message.icon, 24, 24))
                            menu_item.set_image(icon)
                            menu_item.set_name('GtkTweetMenuItem')
                            menu_item.connect('activate',
                                             open_browser, message.url)
                            menu.prepend(menu_item)

            menu.show_all()
            menu.popup(None, None, None, 3, timestamp)


class GnotwifyError(Exception):
    """Class that define the Gnotwify errors."""
    def __init__(self, description):
        self.description = description

    def __str__(self):
        return repr(self.descripton)

