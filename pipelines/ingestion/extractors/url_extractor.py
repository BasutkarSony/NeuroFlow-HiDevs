import asyncio
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura

from security.validators import validate_document_url

from . import ExtractedPage


REDIRECT_STATUSES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 5


async def _get_with_safe_redirects(
    client: httpx.AsyncClient,
    url: str,
) -> httpx.Response:
    current_url = url

    for redirect_count in range(MAX_REDIRECTS + 1):
        # Re-resolve and validate every hop; never let httpx follow redirects
        # to an unchecked private or local destination.
        await asyncio.to_thread(validate_document_url, current_url)
        response = await client.get(current_url)

        if response.status_code not in REDIRECT_STATUSES:
            response.raise_for_status()
            return response

        location = response.headers.get("location")
        if not location:
            raise RuntimeError("URL redirect did not include a Location header")
        if redirect_count == MAX_REDIRECTS:
            raise RuntimeError("URL exceeded the maximum redirect count")

        current_url = urljoin(current_url, location)
        await asyncio.to_thread(validate_document_url, current_url)

    raise RuntimeError("URL exceeded the maximum redirect count")


async def extract_url(url: str) -> list[ExtractedPage]:
    parsed = urlparse(url)
    robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")

    robots = robotparser.RobotFileParser()
    robots.set_url(robots_url)

    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=30.0,
        ) as client:
            # Do not follow robots.txt redirects implicitly either.
            await asyncio.to_thread(validate_document_url, robots_url)
            robots_response = await client.get(robots_url)

            if robots_response.status_code < 400 and robots_response.status_code not in REDIRECT_STATUSES:
                robots.parse(robots_response.text.splitlines())
            else:
                robots = None

            if robots is not None and not robots.can_fetch("NeuroFlow", url):
                raise PermissionError(f"robots.txt disallows fetching {url}")

            response = await _get_with_safe_redirects(client, url)

    except httpx.HTTPError as exc:
        raise RuntimeError(f"Failed to fetch URL: {url}") from exc

    html = response.text
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
            "canonical_url": getattr(extracted_metadata, "url", None) or str(response.url),
            "publish_date": getattr(extracted_metadata, "date", None),
        }
    else:
        metadata = {"canonical_url": str(response.url)}

    return [
        ExtractedPage(
            page_number=1,
            content=content,
            content_type="text",
            metadata=metadata,
        )
    ]
