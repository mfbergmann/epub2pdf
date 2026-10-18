# epub2pdf — print-paginated EPUB→PDF converter
# Build:  docker build -t epub2pdf .
# Run:    docker run --rm -v "$PWD:/work" epub2pdf book.epub
FROM python:3.12-slim

# WeasyPrint's native dependencies (Pango, which pulls in HarfBuzz and fontconfig)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 \
        libffi8 fonts-dejavu fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "weasyprint>=60" beautifulsoup4 lxml

WORKDIR /work
COPY epub2pdf.py /usr/local/bin/epub2pdf.py
ENTRYPOINT ["python", "/usr/local/bin/epub2pdf.py"]
