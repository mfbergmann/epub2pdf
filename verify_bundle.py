#!/usr/bin/env python3
"""Prove a freshly-built bundle is self-contained, before it gets published.

The failure this exists to catch is silent. PyInstaller's weasyprint hook looks
for Pango/GObject/HarfBuzz/fontconfig with ctypes.util.find_library() at build
time; when it finds nothing it logs a warning and the build *succeeds*. The
result is an app that launches fine and then dies the moment someone converts a
book, because WeasyPrint is imported lazily. A green CI run therefore proves
very little on its own — hence this.

Three checks, in increasing order of how much they prove:
  1. the native libraries are in the bundle at all;
  2. (macOS) nothing in the bundle loads a library from outside it;
  3. the shipped binary actually converts an EPUB, with correct page labels.

Run against a build tree: python verify_bundle.py dist
"""
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# Substrings of the shared libraries WeasyPrint dlopen()s. Matched loosely
# because the filenames differ per platform (libpango-1.0.dylib /
# libpango-1.0.so.0 / libpango-1.0-0.dll).
REQUIRED_LIBS = ['gobject-2.0', 'pango-1.0', 'pangoft2-1.0', 'harfbuzz', 'fontconfig']

# Load paths that are fine to depend on: these ship with the OS itself.
SYSTEM_PREFIXES = ('/usr/lib/', '/System/Library/', '@rpath/', '@loader_path/', '@executable_path/')


def locate(dist: Path):
    """Return (executable, directory holding the bundled libraries)."""
    app = dist / 'epub2pdf.app'
    if app.is_dir():                                     # macOS
        return app / 'Contents' / 'MacOS' / 'epub2pdf', app / 'Contents' / 'Frameworks'
    onedir = dist / 'epub2pdf'
    exe = onedir / ('epub2pdf.exe' if os.name == 'nt' else 'epub2pdf')
    internal = onedir / '_internal'                      # PyInstaller >= 6 layout
    return exe, (internal if internal.is_dir() else onedir)


def check_libs_present(libdir: Path) -> list:
    names = [p.name for p in libdir.rglob('*') if p.is_file()]
    missing = [lib for lib in REQUIRED_LIBS
               if not any(lib in n for n in names)]
    for lib in REQUIRED_LIBS:
        hit = [n for n in names if lib in n]
        print(f"  {'ok  ' if hit else 'MISS'} {lib:<14} {hit[0] if hit else '-- not bundled --'}")
    return missing


def check_no_external_links(libdir: Path) -> list:
    """macOS only: every load command must resolve inside the bundle or to the OS."""
    if sys.platform != 'darwin':
        print('  (skipped — macOS only)')
        return []
    bad = []
    for lib in sorted(libdir.rglob('*.dylib')):
        try:
            out = subprocess.run(['otool', '-L', str(lib)],
                                 capture_output=True, text=True, check=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        for line in out.splitlines()[1:]:
            path = line.strip().split(' (')[0]
            if not path or path.startswith(SYSTEM_PREFIXES):
                continue
            bad.append(f'{lib.name} -> {path}')
    for entry in bad:
        print(f'  EXTERNAL {entry}')
    if not bad:
        print(f'  ok   no external load paths ({len(list(libdir.rglob("*.dylib")))} dylibs checked)')
    return bad


def make_test_epub(path: Path):
    """A minimal EPUB carrying an NCX page list, matching real-world shapes.

    The pageTargets deliberately carry their label in navLabel/text with no
    @value attribute, and one pagebreak marker deliberately mislabels its title
    as "page_iv" — both are shapes that publishers actually ship and that this
    converter has gotten wrong before.
    """
    opf = '''<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="i">
 <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Verification Fixture</dc:title><dc:creator>epub2pdf</dc:creator>
  <dc:identifier id="i">urn:uuid:verify</dc:identifier></metadata>
 <manifest>
  <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  <item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
 </manifest>
 <spine toc="ncx"><itemref idref="c1"/></spine>
</package>'''
    ncx = '''<?xml version="1.0"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
 <head/><docTitle><text>Verification Fixture</text></docTitle>
 <navMap><navPoint id="n1" playOrder="1"><navLabel><text>Chapter</text></navLabel>
  <content src="ch1.xhtml"/></navPoint></navMap>
 <pageList>
  <pageTarget id="p1" type="front"><navLabel><text>iv</text></navLabel>
   <content src="ch1.xhtml#page_iv"/></pageTarget>
  <pageTarget id="p2" type="normal"><navLabel><text>7</text></navLabel>
   <content src="ch1.xhtml#page_7"/></pageTarget>
 </pageList>
</ncx>'''
    ch1 = '''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Chapter</title></head><body>
<span epub:type="pagebreak" id="page_iv" title="page_iv"/>
<p>Front matter body text on roman page four.</p>
<span epub:type="pagebreak" id="page_7" title="7"/>
<p>Body text that belongs on print page seven.</p>
</body></html>'''
    container = '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
 <rootfiles><rootfile full-path="OEBPS/content.opf"
  media-type="application/oebps-package+xml"/></rootfiles></container>'''

    with zipfile.ZipFile(path, 'w') as z:
        # mimetype must be first and stored uncompressed.
        z.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip',
                   compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml', container)
        z.writestr('OEBPS/content.opf', opf)
        z.writestr('OEBPS/toc.ncx', ncx)
        z.writestr('OEBPS/ch1.xhtml', ch1)


def check_converts(exe: Path) -> list:
    """Run the shipped binary on a fixture and confirm the labels are right."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return ['pypdf is required to verify the output PDF (pip install pypdf)']

    with tempfile.TemporaryDirectory() as tmp:
        epub, pdf = Path(tmp) / 'fixture.epub', Path(tmp) / 'fixture.pdf'
        make_test_epub(epub)
        proc = subprocess.run([str(exe), str(epub), '-o', str(pdf)],
                              capture_output=True, text=True, timeout=300)
        if not pdf.is_file():
            return [f'conversion produced no PDF (exit {proc.returncode})\n'
                    f'--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}']

        text = ' '.join((p.extract_text() or '') for p in PdfReader(str(pdf)).pages)
        found = set(re.findall(r'print p\. (\S+)', text))
        print(f'  ok   converted fixture, footers: {sorted(found)}')

        problems = []
        for expected in ('iv', '7'):
            if expected not in found:
                problems.append(f'expected a "print p. {expected}" footer, got {sorted(found)}')
        if not re.search(r'roman page four', text):
            problems.append('page content missing from the PDF')
        return problems


def main():
    dist = Path(sys.argv[1] if len(sys.argv) > 1 else 'dist').resolve()
    exe, libdir = locate(dist)
    print(f'bundle:     {dist}')
    print(f'executable: {exe}')
    print(f'libraries:  {libdir}\n')

    if not exe.is_file():
        sys.exit(f'FAIL: no executable at {exe} — did the build run?')

    failures = []
    print('[1/3] native libraries bundled')
    for lib in check_libs_present(libdir):
        failures.append(f'{lib} was not bundled — the build environment could not '
                        f'find it, so weasyprint will fail at runtime')

    print('\n[2/3] no dependencies outside the bundle')
    for entry in check_no_external_links(libdir):
        failures.append(f'bundled library links outside the bundle: {entry}')

    print('\n[3/3] the shipped binary converts an EPUB')
    failures.extend(check_converts(exe))

    print()
    if failures:
        for f in failures:
            print(f'FAIL: {f}')
        sys.exit(f'\n{len(failures)} check(s) failed — this build is not self-contained.')
    print('PASS: bundle is self-contained.')


if __name__ == '__main__':
    main()
