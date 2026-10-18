# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the epub2pdf desktop app.

The job of this file is to make the released app self-contained: someone
downloads it, double-clicks, and it works, with nothing else installed.

The hard part is WeasyPrint. It does not link against Pango / GObject /
HarfBuzz / fontconfig — it dlopen()s them by name at runtime, so PyInstaller's
static analysis cannot see them. pyinstaller-hooks-contrib ships a weasyprint
hook that collects them, but it locates them with ctypes.util.find_library()
*at build time*, which finds nothing unless those libraries sit on the building
interpreter's loader search path. When that happens the hook logs a warning and
the build still succeeds — shipping an app that dies on the first conversion
with "cannot load library 'libgobject-2.0-0'".

Two things therefore have to hold, and neither is checked by PyInstaller:
  1. The build environment puts the native libs on the search path
     (see the `Build desktop app` workflow for the per-platform env).
  2. The libs actually landed in the bundle — asserted by verify_bundle.py,
     which the workflow runs before anything is uploaded.
"""
import os

datas = [('epub2pdf.py', '.')]

# fontconfig reads its configuration from disk at startup. Without it the
# bundled fontconfig finds no font directories and every PDF renders in a
# fallback face. The stock weasyprint hook only collects /etc/fonts, which does
# not exist on macOS, so pick up Homebrew's copy there — its <dir> entries point
# at the macOS system font directories, which are present on every Mac.
if not os.path.isdir('/etc/fonts'):
    for candidate in ('/opt/homebrew/etc/fonts', '/usr/local/etc/fonts'):
        if os.path.isdir(candidate):
            datas.append((candidate, 'etc/fonts'))
            break

a = Analysis(
    ['epub2pdf_gui.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['epub2pdf'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rthook_weasyprint.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='epub2pdf',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX mangles signed dylibs on macOS and buys little here; the download is
    # dominated by Python and the Pango stack either way.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='epub2pdf',
)
app = BUNDLE(
    coll,
    name='epub2pdf.app',
    icon=None,
    bundle_identifier='ai.bergmann.epub2pdf',
    info_plist={
        'NSHighResolutionCapable': True,
        'CFBundleDocumentTypes': [{
            'CFBundleTypeName': 'EPUB book',
            'CFBundleTypeRole': 'Viewer',
            'LSItemContentTypes': ['org.idpf.epub-container'],
        }],
    },
)
