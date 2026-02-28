"""Clean HTML boilerplate and UI chrome from article content.

Web-sourced articles frequently contain navigation elements, feedback buttons,
share links, and other UI text that dilutes embedding quality. This module
strips common boilerplate patterns before embedding generation.

Experiment 3 found 27% of dotnet-expert sections contaminated with such text.
"""

import re

# Patterns to remove (case-insensitive)
BOILERPLATE_PATTERNS = [
    # Navigation/UI chrome
    r"(?i)\b(feedback|share this|share on|tweet|facebook|x\.com|linkedin|reddit)\b",
    r"(?i)summarize this article for me",
    r"(?i)in this article",
    r"(?i)skip to main content",
    r"(?i)table of contents",
    r"(?i)on this page",
    r"(?i)was this page helpful\??",
    r"(?i)yes\s*no\s*(feedback)?",
    r"(?i)edit this page( on github)?",
    r"(?i)suggest (an )?edit",
    r"(?i)report (an )?issue",
    r"(?i)previous\s*(page|article|chapter)?\s*next\s*(page|article|chapter)?",
    # Cookie/privacy notices
    r"(?i)we use cookies",
    r"(?i)cookie (policy|notice|consent|settings)",
    r"(?i)accept (all )?cookies",
    r"(?i)privacy (policy|notice)",
    # Subscription/newsletter
    r"(?i)subscribe to (our )?newsletter",
    r"(?i)sign up for updates",
    # Breadcrumbs (e.g., "Home > Docs > Section > Page")
    r"(?:[\w\s]+\s*>\s*){3,}[\w\s]+",
]

# Compiled patterns for performance
_COMPILED_PATTERNS = [re.compile(p) for p in BOILERPLATE_PATTERNS]

# Lines that are pure boilerplate (entire line matches)
BOILERPLATE_LINES = {
    "feedback",
    "share",
    "yes",
    "no",
    "edit",
    "next",
    "previous",
    "copy",
    "copied!",
    "print",
    "download",
    "bookmark",
}


def clean_content(text: str) -> str:
    """Remove HTML boilerplate and UI chrome from article text.

    Args:
        text: Raw article section text, potentially containing navigation
              elements, share buttons, feedback forms, and other UI cruft.

    Returns:
        Cleaned text with boilerplate removed. Preserves meaningful content
        and paragraph structure.
    """
    if not text:
        return text

    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        # Skip empty lines (preserve paragraph breaks later)
        if not stripped:
            cleaned_lines.append("")
            continue

        # Skip single-word boilerplate lines
        if stripped.lower() in BOILERPLATE_LINES:
            continue

        # Skip very short lines that are likely UI elements
        if len(stripped) < 4 and not stripped[0].isdigit():
            continue

        # Apply pattern-based cleaning
        cleaned = stripped
        for pattern in _COMPILED_PATTERNS:
            cleaned = pattern.sub("", cleaned).strip()

        # Skip if nothing meaningful remains after cleaning
        if len(cleaned) < 5:
            continue

        cleaned_lines.append(cleaned)

    # Join and collapse multiple blank lines
    result = "\n".join(cleaned_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()
