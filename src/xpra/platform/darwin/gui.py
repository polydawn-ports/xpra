# This file is part of Xpra.
# Copyright (C) 2011-2013 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

from xpra.platform.darwin.osx_tray import OSXTray
from xpra.platform.darwin.osx_menu import OSXMenuHelper

from xpra.log import Logger
log = Logger()

#for attention_request:
CRITICAL_REQUEST = 0
INFO_REQUEST = 10

macapp = None
def get_OSXApplication():
    global macapp
    if macapp is None:
        try:
            import gtkosx_application        #@UnresolvedImport
            macapp = gtkosx_application.Application()
        except:
            pass
    return macapp

try:
    from Carbon import Snd      #@UnresolvedImport
except:
    Snd = None


def make_tray_menu(client):
    return OSXMenuHelper(client)

def make_native_tray(menu_helper, delay_tray, tray_icon):
    return OSXTray(menu_helper, tray_icon)

def system_bell(self, *args):
    if Snd is None:
        return False
    Snd.SysBeep(1)
    return True