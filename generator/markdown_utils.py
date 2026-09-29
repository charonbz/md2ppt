import html
import re
from typing import List, Tuple, Dict, Any


# Inline Markdown token regex with raw URL auto-linking support
INLINE_TOKEN_RE = re.compile(
    r"(?P<link>\[(?P<link_text>[^\]]+)\]\((?P<link_url>[^)]+)\))|"
    r"(?P<raw_url>https?://[^\s<>'\"`]+)|"
    r"(?P<bold_star>\*\*(?P<bold_star_text>.+?)\*\*)|"
    r"(?P<bold_under>__(?P<bold_under_text>.+?)__)|"
    r"(?P<code_tick>`(?P<code_text>[^`]+)`)|"
    r"(?P<italic_star>(?<!\*)\*(?P<italic_star_text>[^*]+?)\*(?!\*))|"
    r"(?P<italic_under>(?<!_)_(?P<italic_under_text>[^_]+?)_(?!_))"
)


def strip_markdown(text: str) -> str:
    """Strips all Markdown markup to return clean plain text (ideal for slide titles)."""
    if not text:
        return ""
    # Strip links [text](url) -> text
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Strip bold / italic markers
    cleaned = re.sub(r"[*_]{1,3}(.*?)[*_]{1,3}", r"\1", cleaned)
    # Strip backticks
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    # Strip leading heading hashes
    cleaned = re.sub(r"^#{1,6}\s*", "", cleaned)
    # Strip trailing colons or excess whitespace
    cleaned = cleaned.strip()
    return cleaned


def render_markdown_html(text: str) -> str:
    """Converts inline Markdown (**bold**, *italic*, `code`, [link](url), raw URLs) to safe HTML."""
    if not text:
        return ""

    pos = 0
    parts = []

    for match in INLINE_TOKEN_RE.finditer(text):
        start, end = match.span()
        if start > pos:
            # Escape plain text before the match, preserving linebreaks
            chunk = html.escape(text[pos:start])
            chunk = chunk.replace("\n", "<br/>")
            parts.append(chunk)

        if match.group("link"):
            link_text = html.escape(match.group("link_text"))
            link_url = html.escape(match.group("link_url"))
            parts.append(f'<a href="{link_url}" target="_blank" rel="noopener">{link_text}</a>')
        elif match.group("raw_url"):
            url = html.escape(match.group("raw_url"))
            parts.append(f'<a href="{url}" target="_blank" rel="noopener">{url}</a>')
        elif match.group("bold_star"):
            content = html.escape(match.group("bold_star_text"))
            parts.append(f"<strong>{content}</strong>")
        elif match.group("bold_under"):
            content = html.escape(match.group("bold_under_text"))
            parts.append(f"<strong>{content}</strong>")
        elif match.group("code_tick"):
            content = html.escape(match.group("code_text"))
            parts.append(f"<code>{content}</code>")
        elif match.group("italic_star"):
            content = html.escape(match.group("italic_star_text"))
            parts.append(f"<em>{content}</em>")
        elif match.group("italic_under"):
            content = html.escape(match.group("italic_under_text"))
            parts.append(f"<em>{content}</em>")

        pos = end

    if pos < len(text):
        chunk = html.escape(text[pos:])
        chunk = chunk.replace("\n", "<br/>")
        parts.append(chunk)

    return "".join(parts)


def parse_markdown_runs(text: str) -> List[Tuple[str, bool, bool, bool]]:
    """
    Parses inline Markdown into runs of (text, is_bold, is_italic, is_code).
    Used by pptx_renderer to construct formatted PowerPoint text runs.
    """
    if not text:
        return []

    pos = 0
    runs: List[Tuple[str, bool, bool, bool]] = []

    for match in INLINE_TOKEN_RE.finditer(text):
        start, end = match.span()
        if start > pos:
            runs.append((text[pos:start], False, False, False))

        if match.group("link"):
            runs.append((f"{match.group('link_text')} ({match.group('link_url')})", False, True, False))
        elif match.group("raw_url"):
            runs.append((match.group("raw_url"), False, True, False))
        elif match.group("bold_star"):
            runs.append((match.group("bold_star_text"), True, False, False))
        elif match.group("bold_under"):
            runs.append((match.group("bold_under_text"), True, False, False))
        elif match.group("code_tick"):
            runs.append((match.group("code_text"), False, False, True))
        elif match.group("italic_star"):
            runs.append((match.group("italic_star_text"), False, True, False))
        elif match.group("italic_under"):
            runs.append((match.group("italic_under_text"), False, True, False))

        pos = end

    if pos < len(text):
        runs.append((text[pos:], False, False, False))

    return runs
