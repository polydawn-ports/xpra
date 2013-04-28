# This file is part of Xpra.
# Copyright (C) 2010 Nathaniel Smith <njs@pobox.com>
# Copyright (C) 2011-2013 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import os as _os
import sys as _sys

if _os.name == "nt":
    from win32.keyboard import Keyboard            #@UnusedImport
elif _sys.platform.startswith("darwin"):
    from darwin.keyboard import Keyboard           #@UnusedImport @Reimport
elif _os.name == "posix":
    from xposix.keyboard import Keyboard           #@UnusedImport @Reimport
else:
    raise OSError("Unknown OS %s" % (_os.name))