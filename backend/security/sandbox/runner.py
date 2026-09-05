"""Run untrusted document extractors inside a restricted Docker container."""

from __future__ import annotations

import subprocess
from pathlib import Path


SANDBOX_IMAGE = "neuroflow-document-sandbox"
MEMORY_LIMIT = "256m"


def run_extractor(
    input_file: str | Path,
    extractor_command: list[str],
    *,
    timeout_seconds: int = 60,
) -> subprocess.CompletedProcess[str]:
    """
    Execute an ingestion extractor in an isolated Docker container.

    Security boundaries:
    - no network access
    - 256 MiB memory limit
    - read-only input mount
    - temporary writable output workspace
    - no host filesystem access beyond the explicit mounts
    """
    input_path = Path(input_file).resolve()

    if not input_path.is_file():
        raise FileNotFoundError(f"Input document does not exist: {input_path}")

    command = [
        "docker",
        "run",
        "--rm",
        "--network=none",
        "--memory=256m",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--tmpfs=/tmp:rw,noexec,nosuid,size=64m",
        "--mount",
        f"type=bind,src={input_path},dst=/input/document,readonly",
        SANDBOX_IMAGE,
        *extractor_command,
    ]

    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
