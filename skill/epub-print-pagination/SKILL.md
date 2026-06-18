---
name: epub-print-pagination
description: Convert an EPUB ebook into a print-paginated PDF whose page numbers match the print edition, for page-level citation in reference managers like Paperpile, Zotero, or EndNote. Use this whenever someone wants to cite an ebook by page number, convert an EPUB to a citation-accurate or print-paginated PDF, add an ebook to a reference manager with real page numbers, or asks why their Calibre-converted EPUB has the wrong page numbers. It works by reading the print edition's page list embedded in EPUB 3 files (doc-pagebreak markers) or the older NCX pageList, and forcing each print-page boundary to become a labelled page in the PDF. Trigger even if the user only says "turn this ebook into a PDF I can cite" or "make the page numbers match the print book."
license: MIT
---

# EPUB to print-paginated PDF

## Why this exists

EPUB is reflowable, so an ordinary EPUB-to-PDF conversion (including Calibre's
"add page numbers" option) produces page numbers tied to the chosen font and
margins. Those numbers match no published edition and are useless for citation.

Many EPUBs, though, embed the *print edition's* pagination as page-break
markers. This skill uses those markers so that a passage on print page N lands
on a PDF page labelled N — genuine, citable page numbers that match the print
book. The conversion is faithful at the page level (content to page-number), not
the line level: physical layout does not mirror the publisher's typesetting.

This only works when the EPUB actually carries a print page list, so always
check first and never fabricate pagination.

## Step 1 — Confirm a print page list exists

Run these against the EPUB. If either prints a match, the data is present.

```bash
unzip -p "book.epub" '*nav*' | grep -i 'page-list'   # EPUB 3 nav doc
unzip -p "book.epub" '*.ncx' | grep -i 'pageList'     # older NCX fallback
```

If neither matches, the print pagination is not in the file. Do not bake in
arbitrary numbers. Tell the user plainly and offer the alternatives: read the
book in a page-list-aware reader (Thorium Reader, Calibre's built-in viewer, or
Apple Books) and cite the print page it displays, or proceed with `--force` for
a non-citable reading copy.

## Step 2 — Run the converter

The converter is bundled at `scripts/epub2pdf.py` (resolve the path relative to
this SKILL.md). Ensure dependencies are available first:

```bash
pip install weasyprint beautifulsoup4 lxml --break-system-packages
```

WeasyPrint also needs the system libraries Pango, Cairo, and GDK-Pixbuf, which
are normally already present in Claude's sandbox. If the import fails, install
them with apt (libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0).

Then convert:

```bash
python scripts/epub2pdf.py "input.epub" -o "output.print-paginated.pdf"
```

Modes and options:
- Default: one PDF page per print page, each labelled top-right.
- `--compact`: a normal-length PDF with inline `[N]` markers in the flowing text
  instead of one sheet per page. Offer this if the user finds the default bulky.
- `--page-size` (6x9 default, or letter/a4), `--margin`, `--font`, `--font-size`,
  `--leading` for layout tuning.
- `--force`: convert even when no page list is found (not citation-grade).

The script auto-detects the page list, reads title and author from the EPUB
metadata, and handles both EPUB 3 markers and the NCX fallback.

## Step 3 — Verify before handing it over

Confirm the output has pages and that the mapping is correct: extract the text,
locate a footer such as "print p. 29", and check the content on that page is
what you'd expect for that print page. Rasterizing one page to an image is a
good final visual check.

## Step 4 — Explain the result (always do this)

Tell the user, briefly:
- The footer "print p. N" is the citation locator. The faint number in the
  bottom-right corner is just the physical sheet count — ignore it for citation.
- The physical PDF page count may exceed the print count, because dense print
  pages can overflow onto a second sheet. The footer still shows the correct
  print page on those sheets, so citation stays accurate.
- Reference managers extract metadata for journal articles, not books, so the
  title/author/year/publisher should be verified by hand after import.

## Canonical source

The maintained version of the converter lives in the user's `epub2pdf` GitHub
repository. To run it ad hoc inside a chat without installing the skill, fetch
the raw script and run it (replace USERNAME with the repo owner):

```bash
curl -sL https://raw.githubusercontent.com/USERNAME/epub2pdf/main/epub2pdf.py -o /tmp/epub2pdf.py
python /tmp/epub2pdf.py "input.epub" -o "output.print-paginated.pdf"
```
