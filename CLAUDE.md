# epub2pdf

Converts an EPUB into a **print-paginated PDF** whose page numbers match the print
edition, for page-level citation in reference managers (Paperpile, Zotero, EndNote).
Works only when the EPUB embeds the print edition's page list (EPUB 3 `doc-pagebreak`
markers or NCX `pageList`); otherwise it refuses unless `--force` is given.

## Usage
    pip install weasyprint beautifulsoup4 lxml        # or: uv run epub2pdf.py ...
    python epub2pdf.py "book.epub" -o "book.print-paginated.pdf"
WeasyPrint needs system libs Pango/HarfBuzz/fontconfig (Debian: libpango-1.0-0
libpangoft2-1.0-0 libharfbuzz0b libfontconfig1; macOS: brew install pango). On macOS the
script adds Homebrew/MacPorts lib dirs to the dyld search itself, since uv's and
python.org's Pythons don't look there. Or use the bundled Dockerfile.

## Precondition check (always run first)
    unzip -p "book.epub" '*nav*' | grep -i 'page-list'    # EPUB 3
    unzip -p "book.epub" '*.ncx'  | grep -i 'pageList'    # NCX fallback
If neither matches, there is no print page list — do not fabricate pagination.

## Options
- default: one PDF page per print page, labelled top-right
- `--compact`: normal-length PDF with inline [N] markers
- `--page-size` (6x9 | letter | a4), `--margin`, `--font`, `--font-size`, `--leading`, `--force`

## Verify before delivering
Output pages > 0; extract text and confirm a "print p. N" footer sits on the expected content.

## Caveats to relay to the user
- The footer "print p. N" is the citation locator; the faint bottom-right number is the
  physical sheet count — ignore it for citation.
- Faithful at the page level, not the line level; physical layout isn't the publisher's.
- Physical page count may exceed the print count (dense pages overflow); the footer stays correct.
- Reference managers extract article metadata, not book metadata — verify title/author/year/publisher.

## Repo layout & sync rule
- `epub2pdf.py` — the converter (source of truth)
- `epub2pdf_gui.py` — desktop GUI; also the frozen app's entry point, and dispatches
  to the CLI when given arguments
- `epub2pdf.spec` / `rthook_weasyprint.py` — PyInstaller build; these exist to make the
  released app self-contained
- `verify_bundle.py` — run against `dist/` after a build; asserts the app is self-contained
- `skill/epub-print-pagination/` — packaged Claude skill; bundles its own copy of the script
- `Dockerfile`, `README.md`
When you edit `epub2pdf.py`, also copy it to `skill/epub-print-pagination/scripts/epub2pdf.py`
so the installed skill stays in sync.

## Packaging trap (read before touching the build)
WeasyPrint `dlopen`s Pango/GObject/HarfBuzz/fontconfig by name; PyInstaller cannot see
them statically. Its weasyprint hook bundles them only if `ctypes.util.find_library()`
finds them **at build time**, and when it doesn't it just logs a warning — the build
still succeeds and ships an app that dies on the first conversion. WeasyPrint is also
imported lazily inside `convert()`, so the app launches fine and only fails on Convert.
A green build proves nothing here; `verify_bundle.py` is the real gate, and CI runs it
before uploading anything. Never make it non-blocking.
