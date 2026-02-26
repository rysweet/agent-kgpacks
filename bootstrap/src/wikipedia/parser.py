"""
Wikipedia wikitext section parser.

Extracts structured sections from Wikipedia wikitext, handling H2 and H3 headings,
stripping formatting, and filtering by content length.
"""

import re


def parse_sections(wikitext: str) -> list[dict[str, str | int]]:
    """
    Extract H2 and H3 sections from wikitext or markdown.

    Parses Wikipedia wikitext (== H2 ==) or markdown (## H2) to identify section
    headings, extracts content between headings, strips formatting, and filters out
    sections with less than 100 characters of content.

    Args:
        wikitext: Wikipedia wikitext or markdown content

    Returns:
        List of sections with structure:
        [
            {
                'level': int,      # 2 for H2, 3 for H3
                'title': str,      # Section title (cleaned)
                'content': str     # Section content (cleaned, >100 chars)
            },
            ...
        ]

    Example:
        >>> wikitext = '''
        ... == Introduction ==
        ... Machine learning is a field of [[artificial intelligence]].
        ...
        ... === History ===
        ... The term was coined in 1959.
        ... '''
        >>> sections = parse_sections(wikitext)
        >>> len(sections) >= 1
        True
        >>> sections[0]['level']
        2
        >>> sections[0]['title']
        'Introduction'
    """
    sections = []

    # Try markdown format first (## Title), then wikitext format (== Title ==)
    # Markdown: ^#{2,6}\s+(.+)$
    # Wikitext: ^(={2,3})\s*(.+?)\s*\1$
    markdown_pattern = r"^(#{2,6})\s+(.+)$"
    wikitext_pattern = r"^(={2,3})\s*(.+?)\s*\1$"

    # Try markdown first (more common for web content)
    matches = list(re.finditer(markdown_pattern, wikitext, re.MULTILINE))
    is_markdown = len(matches) > 0

    if not is_markdown:
        # Fall back to wikitext format
        matches = list(re.finditer(wikitext_pattern, wikitext, re.MULTILINE))

    for i, match in enumerate(matches):
        if is_markdown:
            level = len(match.group(1))  # Count # symbols
            title = match.group(2).strip()
        else:
            level = len(match.group(1))  # Count = symbols
            title = match.group(2).strip()

        start = match.end()  # Content starts after heading
        end = matches[i + 1].start() if i + 1 < len(matches) else len(wikitext)
        content = wikitext[start:end].strip()
        cleaned_content = strip_wikitext(content)

        sections.append({"level": level, "title": title, "content": cleaned_content})

    # Filter sections with content >= 100 characters
    filtered_sections = [section for section in sections if len(section["content"]) >= 100]

    return filtered_sections


def strip_wikitext(text: str) -> str:
    """
    Remove wikitext formatting to get clean text.

    Strips common Wikipedia markup patterns:
    - Templates: {{template|param=value}}
    - Links: [[Article|Display]] -> Display, [[Article]] -> Article
    - References: <ref>...</ref>, <ref name="..." />
    - HTML tags: <div>...</div>, <span>...</span>
    - Files/Images: [[File:...]], [[Image:...]]
    - Comments: <!-- comment -->

    Args:
        text: Raw wikitext string

    Returns:
        Cleaned plain text with formatting removed

    Example:
        >>> wikitext = "This is a [[link|example]] with {{template}} markup."
        >>> strip_wikitext(wikitext)
        'This is a example with  markup.'
    """
    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Remove templates (nested braces supported via recursive pattern)
    # Start with innermost templates and work outward
    while "{{" in text:
        # Match {{...}} non-greedily, avoiding nested braces issues
        old_text = text
        text = re.sub(r"\{\{[^{}]*\}\}", " ", text)
        # Break if no more changes (avoid infinite loop on malformed templates)
        if text == old_text:
            break

    # Remove references with content: <ref>...</ref>
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove self-closing references: <ref name="..." />
    text = re.sub(r"<ref[^/>]*/?>", "", text, flags=re.IGNORECASE)

    # Remove file/image links: [[File:...]] or [[Image:...]]
    text = re.sub(r"\[\[(File|Image):[^\]]+\]\]", "", text, flags=re.IGNORECASE)

    # Convert piped links to display text: [[Article|Display]] -> Display
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)

    # Convert simple links to text: [[Article]] -> Article
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)

    # Remove HTML tags: <tag>...</tag> or <tag />
    text = re.sub(r"<[^>]+>", "", text)

    # Clean up multiple spaces and newlines
    text = re.sub(r"\n\s*\n", "\n", text)  # Multiple newlines -> single
    text = re.sub(r" +", " ", text)  # Multiple spaces -> single

    return text.strip()


# Test code
if __name__ == "__main__":
    # Sample wikitext from a typical Wikipedia article
    sample_wikitext = """
== Introduction ==
[[Machine learning]] (ML) is a field of study in [[artificial intelligence]] concerned with the development and study of [[statistical algorithm]]s that can learn from [[data]] and [[Generalization|generalize]] to unseen data, and thus perform tasks without explicit instructions.{{cite journal|title=Example}}

Recently, [[artificial neural network]]s have been able to surpass many previous approaches in performance.<ref>Deep Learning. Nature, 2015.</ref>

=== History ===
The term "machine learning" was coined in 1959 by [[Arthur Samuel]], an [[IBM]] employee and pioneer in the field of [[computer game]]s and [[artificial intelligence]].<ref name="samuel1959">Samuel, A. L. (1959). "Some Studies in Machine Learning Using the Game of Checkers". ''IBM Journal of Research and Development''.</ref>

The representative book ''The Organization of Behavior'', published in 1949 by [[Donald Hebb]], introduced the theory that neural pathways are strengthened each time they are used.

=== Modern developments ===
In the 1990s, machine learning began to flourish.

== Applications ==
Machine learning has been applied to various domains including:
* [[Computer vision]]
* [[Natural language processing]]
* [[Speech recognition]]

[[File:ML_diagram.png|thumb|Machine Learning Overview]]

Applications include [[email filtering]], detection of [[network intruders]], and [[computer vision]].

=== Healthcare ===
ML is being used for medical diagnosis and [[drug discovery]].

== See also ==
* [[Deep learning]]
* [[Neural networks]]

== Short ==
Too short.
"""

    print("Testing parse_sections()...")
    print("=" * 60)

    sections = parse_sections(sample_wikitext)

    print(f"\nFound {len(sections)} sections (>= 100 chars):\n")

    for i, section in enumerate(sections, 1):
        print(f"{i}. [H{section['level']}] {section['title']}")
        print(f"   Content length: {len(str(section['content']))} chars")
        print(f"   Preview: {str(section['content'])[:100]}...")
        print()

    print("=" * 60)
    print("\nTesting strip_wikitext()...")
    print("=" * 60)

    test_cases = [
        ("[[Machine learning]] is cool", "Machine learning is cool"),
        ("See [[Artificial intelligence|AI]] for details", "See AI for details"),
        ("This has {{template|param=value}} markup", "This has markup"),
        ("Reference here<ref>Citation</ref> text", "Reference here text"),
        ("[[File:image.png|thumb|Caption]] text", "text"),
        ("HTML <div>content</div> here", "HTML content here"),
    ]

    for i, (input_text, expected_pattern) in enumerate(test_cases, 1):
        result = strip_wikitext(input_text)
        print(f"{i}. Input:  {input_text}")
        print(f"   Output: {result}")
        print(
            f"   Status: {'✓' if expected_pattern in result or result.strip() == expected_pattern.strip() else '✗'}"
        )
        print()
