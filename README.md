# epub2pdf

Convert an EPUB into a **print-paginated PDF** using the print edition's page
list embedded in the file (EPUB 3 `doc-pagebreak` markers, or NCX `pageList`).
Each print-page boundary becomes a labelled break, so a passage on print page
*N* lands on the sheet labelled *N* — suitable for page-level citation in a
reference manager.

Only works when the EPUB actually carries a print page list. Check first:

```bash
unzip -p book.epub '*nav*' | grep -i 'page-list'      # EPUB 3
unzip -p book.epub '*.ncx' | grep -i 'pageList'       # older fallback
```

## Run options

**A. Local, with [uv](https://docs.astral.sh/uv/) (simplest if deps are present):**
```bash
uv run epub2pdf.py book.epub
```
uv handles the Python packages. You still need WeasyPrint's system libraries:
- Debian/Ubuntu: `apt-get install libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0`
- macOS: `brew install pango cairo gdk-pixbuf libffi`

**B. Docker (zero-friction, nothing to install but Docker):**
```bash
docker build -t epub2pdf .
docker run --rm -v "$PWD:/work" epub2pdf book.epub
```

**C. Via Claude:** keep this repo on GitHub and tell Claude
"fetch epub2pdf.py from <raw URL> and run it on this EPUB" — Claude can pull
from raw.githubusercontent.com and run it in its sandbox, no local deps.

## Options
```
-o, --output       output path (default: <name>.print-paginated.pdf)
--page-size        6x9 (default) | letter | a4 | "W in H in"
--margin           inches (default 0.7)
--font             CSS font stack (default Georgia serif)
--font-size        pt (default 10.5)
--leading          line-height (default 1.5)
--compact          inline [N] markers, normal-length PDF (vs one sheet per print page)
--force            convert even if no page list is found
```

## Notes
- The footer "print p. N" is the citation locator; the faint bottom-right number
  is just the physical sheet count — ignore it for citation.
- Faithful at the page level (content→page-number), not the line level; physical
  layout does not mirror the publisher's typesetting.
