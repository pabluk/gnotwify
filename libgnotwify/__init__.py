import os
import sys
import glib
import logging

APP_NAME = 'Gnotwify'
APP_SHORT_NAME = 'gnotwify'
SRV_NAME = 'twitter'

CONFIG_DIR = os.path.join(glib.get_user_config_dir(), APP_SHORT_NAME)
DATA_DIR = os.path.join(glib.get_user_data_dir(), APP_SHORT_NAME)
CACHE_DIR = os.path.join(glib.get_user_cache_dir(), APP_SHORT_NAME)
CURRENT_DIR = os.path.realpath(os.path.dirname(sys.argv[0]))

CONFIG_FILE = os.path.join(CONFIG_DIR, APP_SHORT_NAME + '.cfg')
LOG_FILENAME = os.path.join(CACHE_DIR, APP_SHORT_NAME + '.log')
LOG_LEVELS = {'debug': logging.DEBUG,
              'info': logging.INFO,
              'warning': logging.WARNING,
              'error': logging.ERROR,
              'critical': logging.CRITICAL}

logging.basicConfig(level=logging.INFO,
                    datefmt='%H:%M',
                    format='[%(asctime)s][%(levelname)s:%(name)s] %(message)s')

from libgnotwify.Message import Message
from libgnotwify.Gnotwify import Gnotwify, GnotwifyError

