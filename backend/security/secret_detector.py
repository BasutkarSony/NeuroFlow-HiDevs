import logging
import re
from typing import Any


logger = logging.getLogger(__name__)


SECRET_PATTERNS = {
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "generic_api_key": re.compile(
        r"""['"]?(?:api|secret|token|key|password)['"]?\s*[:=]\s*['"][A-Za-z0-9/+]{20,}['"]""",
        re.IGNORECASE,
    ),
    "private_key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    ),
    "jwt": re.compile(
        r"\b[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
    ),
}


def redact_secrets(
    text: str,
    document_id: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Detect and redact secrets before content is stored or embedded.

    Returns:
        (redacted_text, detections)
    """
    redacted_text = text
    detections: list[dict[str, Any]] = []

    for pattern_type, pattern in SECRET_PATTERNS.items():
        if pattern.search(redacted_text):
            redacted_text = pattern.sub("[REDACTED]", redacted_text)

            detection = {
                "event": "secret_redacted",
                "document_id": document_id,
                "pattern_type": pattern_type,
            }

            detections.append(detection)

            logger.warning(
                "Secret redacted",
                extra=detection,
            )

    return redacted_text, detections
