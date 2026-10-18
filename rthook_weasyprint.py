"""PyInstaller runtime hook: make the bundled Pango/fontconfig stack findable.

Two jobs, both about WeasyPrint resolving things by name at runtime rather than
being linked against them.

1. Locating the bundled shared libraries (macOS). PyInstaller tries to do this
   itself in pyimod03_ctypes, but its copy runs during early bootstrap, where
   `from ctypes.macholib import dyld` raises ImportError — macholib is not in
   base_library.zip — and the failure is swallowed silently. By the time
   WeasyPrint calls ctypes.util.find_library() the stdlib is fully available but
   the search path was never extended, so every lookup misses the bundle and
   falls through to the system, which on a clean Mac has nothing. Runtime hooks
   run after bootstrap completes, so redoing it here actually sticks.

   Linux and Windows arrive at the same place by other routes: the Linux
   bootloader exports LD_LIBRARY_PATH pointing at the bundle, and on Windows
   PyInstaller patches find_library to search sys._MEIPASS.

2. Telling fontconfig where its *configuration* lives.

That matters because fontconfig compiles in an absolute config path at build
time (e.g. /opt/homebrew/etc/fonts on a Homebrew build). On the machine that
built the app that path exists; on the machine that downloads it, it does not,
so fontconfig starts up with no font directories and WeasyPrint renders every
PDF in a fallback face instead of the requested serif.

FONTCONFIG_PATH is read by the library when it initialises, which happens the
first time WeasyPrint lays out text — comfortably after this hook runs. (Note
this only works because it is fontconfig doing the reading. The same trick does
not work for DYLD_* variables, which dyld latches at process start.)
"""
import os
import sys

if hasattr(sys, '_MEIPASS'):
    if sys.platform == 'darwin':
        try:
            from ctypes.macholib import dyld
        except ImportError:
            pass
        else:
            if sys._MEIPASS not in dyld.DEFAULT_LIBRARY_FALLBACK:
                dyld.DEFAULT_LIBRARY_FALLBACK.insert(0, sys._MEIPASS)

    _fonts_dir = os.path.join(sys._MEIPASS, 'etc', 'fonts')
    if os.path.isdir(_fonts_dir):
        # setdefault so anyone debugging a font problem can still override.
        os.environ.setdefault('FONTCONFIG_PATH', _fonts_dir)
        _conf = os.path.join(_fonts_dir, 'fonts.conf')
        if os.path.isfile(_conf):
            os.environ.setdefault('FONTCONFIG_FILE', _conf)
