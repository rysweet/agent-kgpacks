"""Shared utilities for WikiGR knowledge pack build scripts."""

import logging
from itertools import islice
from pathlib import Path

logger = logging.getLogger(__name__)


def load_urls(urls_file: Path, limit: int | None = None) -> list[str]:
    """Load URLs from urls.txt file.

    Args:
        urls_file: Path to urls.txt
        limit: Optional limit on number of URLs (for testing). A value of 0
            is falsy and treated as no limit — pass None or omit to load all.

    Returns:
        List of URLs
    """
    with open(urls_file) as f:
        candidates = (
            stripped
            for line in f
            if (stripped := line.strip())
            and not stripped.startswith("#")
            and stripped.startswith("http")
        )
        urls = list(islice(candidates, limit or None))

    if limit:
        logger.info(f"Limited to {limit} URLs for testing")

    logger.info(f"Loaded {len(urls)} URLs from {urls_file}")
    return urls
