# This file is part of Parti.
# Copyright (C) 2010-2013 Antoine Martin <antoine@devloop.org.uk>
# Parti is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import sys
import os

#this is here so we can expose the "platform" module
#before we import xpra.platform
import platform as python_platform
assert python_platform
from xpra.platform import DEFAULT_SSH_CMD

from wimpiggy.util import AdHocStruct
from wimpiggy.gobject_compat import import_gobject, is_gtk3
gobject = import_gobject()
try:
    import Image
    assert Image
    _has_PIL = True
except:
    _has_PIL = False
ENCODINGS = []
if is_gtk3():
    """ with gtk3, we get png via cairo out of the box
        but we need PIL for the others:
    """
    ENCODINGS.append("png")
    if _has_PIL:
        ENCODINGS.append("jpeg")
        ENCODINGS.append("rgb24")
else:
    """ with gtk2, we get rgb24 via gdk pixbuf out of the box
        but we need PIL for the others:
    """
    if _has_PIL:
        ENCODINGS.append("png")
        ENCODINGS.append("jpeg")
    ENCODINGS.append("rgb24")
#we need rgb24 for x264 and vpx (as well as the cython bindings and libraries):
if "rgb24" in ENCODINGS:
    try:
        from xpra import vpx            #@UnusedImport
        try:
            from xpra.vpx import codec      #@UnusedImport @UnresolvedImport @Reimport
            ENCODINGS.insert(0, "vpx")
        except Exception, e:
            print("cannot load vpx codec: %s" % e)
    except ImportError, e:
        #the vpx module does not exist
        #xpra was probably built with --without-vpx
        pass
    try:
        from xpra import x264           #@UnusedImport
        try:
            from xpra.x264 import codec     #@UnusedImport @UnresolvedImport
            ENCODINGS.insert(0, "x264")
        except Exception, e:
            print("cannot load x264 codec: %s" % e)
    except ImportError, e:
        #the x264 module does not exist
        #xpra was probably built with --without-x264
        pass
    try:
        from xpra.webm.decode import DecodeRGB      #@UnusedImport
        from xpra.webm.encode import EncodeRGB      #@UnusedImport
        ENCODINGS.append("webp")
    except ImportError, e:
        #the webm module does not exist
        #xpra was probably built with --without-webp
        pass
    except Exception, e:
        print("cannot load webp: %s" % e)

ENCRYPTION_CIPHERS = []
try:
    from Crypto.Cipher import AES
    assert AES
    ENCRYPTION_CIPHERS.append("AES")
except:
    pass





# we end up initializing gstreamer here and it does things
# we don't want with sys.argv, so hack around it:
saved_args = sys.argv
sys.argv = sys.argv[:1]
try:
    from xpra.sound import gstreamer_util   #@UnusedImport
    HAS_SOUND = True
except:
    HAS_SOUND = False
sys.argv = saved_args

def get_codecs(is_speaker, is_server):
    if not HAS_SOUND:
        return []
    try:
        from xpra.sound.gstreamer_util import can_encode, can_decode
        if (is_server and is_speaker) or (not is_server and not is_speaker):
            return can_encode()
        else:
            return can_decode()
    except Exception, e:
        print("failed to get list of codecs: %s" % e)
        return []

def show_codec_help(is_server, speaker_codecs, microphone_codecs):
    all_speaker_codecs = get_codecs(True, is_server)
    invalid_sc = [x for x in speaker_codecs if x not in all_speaker_codecs]
    hs = "help" in speaker_codecs
    if hs:
        print("speaker codecs available: %s" % (", ".join(all_speaker_codecs)))
    elif len(invalid_sc):
        print("WARNING: some of the specified speaker codecs are not available: %s" % (", ".join(invalid_sc)))
        for x in invalid_sc:
            speaker_codecs.remove(x)
    elif len(speaker_codecs)==0:
        speaker_codecs += all_speaker_codecs

    all_microphone_codecs = get_codecs(True, is_server)
    invalid_mc = [x for x in microphone_codecs if x not in all_microphone_codecs]
    hm = "help" in microphone_codecs
    if hm:
        print("microphone codecs available: %s" % (", ".join(all_microphone_codecs)))
    elif len(invalid_mc):
        print("WARNING: some of the specified microphone codecs are not available: %s" % (", ".join(invalid_mc)))
        for x in invalid_mc:
            microphone_codecs.remove(x)
    elif len(microphone_codecs)==0:
        microphone_codecs += all_microphone_codecs
    return hm or hs


def get_default_socket_dir():
    return os.environ.get("XPRA_SOCKET_DIR", "~/.xpra")

def get_build_info():
    info = []
    try:
        from xpra.build_info import BUILT_BY, BUILT_ON, BUILD_DATE, REVISION, LOCAL_MODIFICATIONS
        info.append("Built on %s by %s" % (BUILT_ON, BUILT_BY))
        if BUILD_DATE:
            info.append(BUILD_DATE)
        if int(LOCAL_MODIFICATIONS)==0:
            info.append("revision %s" % REVISION)
        else:
            info.append("revision %s with %s local changes" % (REVISION, LOCAL_MODIFICATIONS))
    except Exception, e:
        print("Error: could not find the build information: %s", e)
    return info


def read_config(conf_file):
    """
        Parses a config file into a dict of strings.
        If the same key is specified more than once,
        the value for this key will be an array of strings.
    """
    d = {}
    f = open(conf_file, "rU")
    lines = []
    for line in f:
        sline = line.strip().rstrip('\r\n').strip()
        if len(sline) == 0:
            continue
        if sline[0] in ( '!', '#' ):
            continue
        lines.append(sline)
    f.close()
    #aggregate any lines with trailing bacakslash
    agg_lines = []
    l = ""
    for line in lines:
        if line.endswith("\\"):
            l += line[:-1]
        else:
            l += line
            agg_lines.append(l)
            l = ""
    if len(l)>0:
        #last line had a trailing backslash... meh
        agg_lines.append(l)
    #parse name=value pairs:
    for sline in agg_lines:
        if sline.find("=")<=0:
            continue
        props = sline.split("=", 1)
        assert len(props)==2
        name = props[0].strip()
        value = props[1].strip()
        current_value = d.get(name)
        if current_value:
            if type(current_value)==list:
                d[name] = current_value + [value]
            else:
                d[name] = [current_value, value]
        else:
            d[name] = value
    return  d

def read_xpra_conf(conf_dir):
    """
        Reads an "xpra.conf" file from the given directory,
        returns a dict with values as strings and arrays of strings.
    """
    d = {}
    if not os.path.exists(conf_dir) or not os.path.isdir(conf_dir):
        return  d
    conf_file = os.path.join(conf_dir, 'xpra.conf')
    if not os.path.exists(conf_file) or not os.path.isfile(conf_file):
        return  d
    return read_config(conf_file)

def read_xpra_defaults():
    """
        Reads the global "xpra.conf" and then the user-specific one.
        (the latter overrides values from the former)
        returns a dict with values as strings and arrays of strings.
    """
    #first, read the global defaults:
    if sys.platform.startswith("win"):
        conf_dir = os.path.dirname(sys.executable)
    elif sys.prefix == '/usr':
        conf_dir = '/etc/xpra'
    else:
        conf_dir = sys.prefix + '/etc/xpra/'
    defaults = read_xpra_conf(conf_dir)
    #now load the per-user config over it:
    if sys.platform.startswith("win"):
        conf_dir = os.path.join(os.environ.get("APPDATA"), "Xpra")
    else:
        conf_dir = os.path.expanduser("~/.xpra")
    user_defaults = read_xpra_conf(conf_dir)
    for k,v in user_defaults.items():
        defaults[k] = v
    return defaults


ALL_OPTIONS = {
                    #string options:
                    "encoding"          : str,
                    "title"             : str,
                    "host"              : str,
                    "username"          : str,
                    "remote-xpra"       : str,
                    "session-name"      : str,
                    "dock-icon"         : str,
                    "tray-icon"         : str,
                    "window-icon"       : str,
                    "password"          : str,
                    "password-file"     : str,
                    "pulseaudio-command": str,
                    "encryption"        : str,
                    "mode"              : str,
                    "ssh"               : str,
                    "xvfb"              : str,
                    "socket-dir"        : str,
                    "log-file"          : str,
                    "mode"              : str,
                    #int options:
                    "quality"           : int,
                    "min-quality"       : int,
                    "speed"             : int,
                    "min-speed"         : int,
                    "port"              : int,
                    "compression_level" : int,
                    "dpi"               : int,
                    #float options:
                    "max-bandwidth"     : float,
                    "auto-refresh-delay": float,
                    #boolean options:
                    "debug"             : bool,
                    "daemon"            : bool,
                    "use-display"       : bool,
                    "no-tray"           : bool,
                    "clipboard"         : bool,
                    "pulseaudio"        : bool,
                    "mmap"              : bool,
                    "mmap-group"        : bool,
                    "speaker"           : bool,
                    "microphone"        : bool,
                    "readonly"          : bool,
                    "keyboard-sync"     : bool,
                    "pings"             : bool,
                    "cursors"           : bool,
                    "bell"              : bool,
                    "notifications"     : bool,
                    "system-tray"       : bool,
                    "sharing"           : bool,
                    "delay-tray"        : bool,
                    "windows"           : bool,
                    "autoconnect"       : bool,
                    "exit-with-children": bool,
                    #arrays of strings (default value, allowed options):
                    "speaker-codec"     : list,
                    "microphone-codec"  : list,
                    "key-shortcut"      : list,
                    "start-child"       : list,
                    "bind-tcp"          : list,
               }
#lowest common denominator here
#(the xpra.conf file shipped is generally better tuned than this - especially for 'xvfb')
try:
    import getpass
    username = getpass.getuser()
except:
    username = ""
GLOBAL_DEFAULTS = {
                    "encoding"          : ENCODINGS[0],
                    "title"             : "@title@ on @client-machine@",
                    "host"              : "",
                    "username"          : username,
                    "remote-xpra"       : ".xpra/run-xpra",
                    "session-name"      : "",
                    "dock-icon"         : "",
                    "tray-icon"         : "",
                    "window-icon"       : "",
                    "password"          : "",
                    "password-file"     : "",
                    "pulseaudio_command": "",
                    "encryption"        : "",
                    "mode"              : "tcp",
                    "ssh"               : DEFAULT_SSH_CMD,
                    "xvfb"              : "Xvfb +extension Composite -screen 0 3840x2560x24+32 -nolisten tcp -noreset -auth $XAUTHORITY",
                    "socket-dir"        : os.environ.get("XPRA_SOCKET_DIR") or '~/.xpra',
                    "log-file"          : "$DISPLAY.log",
                    "quality"           : -1,
                    "min-quality"       : 50,
                    "speed"             : -1,
                    "min-speed"         : -1,
                    "port"              : -1,
                    "compression_level" : 3,
                    "dpi"               : 96,
                    "max-bandwidth"     : 0.0,
                    "auto-refresh-delay": 0.25,
                    "debug"             : False,
                    "daemon"            : True,
                    "use-display"       : False,
                    "no-tray"           : False,
                    "clipboard"         : True,
                    "pulseaudio"        : True,
                    "mmap"              : True,
                    "mmap-group"        : False,
                    "speaker"           : True,
                    "microphone"        : True,
                    "readonly"          : False,
                    "keyboard-sync"     : True,
                    "pings"             : False,
                    "cursors"           : True,
                    "bell"              : True,
                    "notifications"     : True,
                    "system-tray"       : True,
                    "sharing"           : False,
                    "delay-tray"        : False,
                    "windows"           : True,
                    "autoconnect"       : False,
                    "exit-with-children": False,
                    "speaker-codec"     : ["mp3"],
                    "microphone-codec"  : ["mp3"],
                    "key-shortcut"      : ["Meta+Shift+F4:quit"],
                    "bind-tcp"          : None,
                    "start-child"       : None,
                    }
MODES = ["tcp", "tcp + aes", "ssh"]
def validate_in_list(x, options):
    if x in options:
        return None
    return "must be in %s" % (", ".join(options))
OPTIONS_VALIDATION = {
                    "encoding"          : lambda x : validate_in_list(x, ENCODINGS), 
                    "mode"              : lambda x : validate_in_list(x, MODES),
                    }
#fields that got renamed:
CLONES = {
            "quality"       : "jpeg-quality",
          }
#TODO:
#"speaker-codec"     : [""],
#"microphone-codec"  : [""],


def validate_config(d={}):
    """
        Validates all the options given in a dict with fields as keys and
        strings or arrays of strings as values.
        Each option is strongly typed and invalid value are discarded.
        We get the required datatype from GLOBAL_DEFAULTS
    """
    nd = {}
    for k, v in d.items():
        vt = ALL_OPTIONS.get(k)
        if vt is None:
            print("invalid key: %s" % k)
            continue
        if vt==str:
            if type(v)!=str:
                print("invalid value for '%s': %s (string required)" % (k, type(v)))
                continue
        elif vt==int or vt==float:
            if type(v)==str:
                v = v.lower()
            if v=="auto":
                v = -1
            try:
                v = vt(v)
            except Exception, e:
                print("cannot parse value '%s' for '%s' as a type %s: %s" % (v, k, vt, e))
                continue
        elif vt==bool:
            if type(v)==str:
                v = v.lower()
            if v in ["yes", "true", "1", "on"]:
                v = True
            elif v in ["no", "false", "0", "off"]:
                v = False
            else:
                print("cannot parse value '%s' for '%s' as a boolean" % (v, k))
                continue
        elif vt==list:
            if type(v)==str:
                #could just be that we specified it only once..
                v = [v]
            elif type(v)==list or v==None:
                #ok so far..
                pass
            else:
                print("invalid value for '%s': %s (a string or list of strings is required)" % (k, type(v)))
                continue
        else:
            print("Error: unknown option type for '%s': %s" % (k, vt))
        validation = OPTIONS_VALIDATION.get(k)
        if validation and v is not None:
            msg = validation(v)
            if msg:
                print("invalid value for '%s': %s, %s" % (k, v, msg))
                continue
        nd[k] = v
    return nd


def make_defaults_struct():
    #populate config with default values:
    defaults = read_xpra_defaults()
    validated = validate_config(defaults)
    options = GLOBAL_DEFAULTS.copy()
    options.update(validated)
    for k,v in CLONES.items():
        if k in options:
            options[v] = options[k]
    config = AdHocStruct()
    for k,v in options.items():
        attr_name = k.replace("-", "_")
        setattr(config, attr_name, v)
    return config


def main():
    print("default configuration: %s" % make_defaults_struct())


if __name__ == "__main__":
    main()
