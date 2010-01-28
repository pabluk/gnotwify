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
import sys
import logging
import pygtk
pygtk.require("2.0")
import gtk
import webbrowser

from libgnotwify import APP_NAME, CONFIG_DIR, CONFIG_FILE, CURRENT_DIR
from libgnotwify import Logger
from libgnotwify.services import TwitterService

gtk.gdk.threads_init()

class Gnotwify:
    """A class that contains all services."""

    def __init__(self, status_icon):
        self.logger = logging.getLogger(APP_NAME)
        self.logger.debug("Started")
        self.services = []
        self._register_services()
        self._load_config()

        self.menu = gtk.Menu()

        status_icon.set_from_file(
            os.path.join(CURRENT_DIR, 'icons', 'twitter-inactive.png'))

        status_icon.connect('activate', self.on_status_icon_activate)
        status_icon.connect('popup-menu', self.on_status_icon_popup_menu,
            self.menu, status_icon)

        status_icon.set_visible(True)

    def on_status_icon_activate(self, widget, data=None):
        print "click..."

    def on_status_icon_popup_menu(self, widget, button, time, menu, status_icon):
        if button == 3:
            if menu:
                def open_browser(item, url):
                    webbrowser.open(url)

                def quit(widget, status_icon):
                    status_icon.set_visible(False)
                    self.services[0].stop()
                    gtk.main_quit()

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

                menu.show_all()
                menu.popup(None, None, None, 3, time)
        pass
    
    def _register_services(self):
        """Add the services available to the array of services."""
        availables = dict(Twitter=TwitterService)
        for name in iter(availables):
            self.services.append(availables[name]())

    def _load_config(self):
        """Load the required settings for each service."""
        for service in self.services:
            service.load_config()

    def start(self):
        """Start a thread for each registered service."""
        for service in self.services:
            service.start()



