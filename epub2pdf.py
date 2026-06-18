#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["weasyprint>=60", "beautifulsoup4", "lxml"]
# ///
"""
epub2pdf — convert an EPUB into a print-paginated PDF using the print
edition's page list embedded in the EPUB (EPUB 3 `doc-pagebreak` markers /
NCX pageList). Each print-page boundary becomes a labelled break, so a quote
on print page N lands on the sheet labelled N. Intended for citation use in
reference managers.

Requires the system libraries WeasyPrint depends on (Pango/Cairo/GDK-Pixbuf):
  - Debian/Ubuntu: apt-get install libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0
  - macOS (Homebrew): brew install pango cairo gdk-pixbuf libffi
  - Or just use the bundled Dockerfile, which has them baked in.

Usage:
  uv run epub2pdf.py book.epub                  # -> book.print-paginated.pdf
  uv run epub2pdf.py book.epub -o out.pdf
  uv run epub2pdf.py book.epub --page-size letter --font-size 11 --margin 0.8
  uv run epub2pdf.py book.epub --compact         # inline markers, normal length
  (without uv: pip install weasyprint beautifulsoup4 lxml; python epub2pdf.py book.epub)
"""
import argparse, os, re, sys, tempfile, zipfile
from lxml import etree
from bs4 import BeautifulSoup

OPF_NS = "http://www.idpf.org/2007/opf"
CN_NS  = "urn:oasis:names:tc:opendocument:xmlns:container"
DC_NS  = "http://purl.org/dc/elements/1.1/"

def find_opf(root):
    t = etree.parse(os.path.join(root, "META-INF", "container.xml"))
    rp = t.find(f".//{{{CN_NS}}}rootfile")
    return rp.get("full-path")

def parse_opf(root, opf_rel):
    t = etree.parse(os.path.join(root, opf_rel))
    manifest = {it.get("id"): (it.get("href"), it.get("media-type"), (it.get("properties") or ""))
                for it in t.findall(f".//{{{OPF_NS}}}item")}
    spine = [r.get("idref") for r in t.findall(f".//{{{OPF_NS}}}itemref")]
    def dc(tag):
        el = t.find(f".//{{{DC_NS}}}{tag}")
        return el.text.strip() if el is not None and el.text else ""
    return manifest, spine, dc("title"), dc("creator")

def build_label_map(root, opf_dir, manifest):
    """Map fragment-id -> printed page label from EPUB3 nav page-list or NCX pageList."""
    labels = {}
    nav_href = next((h for (h, m, p) in manifest.values() if "nav" in p), None)
    if nav_href:
        p = os.path.join(root, opf_dir, nav_href)
        if os.path.exists(p):
            soup = BeautifulSoup(open(p, encoding="utf-8").read(), "xml")
            nav = soup.find("nav", attrs={"epub:type": "page-list"}) or soup.find("nav", attrs={"role": "doc-pagelist"})
            if nav:
                for a in nav.find_all("a"):
                    href = a.get("href", "")
                    if "#" in href:
                        labels[href.split("#", 1)[1]] = a.get_text(strip=True)
    if not labels:  # NCX fallback
        ncx = next((h for (h, m, p) in manifest.values() if m == "application/x-dtbncx+xml"), None)
        if ncx:
            p = os.path.join(root, opf_dir, ncx)
            if os.path.exists(p):
                soup = BeautifulSoup(open(p, encoding="utf-8").read(), "xml")
                for tgt in soup.find_all("pageTarget"):
                    c = tgt.find("content")
                    if c and "#" in (c.get("src") or ""):
                        labels[c["src"].split("#", 1)[1]] = tgt.get("value", "")
    return labels

def label_for(el, labels):
    return (el.get("aria-label")
            or labels.get(el.get("id", ""))
            or (el.get("id", "")[3:] if el.get("id", "").startswith("pg_") else el.get("id", "")) or "?")

def transform(root, opf_dir, manifest, spine, labels):
    chunks, n = [], 0
    href_by_id = {i: v for i, v in manifest.items()}
    for di, idref in enumerate(spine):
        href, mtype, _ = href_by_id.get(idref, (None, None, None))
        if not href or mtype not in ("application/xhtml+xml", "text/html"):
            continue
        path = os.path.join(root, opf_dir, href)
        if not os.path.exists(path):
            continue
        soup = BeautifulSoup(open(path, encoding="utf-8").read(), "xml")
        body = soup.find("body")
        if body is None:
            continue
        docdir = os.path.dirname(href)
        for img in body.find_all("img"):
            s = img.get("src")
            if s and not s.startswith(("http:", "https:", "data:")):
                img["src"] = os.path.normpath(os.path.join(docdir, s))
        for image in body.find_all("image"):
            h = image.get("xlink:href") or image.get("href")
            if h and not h.startswith(("http:", "https:", "data:")):
                nh = os.path.normpath(os.path.join(docdir, h))
                if image.has_attr("xlink:href"): image["xlink:href"] = nh
                else: image["href"] = nh
        first = True
        for el in body.find_all(True):
            et = el.get("epub:type") or ""
            if el.get("role") == "doc-pagebreak" or "pagebreak" in et:
                lbl = label_for(el, labels)
                el.attrs = {}; el.name = "span"
                el["class"] = "pp first" if first else "pp"
                el["data-page"] = lbl
                el.string = ""
                first = False; n += 1
        inner = "".join(str(c) for c in body.children)
        chunks.append(f'<div class="docwrap{" firstdoc" if di == 0 else ""}">{inner}</div>')
    return chunks, n

def css(args):
    size = {"6x9": "6in 9in", "letter": "letter", "a4": "A4"}.get(args.page_size, args.page_size)
    m = f"{args.margin}in"
    base = f"""
@page {{ size: {size}; margin: {m} {m} {float(args.margin)+0.1}in {m};
  @bottom-center {{ content: "print p. " string(pp); font-family: sans-serif; font-size: 8pt; color: #555; }}
  @bottom-right  {{ content: counter(page); font-family: sans-serif; font-size: 8pt; color: #aaa; }} }}
body {{ font-family: {args.font}; font-size: {args.font_size}pt; line-height: {args.leading}; hyphens: auto; }}
.docwrap {{ break-before: page; }} .firstdoc {{ break-before: auto; }}
img {{ max-width: 100%; height: auto; }} h1,h2,h3 {{ break-after: avoid; }}
.pp {{ string-set: pp attr(data-page); }}
"""
    if args.compact:
        base += """.pp::before { content: "[" attr(data-page) "]"; font-family: sans-serif;
  font-size: 7pt; color: #b00; vertical-align: super; margin: 0 0.15em; }"""
    else:
        base += """.pp { break-before: page; display: block; } .pp.first { break-before: auto; }
.pp::before { content: attr(data-page); display: block; text-align: right; font-family: sans-serif;
  font-weight: bold; font-size: 8pt; color: #999; border-bottom: 1px solid #e2e2e2;
  padding-bottom: 2px; margin-bottom: 0.7em; }"""
    return base

def main():
    ap = argparse.ArgumentParser(description="EPUB -> print-paginated PDF using the embedded print page list.")
    ap.add_argument("epub")
    ap.add_argument("-o", "--output")
    ap.add_argument("--page-size", default="6x9", help="6x9 | letter | a4 | 'W in H in' (default 6x9)")
    ap.add_argument("--margin", type=float, default=0.7, help="inches (default 0.7)")
    ap.add_argument("--font", default="Georgia, 'Times New Roman', serif")
    ap.add_argument("--font-size", type=float, default=10.5)
    ap.add_argument("--leading", type=float, default=1.5)
    ap.add_argument("--compact", action="store_true", help="inline page markers, normal-length PDF")
    ap.add_argument("--force", action="store_true", help="render even if no page list is found")
    args = ap.parse_args()

    out = args.output or re.sub(r"\.epub$", "", args.epub, flags=re.I) + ".print-paginated.pdf"
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(args.epub) as z:
            z.extractall(tmp)
        opf_rel = find_opf(tmp)
        opf_dir = os.path.dirname(opf_rel)
        manifest, spine, title, author = parse_opf(tmp, opf_rel)
        labels = build_label_map(tmp, opf_dir, manifest)
        chunks, n = transform(tmp, opf_dir, manifest, spine, labels)
        if n == 0 and not args.force:
            sys.exit("No page-break markers found — this EPUB has no print page list. "
                     "Re-run with --force to convert without print pagination.")
        css_files = "".join(
            f'<link rel="stylesheet" href="{h}"/>'
            for (h, m, p) in manifest.values() if m == "text/css")
        html = (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>'
                f'<title>{title or os.path.basename(args.epub)}</title>'
                f'<meta name="author" content="{author}"/>{css_files}'
                f'<style>{css(args)}</style></head><body>{"".join(chunks)}</body></html>')
        from weasyprint import HTML
        base = os.path.join(tmp, opf_dir) + os.sep
        HTML(string=html, base_url=base).write_pdf(out)
        print(f"OK  {n} print pages | title: {title or '(none)'} | author: {author or '(none)'}")
        print(f"--> {out}")

if __name__ == "__main__":
    main()
