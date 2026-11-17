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


def resolve_document_url(url: str) -> tuple[str, str, int, list[tuple[int, int, int, str]]]:
    """Validate a document URL and return the exact public IPs to pin for its connection."""
    url = url.strip()
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=400,
            detail="Document URL must use http or https",
        )

    if not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(
            status_code=400,
            detail="Invalid document URL",
        )

    raw_hostname = parsed.hostname.rstrip(".").lower()
    try:
        hostname = ipaddress.ip_address(raw_hostname).compressed
    except ValueError:
        try:
            hostname = raw_hostname.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid document URL hostname",
            ) from exc

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid document URL port",
        ) from exc

    try:
        records = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise HTTPException(
            status_code=400,
            detail="Unable to resolve document URL hostname",
        ) from exc

    pinned: list[tuple[int, int, int, str]] = []
    seen: set[tuple[int, int, int, str]] = set()
    for family, socktype, proto, _canonname, sockaddr in records:
        try:
            address = ipaddress.ip_address(sockaddr[0])
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Document URL resolved to an invalid address",
            ) from exc

        # Require globally routable unicast addresses. This also rejects
        # loopback, private, link-local, multicast, reserved and unspecified IPs.
        if not address.is_global or address.is_multicast:
            raise HTTPException(
                status_code=400,
                detail="Document URL resolves to a non-public address",
            )

        entry = (family, socktype, proto, str(address))
        if entry not in seen:
            seen.add(entry)
            pinned.append(entry)

    if not pinned:
        raise HTTPException(
            status_code=400,
            detail="Document URL did not resolve to a public address",
        )

    return url, hostname, port, pinned


def validate_document_url(url: str) -> str:
    """Validate a document URL and reject private, local, or non-public targets."""
    validated_url, _hostname, _port, _addresses = resolve_document_url(url)
    return validated_url


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
