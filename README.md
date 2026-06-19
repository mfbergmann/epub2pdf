# epub2pdf

Convert an EPUB into a PDF with **accurate print-edition page numbers** — so
you can cite ebook passages by the same page numbers as the physical book.

## The problem

EPUB is reflowable: when you convert one to PDF (including via Calibre), the
page numbers depend on the chosen font and margins and match no published
edition. That makes page-level citation impossible — a "page 42" in your PDF
isn't page 42 in the print book.

## How this solves it

Many EPUBs ship with the print edition's page list baked in as metadata (EPUB 3
`doc-pagebreak` markers or the older NCX `pageList`). epub2pdf reads those
markers and forces each print-page boundary into the PDF as a labelled break, so
a passage on print page *N* lands on a sheet labelled *N*. The result is a PDF
you can import into a reference manager (Paperpile, Zotero, EndNote) and cite
with real, verifiable page numbers.

### Requirement: the EPUB must contain a print page list

Not every EPUB has one. Before converting, check:

```bash
unzip -p book.epub '*nav*' | grep -i 'page-list'      # EPUB 3
unzip -p book.epub '*.ncx' | grep -i 'pageList'       # older NCX fallback
```

If neither command prints a match, the EPUB has no print pagination data and
epub2pdf will refuse to run (you can override with `--force`, but the output
won't have meaningful page numbers).

## Desktop app (no terminal required)

Download the latest build for your platform from the
[Releases](https://github.com/mfbergmann/epub2pdf/releases) page:

- **macOS:** `epub2pdf-mac.zip` — unzip, move to Applications, double-click
- **Windows:** `epub2pdf-windows.zip` — extract and run `epub2pdf.exe`
- **Linux:** `epub2pdf-linux.tar.gz` — extract and run `epub2pdf`

Pick an EPUB, click **Convert to PDF**, done. The app will tell you if the EPUB
doesn't have a print page list and offer to convert anyway.

## Command-line installation

### With [uv](https://docs.astral.sh/uv/) (simplest)

```bash
uv run epub2pdf.py book.epub
```

uv handles the Python packages automatically. You still need WeasyPrint's system
libraries:

- **Debian / Ubuntu:** `sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0`
- **macOS:** `brew install pango cairo gdk-pixbuf libffi`

### With pip

```bash
pip install weasyprint beautifulsoup4 lxml
python epub2pdf.py book.epub
```

### With Docker (nothing to install but Docker)

```bash
docker build -t epub2pdf .
docker run --rm -v "$PWD:/work" epub2pdf book.epub
```

## Usage

```bash
python epub2pdf.py book.epub                        # -> book.print-paginated.pdf
python epub2pdf.py book.epub -o output.pdf          # custom output path
python epub2pdf.py book.epub --compact              # inline [N] markers, shorter PDF
python epub2pdf.py book.epub --page-size letter     # letter instead of 6x9
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output` | `<name>.print-paginated.pdf` | Output file path |
| `--page-size` | `6x9` | `6x9`, `letter`, `a4`, or `"W in H in"` |
| `--margin` | `0.7` | Page margin in inches |
| `--font` | Georgia serif | CSS font stack |
| `--font-size` | `10.5` | Font size in pt |
| `--leading` | `1.5` | Line height |
| `--compact` | off | Inline `[N]` markers instead of one sheet per print page |
| `--force` | off | Convert even without a print page list |

## Reading the output

- The **footer "print p. N"** is the citation page number — use this in your
  references.
- The faint number in the bottom-right corner is just the physical sheet count;
  ignore it for citation.
- The PDF is faithful at the **page level** (content maps to the correct page
  number), not the line level — physical layout won't mirror the publisher's
  typesetting.
- Dense print pages may overflow onto a second sheet; the footer still shows the
  correct print page number on both sheets.

## License

MIT
