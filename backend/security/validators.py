import ipaddress
import socket
from urllib.parse import urlparse

import bleach
from fastapi import HTTPException


def sanitize_text(text: str) -> str:
    """Remove HTML tags from user-provided text."""
    return bleach.clean(text, tags=[], strip=True)


def validate_query(query: str) -> str:
    """Sanitize and validate a query."""
    query = sanitize_text(query).strip()

    if len(query) > 5000:
        raise HTTPException(
            status_code=400,
            detail="Query exceeds maximum length of 5000 characters",
        )

    return query


def validate_pipeline_name(name: str) -> str:
    """Sanitize and validate a pipeline name."""
    name = sanitize_text(name).strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Pipeline name cannot be empty",
        )

    if len(name) > 100:
        raise HTTPException(
            status_code=400,
            detail="Pipeline name exceeds maximum length of 100 characters",
        )

    return name


def _is_private_or_local(hostname: str) -> bool:
    """Return True for localhost or private/reserved IP addresses."""
    hostname = hostname.strip().lower().rstrip(".")

    if hostname in {"localhost", "localhost.localdomain"}:
        return True

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return False

    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
    )


def validate_document_url(url: str) -> str:
    """Validate a document URL and reject obvious SSRF targets."""
    url = url.strip()

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=400,
            detail="Document URL must use http or https",
        )

    if not parsed.hostname:
        raise HTTPException(
            status_code=400,
            detail="Invalid document URL",
        )

    hostname = parsed.hostname

    if _is_private_or_local(hostname):
        raise HTTPException(
            status_code=400,
            detail="Document URL targets a private or local address",
        )

    # Resolve hostnames so that domains resolving to private IPs are blocked.
    try:
        addresses = socket.getaddrinfo(
            hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise HTTPException(
            status_code=400,
            detail="Unable to resolve document URL hostname",
        ) from exc

    for address in addresses:
        resolved_ip = address[4][0]

        if _is_private_or_local(resolved_ip):
            raise HTTPException(
                status_code=400,
                detail="Document URL resolves to a private or local address",
            )

    return url


# File signatures ("magic bytes") for supported document types.
FILE_SIGNATURES = {
    "pdf": [
        b"%PDF-",
    ],
    "png": [
        b"\x89PNG\r\n\x1a\n",
    ],
    "jpeg": [
        b"\xff\xd8\xff",
    ],
    "gif": [
        b"GIF87a",
        b"GIF89a",
    ],
    "zip": [
        b"PK\x03\x04",
        b"PK\x05\x06",
        b"PK\x07\x08",
    ],
}


def validate_file_content(
    filename: str,
    content: bytes,
    mime_type: str | None,
) -> str:
    """
    Validate both declared MIME type and file magic bytes.

    Returns the detected logical file type.
    """
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    allowed_mimes = {
        "pdf": {"application/pdf"},
        "docx": {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        },
        "png": {"image/png"},
        "jpeg": {"image/jpeg"},
        "jpg": {"image/jpeg"},
        "gif": {"image/gif"},
        "csv": {
            "text/csv",
            "application/csv",
            "text/plain",
        },
    }

    if extension not in allowed_mimes:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type",
        )

    if mime_type not in allowed_mimes[extension]:
        raise HTTPException(
            status_code=400,
            detail="File MIME type does not match extension",
        )

    if extension == "csv":
        # CSV has no universal magic-byte signature.
        # MIME validation plus UTF-8 decoding is used.
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid CSV content",
            ) from exc

        return "csv"

    signatures = FILE_SIGNATURES.get(extension, [])

    if not any(content.startswith(signature) for signature in signatures):
        raise HTTPException(
            status_code=400,
            detail="File magic bytes do not match declared type",
        )

    return "jpeg" if extension == "jpg" else extension
