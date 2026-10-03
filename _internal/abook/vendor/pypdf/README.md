pypdf 6.16.2 (https://github.com/py-pdf/pypdf, BSD-3-Clause - see LICENSE), copied unchanged from the PyPI wheel
(pypdf-6.16.2-py3-none-any.whl, SHA-256 c8b09a59399062fb45a1b8156c18a787a10a3dae03ac9674397a226712c94604).
Pure Python, no dependencies for unencrypted files (AES-encrypted PDFs would need `cryptography`; the importer reports those as unsupported).
Used by `abook/importers.py` (`pdf_pages`) to read the text layer of a PDF.
pypdf imports itself by absolute name (`from pypdf._utils import ...`), so `abook.importers` puts `abook/vendor` on `sys.path` before `import pypdf`.
Upgrade: replace the files from the new wheel, update this note and docs/THIRD_PARTY.md.
