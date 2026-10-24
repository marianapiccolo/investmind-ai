import re
from dataclasses import dataclass

import tiktoken


CHUNK_TOKEN_LIMIT = 400
CHUNK_OVERLAP_TOKENS = 50

ENCODING_NAME = "cl100k_base"


@dataclass(frozen=True)
class TextChunk:
    section_title: str
    content: str
    token_count: int


def count_tokens(text: str) -> int:
    """
    Count tokens using the tokenizer used for
    InvestMind knowledge-base chunking.
    """
    encoding = tiktoken.get_encoding(ENCODING_NAME)

    return len(encoding.encode(text))


def _split_markdown_sections(
    markdown: str,
) -> list[tuple[str, str]]:
    """
    Split Markdown content by headings.

    Returns tuples containing:
    (section_title, section_content)
    """
    sections: list[tuple[str, str]] = []

    current_title = ""
    current_lines: list[str] = []

    for line in markdown.splitlines():
        heading_match = re.match(
            r"^#{1,6}\s+(.+?)\s*$",
            line,
        )

        if heading_match:
            content = "\n".join(current_lines).strip()

            if content:
                sections.append(
                    (
                        current_title,
                        content,
                    )
                )

            current_title = heading_match.group(1).strip()
            current_lines = []

            continue

        current_lines.append(line)

    content = "\n".join(current_lines).strip()

    if content:
        sections.append(
            (
                current_title,
                content,
            )
        )

    return sections


def _split_text_by_tokens(
    text: str,
    *,
    token_limit: int,
    overlap_tokens: int,
) -> list[str]:
    """
    Split one text into token-based windows
    with optional overlap.
    """
    if token_limit <= 0:
        raise ValueError("token_limit must be greater than zero.")

    if overlap_tokens < 0:
        raise ValueError("overlap_tokens must not be negative.")

    if overlap_tokens >= token_limit:
        raise ValueError("overlap_tokens must be smaller than token_limit.")

    encoding = tiktoken.get_encoding(ENCODING_NAME)

    token_ids = encoding.encode(text)

    if len(token_ids) <= token_limit:
        return [text.strip()]

    chunks: list[str] = []

    step = token_limit - overlap_tokens

    start = 0

    while start < len(token_ids):
        end = min(
            start + token_limit,
            len(token_ids),
        )

        chunk_token_ids = token_ids[start:end]

        chunk_text = encoding.decode(chunk_token_ids).strip()

        if chunk_text:
            chunks.append(chunk_text)

        if end >= len(token_ids):
            break

        start += step

    return chunks


def chunk_markdown(
    markdown: str,
    *,
    token_limit: int = CHUNK_TOKEN_LIMIT,
    overlap_tokens: int = (CHUNK_OVERLAP_TOKENS),
) -> list[TextChunk]:
    """
    Convert Markdown content into structured
    token-limited chunks.

    Markdown headings define semantic sections.
    Large sections are divided using overlapping
    token windows.
    """
    markdown = markdown.strip()

    if not markdown:
        raise ValueError("Markdown content must not be empty.")

    sections = _split_markdown_sections(markdown)

    chunks: list[TextChunk] = []

    for section_title, content in sections:
        text_parts = _split_text_by_tokens(
            content,
            token_limit=token_limit,
            overlap_tokens=overlap_tokens,
        )

        for text_part in text_parts:
            chunks.append(
                TextChunk(
                    section_title=(section_title),
                    content=text_part,
                    token_count=count_tokens(text_part),
                )
            )

    return chunks
