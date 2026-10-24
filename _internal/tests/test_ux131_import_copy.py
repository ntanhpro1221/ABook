"""Lời báo PDF dùng chung với pdf.js; không thay luật nhập chữ."""
import json
from pathlib import Path

import pytest

from abook import importers


FIXTURES = Path(__file__).parent / "fixtures" / "import"
MESSAGES = json.loads((FIXTURES / "messages.json").read_text(encoding="utf-8"))


def test_broken_pdf_uses_shared_copy(tmp_path):
    source = tmp_path / "broken.pdf"
    source.write_bytes(b"not a pdf")
    with pytest.raises(importers.ImportFailed) as error:
        importers.pdf_pages(source)
    assert str(error.value) == MESSAGES["broken"]


def test_locked_pdf_uses_shared_copy():
    with pytest.raises(importers.ImportFailed) as error:
        importers.pdf_pages(FIXTURES / "a84_locked.pdf")
    assert str(error.value) == MESSAGES["password"]
