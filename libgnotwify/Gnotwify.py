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

from libgnotwify import APP_NAME, SRV_NAME, CONFIG_DIR, CONFIG_FILE, CURRENT_DIR
from libgnotwify import Message
from libgnotwify import Logger

gtk.gdk.threads_init()

class Gnotwify(Thread):
    """Threading class base for services."""

    stopthread = Event()

    def __init__(self, status_icon):

        self.last_id = 0
        self.messages = []
        self.disable_libnotify = False
        self.logger = logging.getLogger(APP_NAME)

        Thread.__init__(self, name=SRV_NAME)
        self.logger.debug("Thread started")

        self._load_config()

        self.icon_locked = False
        self.menu = gtk.Menu()

        status_icon.set_from_file(
            os.path.join(CURRENT_DIR, 'icons', 'twitter-inactive.png'))

        status_icon.connect('activate', self.on_status_icon_activate)
        status_icon.connect('popup-menu', self.on_status_icon_popup_menu,
            self.menu, status_icon)
        self.menu.connect('deactivate', self.on_menu_deactivate)


        status_icon.set_visible(True)

    def _load_config(self):
        """Load configuration settings for NotifyAll."""
        LOG_LEVELS = {'debug': logging.DEBUG,
                      'info': logging.INFO,
                      'warning': logging.WARNING,
                      'error': logging.ERROR,
                      'critical': logging.CRITICAL}

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
                if not self.disable_libnotify and os.environ.has_key('DISPLAY'):
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

    def _reverse(self, data):
        """Returns the same array in reverse order."""
        for index in range(len(data)-1, -1, -1):
            yield data[index]

    def _load_messages(self):
        filename = os.path.join(CONFIG_DIR, SRV_NAME + '.dat')
        if os.path.exists(filename):
            file = open(filename, 'r')
            self.messages = pickle.load(file)
            self.logger.debug("Loaded messages")
        else:
            self.logger.debug("Messages file does not exist")
        return

    def _save_messages(self):
        filename = os.path.join(CONFIG_DIR, SRV_NAME + '.dat')
        file = open(filename, 'w')
        pickle.dump(self.messages, file)
        self.logger.debug("Saved messages")
        return

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

            icon = os.path.join(CONFIG_DIR, SRV_NAME, str(entry.user.id))
            if not os.path.exists(icon):
                try:
                    avatar = urllib2.urlopen(entry.user.profile_image_url)
                    self.logger.debug("Fetching image profile for " + entry.user.screen_name)
                except:
                    self.logger.error("Error fetching image profile for " + entry.user.screen_name)
                    icon = os.path.join(os.path.realpath(os.path.dirname(sys.argv[0])), 'icons', 'twitter.png')
                else:
                    avatar_file = open(os.path.join(CONFIG_DIR, SRV_NAME, str(entry.user.id)), 'wb')
                    avatar_file.write(avatar.read())
                    avatar_file.close()
                    icon = os.path.join(CONFIG_DIR, SRV_NAME,
                           str(entry.user.id))

            m = Message(entry.id, 
                        '%s (%s)' % (entry.user.name, entry.user.screen_name),
                        entry.text,
                        'http://twitter.com/%s/status/%u' % (entry.user.screen_name, entry.id),
                        icon)

 
            messages.append(m)

        return messages

    def run(self):
        """Start the loop to update the service and display their own messages."""
        self._load_messages()
        while not self.stopthread.isSet():
            try:
                entries = self._get_updates()
            except ServiceError as error:
                self.logger.error(error.description)
            else:
                new_messages = self._normalize_entries(entries)
                self._update_messages(new_messages)
                self._save_messages()
                #self._showunseen_messages()

            self.logger.debug("Unseen message(s): " + str(self.unseen_messages()) + " of " + str(len(self.messages)))
            self.stopthread.wait(self.interval)

    def stop(self):
        self.stopthread.set()

    def icon_activate(self, activate):
        if not self.icon_locked and activate:
            pass

    def on_status_icon_activate(self, widget, data=None):
        print "click..."

    def on_menu_deactivate(self, widget, data=None):
        self.icon_locked = False

    def on_status_icon_popup_menu(self, widget, button, time, menu, status_icon):
        if button == 3:
            if menu:
                self.icon_locked = True
                def open_browser(item, url):
                    webbrowser.open(url)

                def quit(item, status_icon):
                    status_icon.set_visible(False)
                    self.stop()
                    gtk.main_quit()

                def mark_all_as_seen(item):
                    for item in menu.get_children():
                        if item.get_name() == 'GtkTweetMenuItem' or item.get_name() == 'GtkTweetSeparatorMenuItem':
                            menu.remove(item)
                    for message in self.messages:
                        if message.displayed:
                            message.viewed = True
                        

                #new_messages = False

                if len(menu.get_children()) < 3:
                    item = gtk.ImageMenuItem('Twitter home')
                    icon = gtk.Image()
                    icon.set_from_file(
                        os.path.join(CURRENT_DIR, 'icons', 'browser.png'))
                    item.set_image(icon)
                    item.connect('activate', open_browser, 'http://twitter.com')
                    menu.append(item)

                    item = gtk.SeparatorMenuItem()
                    menu.append(item)

                    item = gtk.ImageMenuItem(gtk.STOCK_QUIT)
                    item.connect('activate', quit, status_icon)
                    menu.append(item)

                if self.unseen_messages() > 0 and len(menu.get_children()) <= 3:
                    menuItem = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
                    menuItem.set_name('GtkTweetMenuItem')
                    menuItem.set_label('Mark all as seen')
                    menuItem.connect('activate', mark_all_as_seen)
                    menu.prepend(menuItem)

                    menuItem = gtk.SeparatorMenuItem()
                    menuItem.set_name('GtkTweetSeparatorMenuItem')
                    menu.prepend(menuItem)

                for message in self.messages:
                    if not message.viewed and not message.displayed:
                        #new_messages = True
                        message.displayed = True
                        menuItem = gtk.ImageMenuItem(textwrap.fill(message.summary, 35))
                        for widget in menuItem.get_children():
                            if widget.get_name() == 'GtkAccelLabel':
                                widget.set_use_underline(False)
                                icon = gtk.Image()
                                icon.set_from_pixbuf(gtk.gdk.pixbuf_new_from_file_at_size(message.icon, 24, 24))
                                menuItem.set_image(icon)
                                menuItem.set_name('GtkTweetMenuItem')
                                menuItem.connect('activate', open_browser, message.url)
                                menu.prepend(menuItem)

                #if new_messages:
                #    show_notification("%d tweets unseen" % (twitterSrv._get_unseen_messages()))
                   
                menu.show_all()
                menu.popup(None, None, None, 3, time)
        pass


class GnotwifyError(Exception):
    def __init__(self, description):
        self.description = description

    def __str__(self):
        return repr(self.descripton)

