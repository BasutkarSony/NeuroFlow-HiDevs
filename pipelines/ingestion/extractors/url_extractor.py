import asyncio
import socket
from urllib.parse import urljoin, urlparse

import aiohttp
import trafilatura

from security.validators import resolve_document_url

from . import ExtractedPage


REDIRECT_STATUSES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 5


class _PinnedResolver(aiohttp.abc.AbstractResolver):
    """Resolve one hostname only to the public addresses validated for this request."""

    def __init__(
        self,
        hostname: str,
        port: int,
        addresses: list[tuple[int, int, int, str]],
    ) -> None:
        self.hostname = hostname
        self.port = port
        self.addresses = addresses

    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: int = socket.AF_INET,
    ) -> list[dict[str, object]]:
        if host.rstrip(".").lower() != self.hostname or port != self.port:
            raise OSError("Pinned DNS resolver received an unexpected destination")

        records = [
            (address_family, socktype, proto, ip)
            for address_family, socktype, proto, ip in self.addresses
            if family in (socket.AF_UNSPEC, address_family)
        ]
        if not records:
            raise OSError("No validated address is available for this destination")

        return [
            {
                "hostname": self.hostname,
                "host": ip,
                "port": self.port,
                "family": address_family,
                "proto": proto,
                "flags": socket.AI_NUMERICHOST,
            }
            for address_family, _socktype, proto, ip in records
        ]

    async def close(self) -> None:
        return None


async def _get_with_safe_redirects(url: str) -> tuple[str, str]:
    """Fetch a URL while pinning each connection to its validated DNS answers."""
    current_url = url

    for redirect_count in range(MAX_REDIRECTS + 1):
        _validated_url, hostname, port, addresses = await asyncio.to_thread(
            resolve_document_url,
            current_url,
        )
        resolver = _PinnedResolver(hostname, port, addresses)
        connector = aiohttp.TCPConnector(
            resolver=resolver,
            use_dns_cache=False,
        )

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30),
            trust_env=False,
        ) as client:
            async with client.get(current_url, allow_redirects=False) as response:
                if response.status not in REDIRECT_STATUSES:
                    response.raise_for_status()
                    return await response.text(), str(response.url)

                location = response.headers.get("location")
                if not location:
                    raise RuntimeError("URL redirect did not include a Location header")
                if redirect_count == MAX_REDIRECTS:
                    raise RuntimeError("URL exceeded the maximum redirect count")

                current_url = urljoin(current_url, location)

    raise RuntimeError("URL exceeded the maximum redirect count")


async def extract_url(url: str) -> list[ExtractedPage]:
    parsed = urlparse(url)
    robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")

    from urllib import robotparser

    robots = robotparser.RobotFileParser()
    robots.set_url(robots_url)

    try:
        # A 4xx response means no robots policy is available; a 5xx or
        # network failure is treated as unreachable and fails closed.
        try:
            robots_text, _robots_final_url = await _get_with_safe_redirects(robots_url)
        except aiohttp.ClientResponseError as exc:
            if 400 <= exc.status < 500:
                robots = None
            else:
                raise RuntimeError("robots.txt is temporarily unavailable") from exc

        if robots is not None:
            robots.parse(robots_text.splitlines())
            if not robots.can_fetch("NeuroFlow", url):
                raise PermissionError(f"robots.txt disallows fetching {url}")

        html, final_url = await _get_with_safe_redirects(url)

    except aiohttp.ClientError as exc:
        raise RuntimeError(f"Failed to fetch URL: {url}") from exc

    content = trafilatura.extract(
        html,
        include_tables=True,
        include_comments=False,
        include_links=True,
    ) or ""

    extracted_metadata = trafilatura.extract_metadata(html)
    if extracted_metadata:
        metadata = {
            "title": getattr(extracted_metadata, "title", None),
            "author": getattr(extracted_metadata, "author", None),
            "canonical_url": getattr(extracted_metadata, "url", None) or final_url,
            "publish_date": getattr(extracted_metadata, "date", None),
        }
    else:
        metadata = {"canonical_url": final_url}

    return [
        ExtractedPage(
            page_number=1,
            content=content,
            content_type="text",
            metadata=metadata,
        )
    ]
