from dataclasses import dataclass


@dataclass
class ExtractedPage:
    page_number: int
    content: str
    content_type: str
    metadata: dict