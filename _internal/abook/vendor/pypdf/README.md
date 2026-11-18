pypdf 6.21.4 (https://github.com/py-pdf/pypdf, BSD-3-Clause - see LICENSE), copied unchanged from the PyPI wheel
(pypdf-6.21.4-py3-none-any.whl, SHA-256 33e4fb41ca352810eb4e9838aa0d82d6888a5f8bf682f43e99cce5faa666255c).
Pure Python, no dependencies for unencrypted files (AES-encrypted PDFs would need `cryptography`; the importer reports those as unsupported).
Used by `abook/importers.py` (`pdf_pages`) to read the text layer of a PDF.
pypdf imports itself by absolute name (`from pypdf._utils import ...`), so `abook.importers` puts `abook/vendor` on `sys.path` before `import pypdf`.
Upgrade: replace the files from the new wheel, update this note and docs/THIRD_PARTY.md.
