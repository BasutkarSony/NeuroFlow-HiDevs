import socket

import pytest
from fastapi import HTTPException

from backend.security.validators import resolve_document_url
from pipelines.ingestion.extractors.url_extractor import _PinnedResolver


def test_resolve_document_url_returns_addresses_for_connection_pinning(monkeypatch):
    calls = []

    def fake_getaddrinfo(host, port, type):
        calls.append((host, port, type))
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("93.184.216.34", port),
            )
        ]

    monkeypatch.setattr(
        "backend.security.validators.socket.getaddrinfo",
        fake_getaddrinfo,
    )

    result = resolve_document_url("https://Example.com/document")

    assert result[0] == "https://Example.com/document"
    assert result[1] == "example.com"
    assert result[2] == 443
    assert result[3] == [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "93.184.216.34")]
    assert calls == [("example.com", 443, socket.SOCK_STREAM)]


def test_resolve_document_url_rejects_mixed_public_and_private_dns_answers(monkeypatch):
    def fake_getaddrinfo(host, port, type):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("93.184.216.34", port),
            ),
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("10.0.0.8", port),
            ),
        ]

    monkeypatch.setattr(
        "backend.security.validators.socket.getaddrinfo",
        fake_getaddrinfo,
    )

    with pytest.raises(HTTPException) as exc_info:
        resolve_document_url("https://example.com/document")
    assert exc_info.value.detail == "Document URL resolves to a non-public address"


@pytest.mark.asyncio
async def test_pinned_resolver_uses_only_prevalidated_addresses(monkeypatch):
    dns_calls = []

    def unexpected_dns_lookup(*args, **kwargs):
        dns_calls.append(args)
        raise AssertionError("Pinned resolver must not perform another DNS lookup")

    monkeypatch.setattr(socket, "getaddrinfo", unexpected_dns_lookup)

    resolver = _PinnedResolver(
        "example.com",
        443,
        [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "93.184.216.34",
            )
        ],
    )

    resolved = await resolver.resolve("example.com", 443, socket.AF_UNSPEC)

    assert [entry["host"] for entry in resolved] == ["93.184.216.34"]
    assert resolved[0]["hostname"] == "example.com"
    assert resolved[0]["port"] == 443
    assert dns_calls == []

    with pytest.raises(OSError, match="unexpected destination"):
        await resolver.resolve("internal.example", 443, socket.AF_UNSPEC)
