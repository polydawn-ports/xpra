#!/usr/bin/env python

# This file is part of Xpra.
# Copyright (C) 2010-2013 Antoine Martin <antoine@devloop.org.uk>
# Copyright (C) 2008, 2009, 2010 Nathaniel Smith <njs@pobox.com>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

##############################################################################
# FIXME: Cython.Distutils.build_ext leaves crud in the source directory.  (So
# does the make_constants hack.)

import glob
from distutils.core import setup
from distutils.extension import Extension
import subprocess, sys, traceback
import os.path
import stat

print(" ".join(sys.argv))

import xpra
from xpra.platform.features import LOCAL_SERVERS_SUPPORTED, SHADOW_SUPPORTED

WIN32 = sys.platform.startswith("win")
OSX = sys.platform.startswith("darwin")


#*******************************************************************************
# Most of the options below can be modified on the command line
# using --with-OPTION or --without-OPTION
# only the default values are specified here:
#*******************************************************************************

shadow_ENABLED = SHADOW_SUPPORTED
server_ENABLED = LOCAL_SERVERS_SUPPORTED or shadow_ENABLED
client_ENABLED = True

x11_ENABLED = not WIN32 and not OSX
argb_ENABLED = True
gtk2_ENABLED = client_ENABLED
gtk3_ENABLED = client_ENABLED
qt4_ENABLED = client_ENABLED
opengl_ENABLED = client_ENABLED
html5_ENABLED = True

bencode_ENABLED = True
cython_bencode_ENABLED = True
rencode_ENABLED = True
cymaths_ENABLED = True
cyxor_ENABLED = True
clipboard_ENABLED = True
Xdummy_ENABLED = None           #none means auto-detect
sound_ENABLED = True

enc_proxy_ENABLED = True
enc_x264_ENABLED = True
x264_static_ENABLED = False
vpx_ENABLED = True
vpx_static_ENABLED = False
dec_avcodec_ENABLED = True
dec_avcodec2_ENABLED = False
avcodec_static_ENABLED = False
avcodec2_static_ENABLED = False
csc_swscale_ENABLED = True
csc_cython_ENABLED = True
swscale_static_ENABLED = False
webp_ENABLED = True
nvenc_ENABLED = False
csc_nvcuda_ENABLED = False
csc_opencl_ENABLED = True

verbose_ENABLED = False
warn_ENABLED = True
strict_ENABLED = True
debug_ENABLED = False
PIC_ENABLED = True

#allow some of these flags to be modified on the command line:
SWITCHES = ("enc_x264", "x264_static",
            "nvenc",
            "dec_avcodec", "avcodec_static",
            "dec_avcodec2", "avcodec2_static",
            "csc_swscale", "swscale_static",
            "csc_nvcuda", "csc_opencl", "csc_cython",
            "vpx", "vpx_static",
            "webp",
            "rencode", "bencode", "cython_bencode",
            "clipboard",
            "server", "client", "x11",
            "gtk2", "gtk3", "qt4", "html5",
            "sound", "cyxor", "cymaths", "opengl", "argb",
            "warn", "strict", "shadow", "debug", "PIC", "Xdummy", "verbose")
HELP = "-h" in sys.argv or "--help" in sys.argv
if HELP:
    setup()
    print("Xpra specific build and install switches:")
    for x in SWITCHES:
        d = vars()["%s_ENABLED" % x]
        with_str = "  --with-%s" % x
        without_str = "  --without-%s" % x
        if d is True or d is False:
            default_str = str(d)
        else:
            default_str = "auto-detect"
        print("%s or %s (default: %s)" % (with_str.ljust(25), without_str.ljust(25), default_str))
    sys.exit(0)

filtered_args = []
for arg in sys.argv:
    #deprecated flag:
    if arg == "--enable-Xdummy":
        Xdummy_ENABLED = True
        continue
    matched = False
    for x in SWITCHES:
        if arg=="--with-%s" % x:
            vars()["%s_ENABLED" % x] = True
            matched = True
            break
        elif arg=="--without-%s" % x:
            vars()["%s_ENABLED" % x] = False
            matched = True
            break
    if not matched:
        filtered_args.append(arg)
sys.argv = filtered_args
if "clean" not in sys.argv:
    switches_info = {}
    for x in SWITCHES:
        switches_info[x] = vars()["%s_ENABLED" % x]
    print("build switches: %s" % switches_info)
    if LOCAL_SERVERS_SUPPORTED:
        print("Xdummy build flag: %s" % Xdummy_ENABLED)

    #sanity check the flags:
    if clipboard_ENABLED and not server_ENABLED and not gtk2_ENABLED and not gtk3_ENABLED:
        print("Warning: clipboard can only be used with the server or one of the gtk clients!")
        clipboard_ENABLED = False
    if opengl_ENABLED and not gtk2_ENABLED:
        print("Warning: opengl can only be used with the gtk2 clients")
        opengl_ENABLED = False
    if shadow_ENABLED and not server_ENABLED:
        print("Warning: shadow requires server to be enabled!")
        shadow_ENABLED = False
    if cymaths_ENABLED and not server_ENABLED:
        print("Warning: cymaths requires server to be enabled!")
        cymaths_ENABLED = False
    if x11_ENABLED and WIN32:
        print("Warning: enabling x11 on MS Windows is unlikely to work!")
    if client_ENABLED and not gtk2_ENABLED and not gtk3_ENABLED and not qt4_ENABLED:
        print("Warning: client is enabled but none of the client toolkits are!?")
    if not argb_ENABLED and (x11_ENABLED or OSX):
        print("Error: argb is required for x11 and osx builds!")
        exit(1)
    if not client_ENABLED and not server_ENABLED:
        print("Error: you must build at least the client or server!")
        exit(1)


#*******************************************************************************
# build options, these may get modified further down..
#
setup_options = {}
setup_options["name"] = "xpra"
setup_options["author"] = "Antoine Martin"
setup_options["author_email"] = "antoine@devloop.org.uk"
setup_options["version"] = xpra.__version__
setup_options["url"] = "http://xpra.org/"
setup_options["download_url"] = "http://xpra.org/src/"
setup_options["description"] = "Xpra: 'screen for X' utility"

xpra_desc = "'screen for X' -- a tool to detach/reattach running X programs"
setup_options["long_description"] = xpra_desc
data_files = []
setup_options["data_files"] = data_files
packages = [
          "xpra", "xpra.scripts", "xpra.keyboard",
          "xpra.net", "xpra.codecs", "xpra.codecs.xor",
          ]
setup_options["packages"] = packages
py2exe_excludes = []       #only used on win32
py2exe_includes = []       #only used on win32
ext_modules = []
cmdclass = {}


def remove_packages(*pkgs):
    global packages
    for x in pkgs:
        if x in packages:
            packages.remove(x)
def add_packages(*pkgs):
    global packages
    for x in pkgs:
        if x not in packages:
            packages.append(x)

#*******************************************************************************
# Utility methods for building with Cython
def cython_version_check(min_version):
    try:
        from Cython.Compiler.Version import version as cython_version
    except ImportError, e:
        sys.exit("ERROR: Cannot find Cython: %s" % e)
    from distutils.version import LooseVersion
    if LooseVersion(cython_version) < LooseVersion(".".join([str(x) for x in min_version])):
        sys.exit("ERROR: Your version of Cython is too old to build this package\n"
                 "You have version %s\n"
                 "Please upgrade to Cython %s or better"
                 % (cython_version, ".".join([str(part) for part in min_version])))

def cython_add(extension, min_version=(0, 14, 0)):
    #gentoo does weird things, calls --no-compile with build *and* install
    #then expects to find the cython modules!? ie:
    #python2.7 setup.py build -b build-2.7 install --no-compile --root=/var/tmp/portage/x11-wm/xpra-0.7.0/temp/images/2.7
    if "--no-compile" in sys.argv and not ("build" in sys.argv and "install" in sys.argv):
        return
    global ext_modules, cmdclass
    cython_version_check(min_version)
    from Cython.Distutils import build_ext
    ext_modules.append(extension)
    cmdclass = {'build_ext': build_ext}

def add_to_keywords(kw, key, *args):
    values = kw.setdefault(key, [])
    for arg in args:
        values.append(arg)
def remove_from_keywords(kw, key, value):
    values = kw.get(key)
    if values and value in values:
        values.remove(value)


PYGTK_PACKAGES = ["pygobject-2.0", "pygtk-2.0"]

GCC_VERSION = []
def get_gcc_version():
    global GCC_VERSION
    if len(GCC_VERSION)==0:
        cmd = [os.environ.get("CC", "gcc"), "-v"]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output, _ = proc.communicate()
        status = proc.wait()
        if status==0:
            V_LINE = "gcc version "
            for line in output.decode("utf8").splitlines():
                if line.startswith(V_LINE):
                    v_str = line[len(V_LINE):].split(" ")[0]
                    for p in v_str.split("."):
                        try:
                            GCC_VERSION.append(int(p))
                        except:
                            break
                    print("found gcc version: %s" % ".".join([str(x) for x in GCC_VERSION]))
                    break
    return GCC_VERSION

def make_constants_pxi(constants_path, pxi_path):
    constants = []
    for line in open(constants_path):
        data = line.split("#", 1)[0].strip()
        # data can be empty ''...
        if not data:
            continue
        # or a pair like 'cFoo "Foo"'...
        elif len(data.split()) == 2:
            (pyname, cname) = data.split()
            constants.append((pyname, cname))
        # or just a simple token 'Foo'
        else:
            constants.append(data)
    out = open(pxi_path, "w")
    out.write("cdef extern from *:\n")
    ### Apparently you can't use | on enum's?!
    # out.write("    enum MagicNumbers:\n")
    # for const in constants:
    #     if isinstance(const, tuple):
    #         out.write('        %s %s\n' % const)
    #     else:
    #         out.write('        %s\n' % (const,))
    for const in constants:
        if isinstance(const, tuple):
            out.write('    unsigned int %s %s\n' % const)
        else:
            out.write('    unsigned int %s\n' % (const,))

    out.write("constants = {\n")
    for const in constants:
        if isinstance(const, tuple):
            pyname = const[0]
        else:
            pyname = const
        out.write('    "%s": %s,\n' % (pyname, pyname))
    out.write("}\n")

def make_constants(*paths):
    base = os.path.join(os.getcwd(), *paths)
    constants_file = "%s.txt" % base
    pxi_file = "%s.pxi" % base
    reason = None
    if not os.path.exists(pxi_file):
        reason = "no pxi file"
    elif os.path.getctime(pxi_file)<os.path.getctime(constants_file):
        reason = "pxi file out of date"
    elif os.path.getctime(pxi_file)<os.path.getctime(__file__):
        reason = "newer build file"
    if reason:
        if verbose_ENABLED:
            print("(re)generating %s (%s):" % (pxi_file, reason))
        make_constants_pxi(constants_file, pxi_file)

# Tweaked from http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/502261
def pkgconfig(*packages_options, **ekw):
    kw = dict(ekw)
    if len(packages_options)>0:
        package_names = []
        #find out which package name to use from potentially many options
        #and bail out early with a meaningful error if we can't find any valid options
        for package_options in packages_options:
            #for this package options, find the ones that work
            valid_option = None
            if type(package_options)==str:
                options = [package_options]     #got given just one string
            else:
                assert type(package_options)==list
                options = package_options       #got given a list of options
            for option in options:
                cmd = ["pkg-config", "--exists", option]
                proc = subprocess.Popen(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                status = proc.wait()
                if status==0:
                    valid_option = option
                    break
            if not valid_option:
                sys.exit("ERROR: cannot find a valid pkg-config package for %s" % (options,))
            package_names.append(valid_option)
        if verbose_ENABLED and list(packages_options)!=list(package_names):
            print("pkgconfig(%s,%s) using package names=%s" % (packages_options, ekw, package_names))
        flag_map = {'-I': 'include_dirs',
                    '-L': 'library_dirs',
                    '-l': 'libraries'}
        cmd = ["pkg-config", "--libs", "--cflags", "%s" % (" ".join(package_names),)]
        proc = subprocess.Popen(cmd, env=os.environ, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (output, _) = proc.communicate()
        status = proc.wait()
        if status!=0:
            sys.exit("ERROR: call to pkg-config ('%s') failed" % " ".join(cmd))
        if sys.version>='3':
            output = output.decode('utf-8')
        for token in output.split():
            if token[:2] in flag_map:
                add_to_keywords(kw, flag_map.get(token[:2]), token[2:])
            else: # throw others to extra_link_args
                add_to_keywords(kw, 'extra_link_args', token)
            for k, v in kw.items(): # remove duplicates
                kw[k] = list(set(v))
    if warn_ENABLED:
        add_to_keywords(kw, 'extra_compile_args', "-Wall")
        add_to_keywords(kw, 'extra_link_args', "-Wall")
    if strict_ENABLED:
        #these are almost certainly real errors since our code is "clean":
        if get_gcc_version()>=[4, 4]:
            eifd = "-Werror=implicit-function-declaration"
        else:
            eifd = "-Werror-implicit-function-declaration"
        add_to_keywords(kw, 'extra_compile_args', eifd)
    if PIC_ENABLED:
        add_to_keywords(kw, 'extra_compile_args', "-fPIC")
    if debug_ENABLED:
        add_to_keywords(kw, 'extra_compile_args', '-g')
        add_to_keywords(kw, 'extra_compile_args', '-ggdb')
        kw['cython_gdb'] = True
        if get_gcc_version()>=4.8:
            add_to_keywords(kw, 'extra_compile_args', '-fsanitize=address')
            add_to_keywords(kw, 'extra_link_args', '-fsanitize=address')
    #add_to_keywords(kw, 'include_dirs', '.')
    if verbose_ENABLED:
        print("pkgconfig(%s,%s)=%s" % (packages_options, ekw, kw))
    return kw


#*******************************************************************************
def get_xorg_conf_and_script():
    if not server_ENABLED:
        return "etc/xpra/client-only/xpra.conf", False

    def Xvfb():
        return "etc/xpra/Xvfb/xpra.conf", False

    if sys.platform.find("bsd")>=0:
        print("Warning: sorry, no support for Xdummy on %s" % sys.platform)
        return Xvfb()

    XORG_BIN = None
    PATHS = os.environ.get("PATH").split(os.pathsep)
    for x in PATHS:
        xorg = os.path.join(x, "Xorg")
        if os.path.isfile(xorg):
            XORG_BIN = xorg
            break
    if not XORG_BIN:
        print("Xorg not found, cannot detect version or Xdummy support")
        return Xvfb()

    def Xorg_suid_check():
        xorg_stat = os.stat(XORG_BIN)
        if (xorg_stat.st_mode & stat.S_ISUID)!=0:
            if (xorg_stat.st_mode & stat.S_IROTH)==0:
                print("Xorg is suid and not readable, Xdummy support unavailable")
                return Xvfb()
            print("%s is suid and readable, using the xpra_Xdummy wrapper" % XORG_BIN)
            return "etc/xpra/xpra_Xdummy/xpra.conf", True
        else:
            print("using Xdummy config file")
            return "etc/xpra/Xdummy/xpra.conf", False

    if Xdummy_ENABLED is False:
        return Xvfb()
    elif Xdummy_ENABLED is True:
        print("Xdummy support specified as 'enabled', will detect suid mode")
        return Xorg_suid_check()
    else:
        print("Xdummy support unspecified, will try to detect")

    cmd = ["lsb_release", "-cs"]
    try:
        proc = subprocess.Popen(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, _ = proc.communicate()
        release = out.replace("\n", "")
        print("Found OS release: %s" % release)
        if release in ("raring", "saucy"):
            #yet another instance of Ubuntu breaking something
            print("Warning: Ubuntu '%s' breaks Xorg/Xdummy usage - using Xvfb fallback" % release)
            return  Xvfb()
    except Exception, e:
        print("failed to detect OS release using %s: %s" % (" ".join(cmd), e))

    #do live detection
    cmd = ["Xorg", "-version"]
    if verbose_ENABLED:
        print("detecting Xorg version using: %s" % str(cmd))
    try:
        proc = subprocess.Popen(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, _ = proc.communicate()
        V_LINE = "X.Org X Server "
        xorg_version = None
        for line in out.decode("utf8").splitlines():
            if line.startswith(V_LINE):
                v_str = line[len(V_LINE):]
                xorg_version = [int(x) for x in v_str.split(".")[:2]]
                break
        if not xorg_version:
            print("Xorg version could not be detected, Xdummy support unavailable")
            return Xvfb()
        if xorg_version<[1, 12]:
            print("Xorg version %s is too old, Xdummy support not available" % str(xorg_version))
            return Xvfb()
        print("found valid recent version of Xorg server: %s" % v_str)
        return Xorg_suid_check()
    except Exception, e:
        print("failed to detect Xorg version: %s" % e)
        print("not installing Xdummy support")
        traceback.print_exc()
        return  Xvfb()


#*******************************************************************************
if 'clean' in sys.argv or 'sdist' in sys.argv:
    #clean and sdist don't actually use cython,
    #so skip this (and avoid errors)
    def pkgconfig(*packages_options, **ekw):
        return {}
    #always include all platform code in this case:
    add_packages("xpra.platform.xposix",
                 "xpra.platform.win32",
                 "xpra.platform.darwin")
    #ensure we remove the files we generate:
    CLEAN_FILES = [
                   "xpra/gtk_common/gdk_atoms.c",
                   "xpra/x11/gtk_x11/constants.pxi",
                   "xpra/x11/gtk_x11/gdk_bindings.c",
                   "xpra/x11/gtk_x11/gdk_display_source.c",
                   "xpra/x11/bindings/constants.pxi",
                   "xpra/x11/bindings/wait_for_x_server.c",
                   "xpra/x11/bindings/keyboard_bindings.c",
                   "xpra/x11/bindings/display_source.c",
                   "xpra/x11/bindings/window_bindings.c",
                   "xpra/x11/bindings/randr_bindings.c",
                   "xpra/x11/bindings/core_bindings.c",
                   "xpra/x11/bindings/ximage.c",
                   "xpra/net/rencode/rencode.c",
                   "xpra/codecs/vpx/encoder.c",
                   "xpra/codecs/vpx/decoder.c",
                   "xpra/codecs/nvenc/encoder.c",
                   "xpra/codecs/nvenc/constants.pxi",
                   "xpra/codecs/enc_x264/encoder.c",
                   "xpra/codecs/enc_x264/constants.pxi",
                   "xpra/codecs/dec_avcodec/decoder.c",
                   "xpra/codecs/dec_avcodec/constants.pxi",
                   "xpra/codecs/dec_avcodec2/decoder.c",
                   "xpra/codecs/dec_avcodec2/constants.pxi",
                   "xpra/codecs/csc_swscale/colorspace_converter.c",
                   "xpra/codecs/csc_swscale/constants.pxi",
                   "xpra/codecs/csc_cython/colorspace_converter.c",
                   "xpra/codecs/xor/cyxor.c",
                   "xpra/codecs/argb/argb.c",
                   "xpra/server/stats/cymaths.c",
                   "etc/xpra/xpra.conf"]
    if sys.platform.startswith("win"):
        #on win32, the build creates ".pyd" files, clean those too:
        for x in list(CLEAN_FILES):
            if x.endswith(".c"):
                CLEAN_FILES.append(x[:-2]+".pyd")
    if 'clean' in sys.argv:
        CLEAN_FILES.append("xpra/build_info.py")
    for x in CLEAN_FILES:
        filename = os.path.join(os.getcwd(), x.replace("/", os.path.sep))
        if os.path.exists(filename):
            if verbose_ENABLED:
                print("removing Cython/build generated file: %s" % x)
            os.unlink(filename)

from add_build_info import record_build_info, record_src_info, has_src_info

if "clean" not in sys.argv:
    # Add build info to build_info.py file:
    record_build_info()

if "sdist" in sys.argv:
    record_src_info()

if "install" in sys.argv:
    #if installing from source tree rather than
    #from a source snapshot, we may not have a "src_info" file
    #so create one:
    if not has_src_info():
        record_src_info()


if 'clean' in sys.argv or 'sdist' in sys.argv:
    #take shortcut to skip cython/pkgconfig steps:
    setup(**setup_options)
    sys.exit(0)



def glob_recurse(srcdir):
    m = {}
    for root, _, files in os.walk(srcdir):
        for f in files:
            dirname = root[len(srcdir)+1:]
            filename = os.path.join(root, f)
            m.setdefault(dirname, []).append(filename)
    return m

#*******************************************************************************
if WIN32:
    # The Microsoft C library DLLs:
    # Unfortunately, these files cannot be re-distributed legally :(
    # So here is the md5sum so you can find the right version:
    # (you can find them in various packages, including Visual Studio 2008,
    # pywin32, etc...)
    import md5
    md5sums = {"Microsoft.VC90.CRT/Microsoft.VC90.CRT.manifest" : "37f44d535dcc8bf7a826dfa4f5fa319b",
               "Microsoft.VC90.CRT/msvcm90.dll"                 : "4a8bc195abdc93f0db5dab7f5093c52f",
               "Microsoft.VC90.CRT/msvcp90.dll"                 : "6de5c66e434a9c1729575763d891c6c2",
               "Microsoft.VC90.CRT/msvcr90.dll"                 : "e7d91d008fe76423962b91c43c88e4eb",
               "Microsoft.VC90.CRT/vcomp90.dll"                 : "f6a85f3b0e30c96c993c69da6da6079e",
               "Microsoft.VC90.MFC/Microsoft.VC90.MFC.manifest" : "17683bda76942b55361049b226324be9",
               "Microsoft.VC90.MFC/mfc90.dll"                   : "462ddcc5eb88f34aed991416f8e354b2",
               "Microsoft.VC90.MFC/mfc90u.dll"                  : "b9030d821e099c79de1c9125b790e2da",
               "Microsoft.VC90.MFC/mfcm90.dll"                  : "d4e7c1546cf3131b7d84b39f8da9e321",
               "Microsoft.VC90.MFC/mfcm90u.dll"                 : "371226b8346f29011137c7aa9e93f2f6",
               }
    # This is where I keep them, you will obviously need to change this value:
    C_DLLs = "C:\\"
    for dll_file, md5sum in md5sums.items():
        filename = os.path.join(C_DLLs, *dll_file.split("/"))
        if not os.path.exists(filename) or not os.path.isfile(filename):
            sys.exit("ERROR: DLL file %s is missing or not a file!" % filename)
        sys.stdout.write("* verifying md5sum for %s: " % filename)
        f = open(filename, mode='rb')
        data = f.read()
        f.close()
        m = md5.new()
        m.update(data)
        digest = m.hexdigest()
        assert digest==md5sum, "md5 digest for file %s does not match, expected %s but found %s" % (dll_file, md5sum, digest)
        sys.stdout.write("OK\n")
        sys.stdout.flush()
    #this should all be done with pkgconfig...
    #but until someone figures this out, the ugly path code below works
    #as long as you install in the same place or tweak the paths.

    #first some header crap so codecs can find the inttypes.h
    #and stdint.h:
    win32_include_dir = os.path.join(os.getcwd(), "win32")

    #cuda:
    cuda_path = "C:\\NVIDIA\CUDA\CUDAToolkit"
    cuda_include_dir   = os.path.join(cuda_path, "include")
    cuda_bin_dir       = os.path.join(cuda_path, "bin")

    #ffmpeg is needed for both swscale and x264:
    if dec_avcodec_ENABLED:
        assert not dec_avcodec2_ENABLED, "cannot enable both dec_avcodec and dec_avcodec2"
        libffmpeg_path = "C:\\ffmpeg-win32-bin"
    elif dec_avcodec2_ENABLED:
        assert not dec_avcodec_ENABLED, "cannot enable both dec_avcodec and dec_avcodec2"
        libffmpeg_path = "C:\\ffmpeg2-win32-bin"
    else:
        libffmpeg_path = "UNUSED"
    libffmpeg_include_dir   = os.path.join(libffmpeg_path, "include")
    libffmpeg_lib_dir       = os.path.join(libffmpeg_path, "lib")
    libffmpeg_bin_dir       = os.path.join(libffmpeg_path, "bin")
    #x264 (direct from build dir.. yuk - sorry!):
    x264_path ="C:\\x264"
    x264_include_dir    = x264_path
    x264_lib_dir        = x264_path
    x264_bin_dir        = x264_path
    # Same for vpx:
    # http://code.google.com/p/webm/downloads/list
    #the path after installing may look like this:
    #vpx_PATH="C:\\vpx-vp8-debug-src-x86-win32mt-vs9-v1.1.0"
    #but we use something more generic, without the version numbers:
    vpx_path = ""
    for p in ("C:\\vpx-1.3", "C:\\vpx-1.2", "C:\\vpx-1.1", "C:\\vpx-vp8"):
        if os.path.exists(p) and os.path.isdir(p):
            vpx_path = p
            break
    vpx_include_dir     = os.path.join(vpx_path, "include")
    vpx_lib_dir         = os.path.join(vpx_path, "lib", "Win32")
    if os.path.exists(os.path.join(vpx_lib_dir, "vpx.lib")):
        vpx_lib_names = ["vpx"]               #for libvpx 1.3.0
    elif os.path.exists(os.path.join(vpx_lib_dir, "vpxmd.lib")):
        vpx_lib_names = ["vpxmd"]             #for libvpx 1.2.0
    else:
        vpx_lib_names = ["vpxmt", "vpxmtd"]   #for libvpx 1.1.0

    # Same for PyGTK:
    # http://www.pygtk.org/downloads.html
    gtk2_path = "C:\\Python27\\Lib\\site-packages\\gtk-2.0"
    python_include_path = "C:\\Python27\\include"
    gtk2runtime_path        = os.path.join(gtk2_path, "runtime")
    gtk2_lib_dir            = os.path.join(gtk2runtime_path, "bin")
    gtk2_base_include_dir   = os.path.join(gtk2runtime_path, "include")

    pygtk_include_dir       = os.path.join(python_include_path, "pygtk-2.0")
    atk_include_dir         = os.path.join(gtk2_base_include_dir, "atk-1.0")
    gtk2_include_dir        = os.path.join(gtk2_base_include_dir, "gtk-2.0")
    gdkpixbuf_include_dir   = os.path.join(gtk2_base_include_dir, "gdk-pixbuf-2.0")
    glib_include_dir        = os.path.join(gtk2_base_include_dir, "glib-2.0")
    cairo_include_dir       = os.path.join(gtk2_base_include_dir, "cairo")
    pango_include_dir       = os.path.join(gtk2_base_include_dir, "pango-1.0")
    gdkconfig_include_dir   = os.path.join(gtk2runtime_path, "lib", "gtk-2.0", "include")
    glibconfig_include_dir  = os.path.join(gtk2runtime_path, "lib", "glib-2.0", "include")

    def checkdirs(*dirs):
        for d in dirs:
            if not os.path.exists(d) or not os.path.isdir(d):
                raise Exception("cannot find a directory which is required for building: %s" % d)

    def pkgconfig(*packages, **ekw):
        kw = dict(ekw)
        if len(packages)==0:
            return kw
        def add_to_PATH(bindir):
            if os.environ['PATH'].find(bindir)<0:
                os.environ['PATH'] = bindir + ';' + os.environ['PATH']
            if bindir not in sys.path:
                sys.path.append(bindir)
        if "libavcodec" in packages[0]:
            add_to_PATH(libffmpeg_bin_dir)
            add_to_keywords(kw, 'include_dirs', win32_include_dir, libffmpeg_include_dir)
            add_to_keywords(kw, 'libraries', "avcodec", "avutil")
            add_to_keywords(kw, 'extra_link_args', "/LIBPATH:%s" % libffmpeg_lib_dir)
            add_to_keywords(kw, 'extra_link_args', "/LIBPATH:%s" % libffmpeg_bin_dir)
            add_to_keywords(kw, 'extra_link_args', "/OPT:NOREF")
            checkdirs(libffmpeg_include_dir, libffmpeg_lib_dir, libffmpeg_bin_dir)
        elif "libswscale" in packages[0]:
            add_to_PATH(libffmpeg_bin_dir)
            add_to_keywords(kw, 'include_dirs', win32_include_dir, libffmpeg_include_dir)
            add_to_keywords(kw, 'libraries', "swscale", "avutil")
            add_to_keywords(kw, 'extra_link_args', "/LIBPATH:%s" % libffmpeg_lib_dir)
            add_to_keywords(kw, 'extra_link_args', "/LIBPATH:%s" % libffmpeg_bin_dir)
            add_to_keywords(kw, 'extra_link_args', "/OPT:NOREF")
            checkdirs(libffmpeg_include_dir, libffmpeg_lib_dir, libffmpeg_bin_dir)
        elif "x264" in packages[0]:
            add_to_PATH(libffmpeg_bin_dir)
            add_to_PATH(x264_bin_dir)
            add_to_keywords(kw, 'include_dirs', win32_include_dir, x264_include_dir)
            add_to_keywords(kw, 'libraries', "libx264")
            add_to_keywords(kw, 'extra_link_args', "/LIBPATH:%s" % x264_lib_dir)
            add_to_keywords(kw, 'extra_link_args', "/OPT:NOREF")
            checkdirs(x264_include_dir, x264_lib_dir)
        elif "vpx" in packages[0]:
            add_to_PATH(libffmpeg_bin_dir)
            add_to_keywords(kw, 'include_dirs', win32_include_dir, vpx_include_dir)
            add_to_keywords(kw, 'libraries', *vpx_lib_names)
            add_to_keywords(kw, 'extra_link_args', "/NODEFAULTLIB:LIBCMT")
            add_to_keywords(kw, 'extra_link_args', "/LIBPATH:%s" % vpx_lib_dir)
            add_to_keywords(kw, 'extra_link_args', "/OPT:NOREF")
            checkdirs(vpx_include_dir, vpx_lib_dir)
        elif "pygobject-2.0" in packages[0]:
            dirs = (python_include_path,
                    pygtk_include_dir, atk_include_dir, gtk2_include_dir,
                    gtk2_base_include_dir, gdkconfig_include_dir, gdkpixbuf_include_dir,
                    glib_include_dir, glibconfig_include_dir,
                    cairo_include_dir, pango_include_dir)
            add_to_keywords(kw, 'include_dirs', *dirs)
            checkdirs(*dirs)
        elif "cuda" in packages[0]:
            add_to_keywords(kw, 'include_dirs', win32_include_dir, cuda_include_dir)
            checkdirs(cuda_include_dir)
            data_files.append(('.', glob.glob("%s/*32*.dll" % cuda_bin_dir)))
        else:
            sys.exit("ERROR: unknown package config: %s" % str(packages))
        if debug_ENABLED:
            #Od will override whatever may be specified elsewhere
            #and allows us to use the debug switches,
            #at the cost of a warning...
            for flag in ('/Od', '/Zi', '/DEBUG', '/RTC1', '/GS'):
                add_to_keywords(kw, 'extra_compile_args', flag)
            add_to_keywords(kw, 'extra_link_args', "/DEBUG")
            kw['cython_gdb'] = True
        print("pkgconfig(%s,%s)=%s" % (packages, ekw, kw))
        return kw

    import py2exe    #@UnresolvedImport
    assert py2exe is not None

    def py2exe_exclude(*pkgs):
        global py2exe_excludes
        for x in pkgs:
            if x not in py2exe_excludes:
                py2exe_excludes.append(x)
    def py2exe_include(*pkgs):
        global py2exe_includes
        for x in pkgs:
            if x not in py2exe_includes:
                py2exe_includes.append(x)

    #with py2exe, we have to remove the default packages and let it figure it out the rest
    #(otherwise, we can't remove specific files from those packages)
    remove_packages("xpra", "xpra.scripts")
    def toggle_packages(enabled, *package_names):
        #on win32: we tell py2exe NOT to include them
        global packages
        if enabled:
            add_packages(*package_names)
        else:
            remove_packages(*package_names)
            #FIXME: this breaks things...
            # we need a better way of excluding packages with py2exe
            #py2exe_exclude(*package_names)

    add_packages("xpra.platform.win32")
    py2exe_exclude("xpra.platform.darwin", "xpra.platform.xposix")
    #UI applications (detached from shell: no text output if ran from cmd.exe)
    setup_options["windows"] = [
                    {'script': 'xpra/scripts/main.py',                      'icon_resources': [(1, "win32/xpra_txt.ico")],  "dest_base": "Xpra",},
                    {'script': 'xpra/gtk_common/gtk_view_keyboard.py',      'icon_resources': [(1, "win32/keyboard.ico")],  "dest_base": "GTK_Keyboard_Test",},
                    {'script': 'xpra/gtk_common/gtk_view_clipboard.py',     'icon_resources': [(1, "win32/clipboard.ico")], "dest_base": "GTK_Clipboard_Test",},
                    {'script': 'xpra/client/gtk2/client_launcher.py',       'icon_resources': [(1, "win32/xpra.ico")],      "dest_base": "Xpra-Launcher",},
              ]
    #Console: provide an Xpra_cmd.exe we can run from the cmd.exe shell
    console = [
                    {'script': 'win32/xpra_cmd.py',                     'icon_resources': [(1, "win32/xpra_txt.ico")],  "dest_base": "Xpra_cmd",},
                    {'script': 'xpra/codecs/loader.py',                 'icon_resources': [(1, "win32/encoding.ico")],  "dest_base": "Encoding_info",},
                    {'script': 'xpra/sound/gstreamer_util.py',          'icon_resources': [(1, "win32/gstreamer.ico")], "dest_base": "GStreamer_info",},
                    {'script': 'xpra/sound/src.py',                     'icon_resources': [(1, "win32/microphone.ico")],"dest_base": "Sound_Record",},
                    {'script': 'xpra/sound/sink.py',                    'icon_resources': [(1, "win32/speaker.ico")],   "dest_base": "Sound_Play",},
              ]
    if opengl_ENABLED:
        console.append({'script': 'xpra/client/gl/gl_check.py',            'icon_resources': [(1, "win32/opengl.ico")],    "dest_base": "OpenGL_check",})
    setup_options["console"] = console

    py2exe_include("cairo", "pango", "pangocairo", "atk", "glib", "gobject", "gio", "gtk.keysyms",
                        "Crypto", "Crypto.Cipher",
                        "hashlib",
                        "PIL",
                        "ctypes", "platform",
                        "win32con", "win32gui", "win32process", "win32api")
    dll_excludes = ["w9xpopen.exe","tcl85.dll", "tk85.dll"]
    py2exe_exclude(
                        #Tcl/Tk
                        "Tkconstants", "Tkinter", "tcl",
                        #PIL bits that import TK:
                        "_imagingtk", "PIL._imagingtk", "ImageTk", "PIL.ImageTk", "FixTk",
                        #formats we don't use:
                        "GimpGradientFile", "GimpPaletteFile", "BmpImagePlugin", "TiffImagePlugin",
                        #not used on win32:
                        "mmap",
                        #we handle GL separately below:
                        "OpenGL", "OpenGL_accelerate",
                        #this is a mac osx thing:
                        "ctypes.macholib",
                        #not used:
                        "curses", "email", "mimetypes", "mimetools", "pdb",
                        "urllib", "urllib2", "tty",
                        "ssl", "_ssl",
                        "cookielib", "BaseHTTPServer", "ftplib", "httplib", "fileinput",
                        "distutils", "setuptools", "doctest")

    if not cyxor_ENABLED or opengl_ENABLED:
        #we need numpy for opengl or as a fallback for the Cython xor module
        py2exe_include("numpy")
    else:
        py2exe_exclude("numpy",
                        "unittest", "difflib",  #avoid numpy warning (not an error)
                        "pydoc")

    if sound_ENABLED:
        py2exe_include("pygst", "gst", "gst.extend")
    else:
        py2exe_exclude("pygst", "gst", "gst.extend")

    if opengl_ENABLED:
        #for this hack to work, you must add "." to the sys.path
        #so python can load OpenGL from the install directory
        #(further complicated by the fact that "." is the "frozen" path...)
        import OpenGL, OpenGL_accelerate        #@UnresolvedImport
        import shutil
        print("*** copy PyOpenGL modules ***")
        for module_name, module in {"OpenGL" : OpenGL, "OpenGL_accelerate" : OpenGL_accelerate}.items():
            module_dir = os.path.dirname(module.__file__ )
            try:
                shutil.copytree(
                    module_dir, os.path.join("dist", module_name),
                    ignore = shutil.ignore_patterns("Tk")
                )
            except WindowsError, error:     #@UndefinedVariable
                if not "already exists" in str( error ):
                    raise
    setup_options["options"] = {
                                "py2exe": {
                                           "skip_archive"   : False,
                                           "optimize"       : 0,    #WARNING: do not change - causes crashes
                                           "unbuffered"     : True,
                                           "compressed"     : True,
                                           "skip_archive"   : False,
                                           "packages"       : packages,
                                           "includes"       : py2exe_includes,
                                           "excludes"       : py2exe_excludes,
                                           "dll_excludes"   : dll_excludes,
                                        }
                                }
    data_files += [
                   ('', ['COPYING']),
                   ('', ['README']),
                   ('', ['win32/website.url']),
                   ('', ['etc/xpra/client-only/xpra.conf']),
                   ('icons', glob.glob('win32\\*.ico')),
                   ('icons', glob.glob('icons\\*.*')),
                   ('Microsoft.VC90.CRT', glob.glob('%s\\Microsoft.VC90.CRT\\*.*' % C_DLLs)),
                   ('Microsoft.VC90.MFC', glob.glob('%s\\Microsoft.VC90.MFC\\*.*' % C_DLLs)),
                   ('', glob.glob('%s\\bin\\*.dll' % libffmpeg_path)),
                   ]
    if enc_x264_ENABLED:
        data_files.append(('', ['%s\\libx264.dll' % x264_bin_dir]))
    html5_dir = ''

    if webp_ENABLED:
        #Note: confusingly, the python bindings are called webm...
        #add the webp DLL to the output:
        #And since 0.2.1, you have to compile the DLL yourself..
        #the path after installing may look like this:
        #webp_DLL = "C:\\libwebp-0.3.1-windows-x86\\bin\\libwebp.dll"
        #but we use something more generic, without the version numbers:
        webp_DLL = "C:\\libwebp-windows-x86\\bin\\libwebp.dll"
        data_files.append(('', [webp_DLL]))
        #and its license:
        data_files.append(('webm', ["xpra/codecs/webm/LICENSE"]))


#*******************************************************************************
else:
    scripts = ["scripts/xpra", "scripts/xpra_launcher"]
    man_pages = ["man/xpra.1", "man/xpra_launcher.1"]
    data_files += [
                    ("share/man/man1", man_pages),
                    ("share/xpra", ["README", "COPYING"]),
                    ("share/xpra/icons", glob.glob("icons/*")),
                    ("share/applications", ["xdg/xpra_launcher.desktop", "xdg/xpra.desktop"]),
                    ("share/icons", ["xdg/xpra.png"])
                  ]
    html5_dir = "share/xpra/www"
    if webp_ENABLED:
        data_files.append(('share/xpra/webm', ["xpra/codecs/webm/LICENSE"]))

    add_packages("xpra", "xpra.platform")
    if OSX:
        #OSX package names (ie: gdk-x11-2.0 -> gdk-2.0, etc)
        PYGTK_PACKAGES += ["gdk-2.0", "gtk+-2.0"]
        add_packages("xpra.platform.darwin")
    else:
        PYGTK_PACKAGES += ["gdk-x11-2.0", "gtk+-x11-2.0"]
        add_packages("xpra.platform.xposix")
        #always include the wrapper in case we need it later:
        #(we remove it during the 'install' step below if it isn't actually needed)
        scripts.append("scripts/xpra_Xdummy")

    def toggle_packages(enabled, *package_names):
        global packages
        if enabled:
            add_packages(*package_names)

    #gentoo does weird things, calls --no-compile with build *and* install
    #then expects to find the cython modules!? ie:
    #> python2.7 setup.py build -b build-2.7 install --no-compile --root=/var/tmp/portage/x11-wm/xpra-0.7.0/temp/images/2.7
    #otherwise we use the flags to skip pkgconfig
    if ("--no-compile" in sys.argv or "--skip-build" in sys.argv) and not ("build" in sys.argv and "install" in sys.argv):
        def pkgconfig(*packages_options, **ekw):
            return {}
    if "install" in sys.argv:
        #prepare default [/usr/local]/etc configuration files:
        if sys.prefix == '/usr':
            etc_prefix = '/etc/xpra'
        else:
            etc_prefix = sys.prefix + '/etc/xpra'

        etc_files = []
        if server_ENABLED and x11_ENABLED:
            etc_files = ["etc/xpra/xorg.conf"]
            #figure out the version of the Xorg server:
            xorg_conf, use_Xdummy_wrapper = get_xorg_conf_and_script()
            if not use_Xdummy_wrapper and "scripts/xpra_Xdummy" in scripts:
                #if we're not using the wrapper, don't install it
                scripts.remove("scripts/xpra_Xdummy")
            etc_files.append(xorg_conf)
        data_files.append((etc_prefix, etc_files))
    setup_options["scripts"] = scripts


STATIC_COMMON_DEFS = pkgconfig()
remove_from_keywords(STATIC_COMMON_DEFS, 'extra_compile_args', '-fsanitize=address')
if os.name=="posix":
    STATIC_COMMON_DEFS.update({'include_dirs': ["/usr/local/include"],
                               'library_dirs': ["/usr/local/lib"]})


if html5_ENABLED:
    for k,v in glob_recurse("html5").items():
        if (k!=""):
            k = os.sep+k
        data_files.append((html5_dir+k, v))



#*******************************************************************************
toggle_packages(server_ENABLED, "xpra.server", "xpra.server.stats", "xpra.server.auth")
if WIN32 and not server_ENABLED:
    #with py2exe, we have to remove the default packages and let it figure it out...
    #(otherwise, we can't remove specific files from those packages)
    remove_packages("xpra", "xpra.scripts")

toggle_packages(server_ENABLED or gtk2_ENABLED or gtk3_ENABLED, "xpra.gtk_common", "xpra.clipboard")


toggle_packages(x11_ENABLED, "xpra.x11", "xpra.x11.gtk_x11", "xpra.x11.bindings")
if x11_ENABLED:
    make_constants("xpra", "x11", "bindings", "constants")
    make_constants("xpra", "x11", "gtk_x11", "constants")

    cython_add(Extension("xpra.x11.bindings.wait_for_x_server",
                ["xpra/x11/bindings/wait_for_x_server.pyx"],
                **pkgconfig("x11")
                ))
    cython_add(Extension("xpra.x11.bindings.display_source",
                ["xpra/x11/bindings/display_source.pyx"],
                **pkgconfig("x11")
                ))
    cython_add(Extension("xpra.x11.bindings.core_bindings",
                ["xpra/x11/bindings/core_bindings.pyx"],
                **pkgconfig("x11")
                ))
    cython_add(Extension("xpra.x11.bindings.randr_bindings",
                ["xpra/x11/bindings/randr_bindings.pyx"],
                **pkgconfig("x11", "xrandr")
                ))
    cython_add(Extension("xpra.x11.bindings.keyboard_bindings",
                ["xpra/x11/bindings/keyboard_bindings.pyx"],
                **pkgconfig("x11", "xtst", "xfixes")
                ))

    cython_add(Extension("xpra.x11.bindings.window_bindings",
                ["xpra/x11/bindings/window_bindings.pyx"],
                **pkgconfig("xtst", "xfixes", "xcomposite", "xdamage")
                ))
    cython_add(Extension("xpra.x11.bindings.ximage",
                ["xpra/x11/bindings/ximage.pyx"],
                **pkgconfig("xcomposite", "xdamage", "xext")
                ))

    #below uses gtk/gdk:
    cython_add(Extension("xpra.x11.gtk_x11.gdk_display_source",
                ["xpra/x11/gtk_x11/gdk_display_source.pyx"],
                **pkgconfig(*PYGTK_PACKAGES)
                ))
    GDK_BINDINGS_PACKAGES = PYGTK_PACKAGES + ["xfixes", "xdamage"]
    cython_add(Extension("xpra.x11.gtk_x11.gdk_bindings",
                ["xpra/x11/gtk_x11/gdk_bindings.pyx"],
                **pkgconfig(*GDK_BINDINGS_PACKAGES)
                ))
elif WIN32:
    #with py2exe, we have to remove the default packages and let it figure it out...
    #(otherwise, we can't remove specific files from those packages)
    remove_packages("xpra", "xpra.scripts")


if argb_ENABLED:
    toggle_packages(True, "xpra.codecs.argb")
    cython_add(Extension("xpra.codecs.argb.argb",
                ["xpra/codecs/argb/argb.pyx"]))

toggle_packages(client_ENABLED, "xpra.client", "xpra.client.notifications")
toggle_packages(client_ENABLED and gtk2_ENABLED or gtk3_ENABLED, "xpra.client.gtk_base")
toggle_packages(client_ENABLED and gtk2_ENABLED, "xpra.client.gtk2")
toggle_packages(client_ENABLED and gtk3_ENABLED, "xpra.client.gtk3")
toggle_packages(client_ENABLED and qt4_ENABLED, "xpra.client.qt4")
toggle_packages(client_ENABLED and gtk2_ENABLED or gtk3_ENABLED, "xpra.client.gtk_base")
toggle_packages(sound_ENABLED, "xpra.sound")
toggle_packages(webp_ENABLED, "xpra.codecs.webm")
toggle_packages(client_ENABLED and gtk2_ENABLED and opengl_ENABLED, "xpra.client.gl")

toggle_packages(clipboard_ENABLED, "xpra.clipboard")
if clipboard_ENABLED:
    cython_add(Extension("xpra.gtk_common.gdk_atoms",
                ["xpra/gtk_common/gdk_atoms.pyx"],
                **pkgconfig(*PYGTK_PACKAGES)
                ))

if cyxor_ENABLED:
    cython_add(Extension("xpra.codecs.xor.cyxor",
                ["xpra/codecs/xor/cyxor.pyx"],
                **pkgconfig()))

if cymaths_ENABLED:
    cython_add(Extension("xpra.server.stats.cymaths",
                ["xpra/server/stats/cymaths.pyx"],
                **pkgconfig()))



toggle_packages(csc_opencl_ENABLED, "xpra.codecs.csc_opencl")
toggle_packages(csc_nvcuda_ENABLED, "xpra.codecs.csc_nvcuda")
toggle_packages(enc_proxy_ENABLED, "xpra.codecs.enc_proxy")

toggle_packages(nvenc_ENABLED, "xpra.codecs.nvenc")
if nvenc_ENABLED:
    make_constants("xpra", "codecs", "nvenc", "constants")
    nvenc_pkgconfig = pkgconfig("nvenc3", "cuda")
    cython_add(Extension("xpra.codecs.nvenc.encoder",
                         ["xpra/codecs/nvenc/encoder.pyx"],
                         **nvenc_pkgconfig), min_version=(0, 16))

toggle_packages(enc_x264_ENABLED, "xpra.codecs.enc_x264")
if enc_x264_ENABLED:
    make_constants("xpra", "codecs", "enc_x264", "constants")
    if x264_static_ENABLED:
        x264_pkgconfig = STATIC_COMMON_DEFS.copy()
        x264_pkgconfig['extra_link_args'] = ["-Wl,-soname,enc_x264.so", "-Wl,-Bstatic", "-Wl,-Bsymbolic",
                                 "-lx264", "-Wl,-Bdynamic"]
    else:
        x264_pkgconfig = pkgconfig("x264")
    cython_add(Extension("xpra.codecs.enc_x264.encoder",
                ["xpra/codecs/enc_x264/encoder.pyx", "xpra/codecs/enc_x264/enc_x264.c"],
                **x264_pkgconfig), min_version=(0, 16))

toggle_packages(dec_avcodec_ENABLED, "xpra.codecs.dec_avcodec")
if dec_avcodec_ENABLED:
    make_constants("xpra", "codecs", "dec_avcodec", "constants")
    if avcodec_static_ENABLED:
        avcodec_pkgconfig = STATIC_COMMON_DEFS.copy()
        avcodec_pkgconfig['extra_link_args'] = ["-Wl,-soname,dec_avcodec.so", "-Wl,-Bstatic", "-Wl,-Bsymbolic",
                                    "-lavcodec", "-lavutil", "-Wl,-Bdynamic"]
    else:
        avcodec_pkgconfig = pkgconfig("libavcodec")
    cython_add(Extension("xpra.codecs.dec_avcodec.decoder",
                ["xpra/codecs/dec_avcodec/decoder.pyx", "xpra/codecs/memalign/memalign.c", "xpra/codecs/inline.c"],
                **avcodec_pkgconfig), min_version=(0, 19))

toggle_packages(dec_avcodec2_ENABLED, "xpra.codecs.dec_avcodec2")
if dec_avcodec2_ENABLED:
    make_constants("xpra", "codecs", "dec_avcodec2", "constants")
    if avcodec2_static_ENABLED:
        avcodec2_pkgconfig = STATIC_COMMON_DEFS.copy()
        avcodec2_pkgconfig['extra_link_args'] = ["-Wl,-soname,dec_avcodec2.so", "-Wl,-Bstatic", "-Wl,-Bsymbolic",
                                    "-lavcodec", "-lavutil", "-Wl,-Bdynamic"]
    else:
        avcodec2_pkgconfig = pkgconfig("libavcodec")
    cython_add(Extension("xpra.codecs.dec_avcodec2.decoder",
                ["xpra/codecs/dec_avcodec2/decoder.pyx", "xpra/codecs/memalign/memalign.c", "xpra/codecs/inline.c"],
                **avcodec2_pkgconfig), min_version=(0, 19))

toggle_packages(csc_swscale_ENABLED, "xpra.codecs.csc_swscale")
if csc_swscale_ENABLED:
    make_constants("xpra", "codecs", "csc_swscale", "constants")
    if swscale_static_ENABLED:
        swscale_pkgconfig = STATIC_COMMON_DEFS.copy()
        swscale_pkgconfig['extra_link_args'] = ["-Wl,-soname,csc_swscale.so", "-Wl,-Bstatic", "-Wl,-Bsymbolic",
                                 "-lswscale", "-Wl,-Bdynamic"]
    else:
        swscale_pkgconfig = pkgconfig("libswscale")
    cython_add(Extension("xpra.codecs.csc_swscale.colorspace_converter",
                ["xpra/codecs/csc_swscale/colorspace_converter.pyx", "xpra/codecs/memalign/memalign.c", "xpra/codecs/inline.c"],
                **swscale_pkgconfig), min_version=(0, 19))

toggle_packages(csc_cython_ENABLED, "xpra.codecs.csc_cython")
if csc_cython_ENABLED:
    cython_add(Extension("xpra.codecs.csc_cython.colorspace_converter",
                ["xpra/codecs/csc_cython/colorspace_converter.pyx", "xpra/codecs/memalign/memalign.c"],
                ), min_version=(0, 15))

toggle_packages(vpx_ENABLED, "xpra.codecs.vpx")
if vpx_ENABLED:
    if vpx_static_ENABLED:
        vpx_pkgconfig = STATIC_COMMON_DEFS.copy()
        vpx_pkgconfig['extra_link_args'] = ["-Wl,-soname,vpx.so", "-Wl,-Bstatic", "-Wl,-Bsymbolic",
                                "-lvpx", "-Wl,-Bdynamic"]
    else:
        vpx_pkgconfig = pkgconfig(["libvpx", "vpx"])
    cython_add(Extension("xpra.codecs.vpx.encoder",
                ["xpra/codecs/vpx/encoder.pyx", "xpra/codecs/vpx/vpxlib.c", "xpra/codecs/memalign/memalign.c"],
                **vpx_pkgconfig), min_version=(0, 16))
    cython_add(Extension("xpra.codecs.vpx.decoder",
                ["xpra/codecs/vpx/decoder.pyx", "xpra/codecs/memalign/memalign.c"],
                **vpx_pkgconfig), min_version=(0, 16))


toggle_packages(rencode_ENABLED, "xpra.net.rencode")
if rencode_ENABLED:
    rencode_pkgconfig = pkgconfig()
    if not debug_ENABLED:
        if WIN32:
            add_to_keywords(rencode_pkgconfig, 'extra_compile_args', "/Ox")
        else:
            add_to_keywords(rencode_pkgconfig, 'extra_compile_args', "-O3")
    cython_add(Extension("xpra.net.rencode._rencode",
                ["xpra/net/rencode/rencode.pyx"],
                **rencode_pkgconfig))


toggle_packages(bencode_ENABLED, "xpra.net.bencode")
if cython_bencode_ENABLED:
    bencode_pkgconfig = pkgconfig()
    if not debug_ENABLED:
        if WIN32:
            add_to_keywords(bencode_pkgconfig, 'extra_compile_args', "/Ox")
        else:
            add_to_keywords(bencode_pkgconfig, 'extra_compile_args', "-O3")
    cython_add(Extension("xpra.net.bencode.cython_bencode",
                ["xpra/net/bencode/cython_bencode.pyx"],
                **bencode_pkgconfig))


if ext_modules:
    setup_options["ext_modules"] = ext_modules
if cmdclass:
    setup_options["cmdclass"] = cmdclass

setup(**setup_options)
