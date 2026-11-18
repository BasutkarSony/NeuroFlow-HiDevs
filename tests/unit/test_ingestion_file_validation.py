import io
import zipfile

import pytest
from fastapi import HTTPException

from backend.security.validators import validate_file_content


DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def make_docx_package() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
    return buffer.getvalue()


def test_valid_docx_package_is_accepted():
    content = make_docx_package()

    assert validate_file_content("notes.docx", content, DOCX_MIME) == "docx"


def test_arbitrary_zip_is_not_accepted_as_docx():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("payload.txt", "not a Word document")

    with pytest.raises(HTTPException) as exc_info:
        validate_file_content("notes.docx", buffer.getvalue(), DOCX_MIME)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "File content is not a valid DOCX document"


def test_invalid_zip_bytes_are_not_accepted_as_docx():
    with pytest.raises(HTTPException) as exc_info:
        validate_file_content("notes.docx", b"PK\\x03\\x04not-a-zip", DOCX_MIME)

    assert exc_info.value.status_code == 400
