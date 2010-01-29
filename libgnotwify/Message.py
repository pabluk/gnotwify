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

from libgnotwify import APP_NAME
try:
    import pynotify
except:
    loggin.warning("There is no support for libnotify.\n"
                   "Messages will be displayed on the terminal")

class Message:
    """Defines the message structure."""

    def __init__(self, id, title, summary, url, icon):
        self.id = id
        self.title = title
        self.summary = summary
        self.url = url
        self.icon = icon
        self.viewed = False
        self.displayed = False

    def show(self):
        """Send messages throug pynotify."""
        pynotify.init(APP_NAME)
        try:
            m = pynotify.Notification(self.title, self.summary, self.icon)
            m.show()
            return True
        except:
            return False

