"""Minimal sandbox entrypoint for document extraction."""

from __future__ import annotations

from pathlib import Path


INPUT_FILE = Path("/input/document")


def detect_type(path: Path) -> str:
    header = path.read_bytes()[:8]

    if header.startswith(b"%PDF-"):
        return "pdf"

    if header.startswith(b"PK\x03\x04"):
        return "docx"

    raise ValueError("Unsupported or invalid document format")


def extract(path: Path) -> str:
    document_type = detect_type(path)

    if document_type == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if document_type == "docx":
        from docx import Document

        document = Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

    raise ValueError("Unsupported document type")


if __name__ == "__main__":
    if not INPUT_FILE.is_file():
        raise SystemExit("Sandbox input document is missing")

    print(extract(INPUT_FILE), end="")
