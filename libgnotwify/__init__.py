import os
import sys
import logging

APP_NAME = 'Gnotwify'
APP_SHORT_NAME = 'gnotwify'
SRV_NAME = 'twitter'

CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.' + APP_SHORT_NAME)
CONFIG_FILE = os.path.join(CONFIG_DIR, APP_SHORT_NAME + '.cfg')
CURRENT_DIR = os.path.realpath(os.path.dirname(sys.argv[0]))
LOG_FILENAME = os.path.join(CONFIG_DIR, APP_SHORT_NAME + '.log')
LOG_LEVELS = {'debug': logging.DEBUG,
                'info': logging.INFO,
                'warning': logging.WARNING,
                'error': logging.ERROR,
                'critical': logging.CRITICAL}

logging.basicConfig(filename=LOG_FILENAME, level=logging.INFO,
                    datefmt='%H:%M',
                    format='[%(asctime)s][%(levelname)s:%(name)s] %(message)s')
# Create config dir
# Need to be ported to GConf
if not os.path.exists(CONFIG_DIR):
    os.mkdir(CONFIG_DIR)
    f = open(CONFIG_FILE, 'w')
    configdata = "[main]\n" \
                "# to run without libnotify\n" \
                "disable_libnotify: 1\n" \
                "# Valid values for loglevel\n" \
                "# debug, info, warning, error, critical\n" \
                "loglevel: debug\n" \
                "username: myuser\n" \
                "password: mypass\n" \
                "interval: 35\n"
    f.write(configdata)
    f.close()
    print "This is the first time you run " + APP_NAME + "\n" \
        "You must edit your user and password in " + CONFIG_FILE + "\n" \
        "and re-run " + APP_NAME +"."
    sys.exit(1)
 
from libgnotwify.Message import Message
from libgnotwify.Gnotwify import Gnotwify, GnotwifyError

