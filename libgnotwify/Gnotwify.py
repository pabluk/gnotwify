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
import gnomekeyring
import webbrowser
import pynotify

import twitter

from libgnotwify import APP_NAME, SRV_NAME, CONFIG_DIR, CONFIG_FILE, \
                        DATA_DIR, CACHE_DIR, CURRENT_DIR, LOG_LEVELS
from libgnotwify import Message

gtk.gdk.threads_init()

class Gnotwify(Thread):
    """Threading class base for services."""

    stopthread = Event()

    def __init__(self, status_icon):

        self.messages = []
        self.disable_libnotify = False
        self.username = ''
        self.password = ''
        self.interval = 35
        self.last_id = None
        self.loglevel = 'debug'
        self.logger = logging.getLogger(APP_NAME)
        self.logger.setLevel(LOG_LEVELS.get(self.loglevel, logging.INFO))
        self.dialog = None
        self.force_update = False

        if not os.path.exists(CONFIG_DIR):
            os.mkdir(CONFIG_DIR)

        if not os.path.exists(CONFIG_FILE):
            # Create a config file with default values
            self._save_config()

        if not os.path.exists(DATA_DIR):
            os.mkdir(DATA_DIR)

        if not os.path.exists(CACHE_DIR):
            os.mkdir(CACHE_DIR)

        Thread.__init__(self, name=SRV_NAME)
        self.logger.debug("Thread started")

        self._load_config()

        self.updates_locked = False
        self.status_icon = status_icon

        self.status_icon.set_from_file(os.path.join(CURRENT_DIR, 'icons', 
                                                    'twitter-inactive.png'))

        self.status_icon.connect('activate', self.on_status_icon_activate)
        self.status_icon.connect('popup-menu', self.on_status_icon_popup_menu)

        status_icon.set_visible(True)

    def _load_config(self):
        """Load configuration settings for Gnotwify."""
        config = ConfigParser.ConfigParser()

        config.read(CONFIG_FILE)
        self.disable_libnotify = config.getboolean("main",
                                                   "disable_libnotify")
        self.loglevel = config.get("main", "loglevel")
        self.logger.setLevel(LOG_LEVELS.get(self.loglevel, logging.INFO))
        self.interval = int(config.get('main', "interval"))
        self.username = config.get('main', "username")
        password = self._get_password_from_keyring()
        if password:
            self.password = password
        else:
            self.password = ''

    def _save_config(self):
        """Store settings in the config file."""

        f = open(CONFIG_FILE, 'w')
        configdata = "[main]\n" 
        configdata += "# to run without libnotify\n"
        configdata += "disable_libnotify: %s\n" % (self.disable_libnotify)
        configdata += "# Valid values for loglevel\n"
        configdata += "# debug, info, warning, error, critical\n"
        configdata += "loglevel: %s\n" % (self.loglevel)
        configdata += "username: %s\n" % (self.username)
        configdata += "interval: %d\n" % (self.interval)
        f.write(configdata)
        f.close()

        stored_pass = self._get_password_from_keyring()
        if stored_pass:
            if stored_pass != self.password:
                self._set_password_to_keyring()
        else:
            self._set_password_to_keyring()

    def _update_messages(self, new_messages):
        """Update the array of messages."""
        if new_messages:
            self.messages.extend(new_messages)
            self.set_last_id()

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

    def set_last_id(self):
        try:
            self.last_id = self.messages[-1].id  
        except:
            self.last_id = None

    def _load_messages(self):
        """Load messages state."""
        filename = os.path.join(DATA_DIR, SRV_NAME + '.dat')
        if os.path.exists(filename):
            msgs_data = open(filename, 'r')
            self.messages = pickle.load(msgs_data)
            self.logger.debug("Loaded messages")
            self.set_last_id()
        else:
            self.logger.debug("Messages file does not exist")
        return

    def _save_messages(self):
        """Store messages state."""
        filename = os.path.join(DATA_DIR, SRV_NAME + '.dat')
        msgs_data = open(filename, 'w')
        pickle.dump(self.messages, msgs_data)
        self.logger.debug("Saved messages")
        return

    def _preferences_dialog(self, menu_item=None):
        if self.dialog:
            self.dialog.present()
            return
        self.updates_locked = True

        dialog = gtk.Dialog("Preferences", None,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                             gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        dialog.set_has_separator(True)

        label_username = gtk.Label("Username:")
        label_password = gtk.Label("Password:")
        label_interval = gtk.Label("Update interval:")

        entry_username = gtk.Entry()
        entry_username.set_text(self.username)
        entry_password = gtk.Entry()
        entry_password.set_visibility(False)
        entry_password.set_text(self.password)
        adj = gtk.Adjustment(35, 35, 600, 5, 50, 0)
        spinbtn_interval = gtk.SpinButton(adj)
        spinbtn_interval.set_numeric(True)

        hbox_username = gtk.HBox()
        hbox_username.pack_start(label_username)
        hbox_username.pack_start(entry_username)
        hbox_password = gtk.HBox()
        hbox_password.pack_start(label_password)
        hbox_password.pack_start(entry_password)
        hbox_interval = gtk.HBox()
        hbox_interval.pack_start(label_interval)
        hbox_interval.pack_start(spinbtn_interval)

        vbox_twitter = gtk.VBox(True, 4)
        vbox_twitter.set_border_width(4)
        vbox_twitter.pack_start(hbox_username)
        vbox_twitter.pack_start(hbox_password)
        vbox_twitter.pack_start(hbox_interval)

        checkbtn_libnotify = gtk.CheckButton("Show notifications " \
                                             "using libnotify")

        frame_twitter = gtk.Frame("<b>Twitter account</b>")
        label = frame_twitter.get_label_widget()
        label.set_use_markup(True)
        frame_twitter.set_shadow_type(gtk.SHADOW_NONE)
        frame_twitter.add(vbox_twitter)

        frame_misc = gtk.Frame("<b>Miscellaneous</b>")
        label = frame_misc.get_label_widget()
        label.set_use_markup(True)
        frame_misc.set_shadow_type(gtk.SHADOW_NONE)
        frame_misc.add(checkbtn_libnotify)

        vbox = gtk.VBox(False, 20)
        vbox.set_border_width(8)
        vbox.pack_start(frame_twitter)
        vbox.pack_start(frame_misc)

        dialog.vbox.pack_start(vbox)

        def response(dialog, response,
                     username, password, interval, libnotify):
            if response == gtk.RESPONSE_ACCEPT:
                self.username = username.get_text()
                self.password = password.get_text()
                self.interval = interval.get_value_as_int()
                self.disable_libnotify = libnotify.get_active()
                self._save_config()
                self.logger.debug("Preferences saved")
                # Try connect again
                self.force_update = True
                self.stopthread.set()

            self.dialog = None
            self.updates_locked = False
            dialog.destroy()

        dialog.connect("response", response, entry_username,
                       entry_password, spinbtn_interval, checkbtn_libnotify)

        self.dialog = dialog
        dialog.show_all()


    def _get_updates(self):
        """
        Retrieves updates from Twitter API and return an array of entries.
        """
        statuses = []
        api = twitter.Api(self.username, self.password)

        try:
            statuses = api.GetFriendsTimeline(since_id=self.last_id)
        except (urllib2.HTTPError, twitter.TwitterError):
            self.logger.debug("Authentication error")
            self._preferences_dialog()
        except urllib2.URLError:
            raise UpdateError, "Update error. Check your internet connection"
        except:
            raise UnknownError, "Unknown error"
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

            icon = os.path.join(CACHE_DIR, str(entry.user.id))
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
                    avatar_file = open(os.path.join(CACHE_DIR, 
                                                    str(entry.user.id)), 'wb')
                    avatar_file.write(avatar.read())
                    avatar_file.close()
                    icon = os.path.join(CACHE_DIR, str(entry.user.id))

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
        while not self.stopthread.isSet() or self.force_update:
            if self.force_update:
                self.force_update = False
                self.stopthread.clear()

            if not self.updates_locked:
                try:
                    entries = self._get_updates()
                except GnotwifyError as error:
                    self.logger.error(error)
                else:
                    new_messages = self._normalize_entries(entries)
                    self._update_messages(new_messages)
                    self._save_messages()
                    if self.unseen_messages() > 0:
                        self.icon_activate(True)
                        if new_messages:
                            self.show_notification('%d tweets unseen' % (self.unseen_messages()))

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

    def on_status_icon_activate(self, status_icon, data=None):
        """On click action mark all messages as seen."""
        self.updates_locked = True

        def on_item_activate(item, id):
            """Mark a message as read and open default browser."""
            status_link = ''
            for message in self.messages:
                if not message.viewed:
                    if message.id < id:
                        message.viewed = True
                    elif message.id == id:
                        message.viewed = True
                        status_link = message.url
            self._save_messages()
            if self.unseen_messages() > 0:
                self.icon_activate(True)
            else:
                self.icon_activate(False)
            open_browser(item=None, url=status_link)

        def open_browser(item, url):
            """Open the message url in a default browser."""
            webbrowser.open(url)

        def mark_all_as_seen(item, data=None):
            """Mark all messages as seen."""
            self.mark_all_as_seen()

        def on_menu_deactivate(menu, data=None):
            """Enable icon status update on menu deactivate."""
            self.updates_locked = False

        menu = gtk.Menu()
        menu.connect('deactivate', on_menu_deactivate)

        if self.unseen_messages() > 0:
            menu_item = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
            menu_item.set_name('GtkTweetMenuItem')
            menu_item.set_label('Mark all as seen')
            menu_item.connect('activate', mark_all_as_seen)
            menu.prepend(menu_item)

            menu_item = gtk.SeparatorMenuItem()
            menu_item.set_name('GtkTweetSeparatorMenuItem')
            menu.prepend(menu_item)

        item = gtk.ImageMenuItem('Twitter home')
        icon = gtk.Image()
        icon.set_from_file(os.path.join(CURRENT_DIR,
                                       'icons','browser.png'))
        item.set_image(icon)
        item.connect('activate', open_browser, 'http://twitter.com')
        menu.append(item)

        for message in self.messages:
            if not message.viewed:
                message.displayed = True

                menu_item = gtk.ImageMenuItem()
                icon = gtk.Image()
                icon.set_from_pixbuf(gtk.gdk.pixbuf_new_from_file_at_size(message.icon, 32, 32))
                menu_item.set_image(icon)

                label = gtk.Label('%s' % (message.summary))
                label.set_use_underline(False)
                label.set_line_wrap(True)
                label.set_width_chars(35)
                label.set_max_width_chars(35)
                label.set_alignment(0,0.5)

                menu_item.add(label)

                menu_item.set_name('GtkTweetMenuItem')
                menu_item.connect('activate',
                                  on_item_activate, message.id)
                menu.prepend(menu_item)

        menu.show_all()
        menu.popup(None, None, gtk.status_icon_position_menu, 3, 0, status_icon)

    def on_status_icon_popup_menu(self, status_icon,
                                 button, timestamp, data=None):
        """Create and show the popup menu."""
        if button == 3:
            self.updates_locked = True

            def quit(item, status_icon):
                """Exit application."""
                status_icon.set_visible(False)
                self.stop()
                gtk.main_quit()

            def on_menu_deactivate(menu, data=None):
                """Enable icon status update on menu deactivate."""
                self.updates_locked = False

            menu = gtk.Menu()
            menu.connect('deactivate', on_menu_deactivate)

            item = gtk.ImageMenuItem(gtk.STOCK_PREFERENCES)
            item.connect('activate', self._preferences_dialog)
            menu.append(item)

            item = gtk.SeparatorMenuItem()
            menu.append(item)

            item = gtk.ImageMenuItem(gtk.STOCK_QUIT)
            item.connect('activate', quit, status_icon)
            menu.append(item)

            menu.show_all()
            menu.popup(None, None, gtk.status_icon_position_menu,
                       3, timestamp, status_icon)

    def _set_password_to_keyring(self):
        if self.username == '':
            return False

        keyring = gnomekeyring.get_default_keyring_sync()
        display_name = 'HTTP secret for %s at twitter.com' % (self.username)
        type = gnomekeyring.ITEM_NETWORK_PASSWORD
        
        # just a utility function to create attrs easily.
        def parse(s):
           ret = {}
           try:
               ret = dict([(k,v) for k,v in [x.split(':') for x in s.split(',')] if k and v])
           except ValueError:
               pass
           return ret
        
        # create attrs :: {} (dict)
        attrs = {
         'user':None, 'domain':None, 'server':None, 'object':None,
          'protocol':None, 'authtype':None, 'port':None,
        }
        usr_attrs = parse("server:twitter.com,user:%s,protocol:http" % (self.username))
        attrs.update(usr_attrs) 
        
        try:
            id = gnomekeyring.item_create_sync(keyring, type, display_name, usr_attrs, self.password, True)
        except gnomekeyring.Error, e:
            return False
        return True
        
    def _get_password_from_keyring(self):
        try:
            results = gnomekeyring.find_network_password_sync(user=self.username, server='twitter.com', protocol='http')
        except gnomekeyring.NoMatchError:
            return None
        return results[0]["password"]

    def show_notification(self, title, summary=None):
        """Send messages throug pynotify."""
        icon = os.path.join(CURRENT_DIR, 'icons', 'twitter-icon.png')
        pynotify.init(APP_NAME)
        try:
            notification = pynotify.Notification(title, summary, icon)
            notification.show()
            return True
        except:
            return False


class GnotwifyError(Exception): pass
class UpdateError(GnotwifyError): pass
class UnknownError(GnotwifyError): pass

