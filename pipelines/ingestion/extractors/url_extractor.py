import json
from urllib.parse import urljoin, urlparse
from urllib import robotparser

import httpx
import trafilatura

from . import ExtractedPage


async def extract_url(url: str) -> list[ExtractedPage]:
    parsed = urlparse(url)

    robots_url = urljoin(
        f"{parsed.scheme}://{parsed.netloc}",
        "/robots.txt",
    )

    robots = robotparser.RobotFileParser()
    robots.set_url(robots_url)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            robots_response = await client.get(robots_url)

            if robots_response.status_code < 400:
                robots.parse(
                    robots_response.text.splitlines()
                )
            else:
                robots = None

            if robots is not None and not robots.can_fetch(
                "NeuroFlow",
                url,
            ):
                raise PermissionError(
                    f"robots.txt disallows fetching {url}"
                )

            response = await client.get(url)
            response.raise_for_status()

    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Failed to fetch URL: {url}"
        ) from exc

    html = response.text

    content = trafilatura.extract(
        html,
        include_tables=True,
        include_comments=False,
        include_links=True,
    )

    if not content:
        content = ""

    metadata = {}

    metadata_json = trafilatura.extract_metadata(html)

    if metadata_json:
        metadata = {
            "title": getattr(
                metadata_json,
                "title",
                None,
            ),
            "author": getattr(
                metadata_json,
                "author",
                None,
            ),
            "canonical_url": getattr(
                metadata_json,
                "url",
                None,
            ) or str(response.url),
            "publish_date": getattr(
                metadata_json,
                "date",
                None,
            ),
        }
    else:
        metadata = {
            "canonical_url": str(response.url),
        }

    return [
        ExtractedPage(
            page_number=1,
            content=content,
            content_type="text",
            metadata=metadata,
        )
    ]