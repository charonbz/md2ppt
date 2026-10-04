import html
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any


@dataclass
class TextRun:
    text: str
    is_bold: bool = False
    is_italic: bool = False
    is_code: bool = False
    is_strike: bool = False
    is_highlight: bool = False
    is_sub: bool = False
    is_sup: bool = False
    is_link: bool = False
    link_url: Optional[str] = None
    is_break: bool = False

    def __iter__(self):
        # Backward compatibility tuple unpacking: chunk, is_bold, is_italic, is_code
        return iter((self.text, self.is_bold, self.is_italic, self.is_code))


# Inline Markdown token regex with full extended syntax
INLINE_TOKEN_RE = re.compile(
    r"(?P<link>\[(?P<link_text>[^\]]+)\]\((?P<link_url>[^)]+)\))|"
    r"(?P<raw_url>https?://[^\s<>'\"`]+)|"
    r"(?P<br><br\s*/?>)|"
    r"(?P<strike>~~(?P<strike_text>.+?)~~)|"
    r"(?P<highlight>==(?P<highlight_text>.+?)==)|"
    r"(?P<sup_caret>\^(?P<sup_text>[^^]+)\^)|"
    r"(?P<sub_tilde>(?<!~)~(?P<sub_text>[^~]+)~(?!~))|"
    r"(?P<bold_star>\*\*(?P<bold_star_text>.+?)\*\*)|"
    r"(?P<bold_under>__(?P<bold_under_text>.+?)__)|"
    r"(?P<code_tick>`(?P<code_text>[^`]+)`)|"
    r"(?P<italic_star>(?<!\*)\*(?P<italic_star_text>[^*]+?)\*(?!\*))|"
    r"(?P<italic_under>(?<!_)_(?P<italic_under_text>[^_]+?)_(?!_))",
    re.IGNORECASE,
)


def strip_markdown(text: str) -> str:
    """Strips all Markdown markup to return clean plain text (ideal for slide titles)."""
    if not text:
        return ""
    # Strip links [text](url) -> text
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Strip <br> or <br/> tags to spaces
    cleaned = re.sub(r"(?i)<br\s*/?>", " ", cleaned)
    # Strip strikethrough ~~text~~
    cleaned = re.sub(r"~~(.*?)~~", r"\1", cleaned)
    # Strip highlight ==text==
    cleaned = re.sub(r"==(.*?)==", r"\1", cleaned)
    # Strip sub / sup
    cleaned = re.sub(r"\^([^^]+)\^", r"\1", cleaned)
    cleaned = re.sub(r"~([^~]+)~", r"\1", cleaned)
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
    """Converts inline Markdown (**bold**, *italic*, `code`, ~~strike~~, ==highlight==, ^sup^, ~sub~, [link](url), raw URLs, <br>) to safe HTML."""
    if not text:
        return ""

    pos = 0
    parts = []

    for match in INLINE_TOKEN_RE.finditer(text):
        start, end = match.span()
        if start > pos:
            chunk = html.escape(text[pos:start]).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")
            parts.append(chunk)

        if match.group("br"):
            parts.append("<br/>")
        elif match.group("link"):
            link_text = html.escape(match.group("link_text"))
            link_url = html.escape(match.group("link_url"))
            parts.append(f'<a href="{link_url}" target="_blank" rel="noopener">{link_text}</a>')
        elif match.group("raw_url"):
            url = html.escape(match.group("raw_url"))
            parts.append(f'<a href="{url}" target="_blank" rel="noopener">{url}</a>')
        elif match.group("strike"):
            content = html.escape(match.group("strike_text"))
            parts.append(f'<del class="md-strike">{content}</del>')
        elif match.group("highlight"):
            content = html.escape(match.group("highlight_text"))
            parts.append(f'<mark class="md-highlight">{content}</mark>')
        elif match.group("sup_caret"):
            content = html.escape(match.group("sup_text"))
            parts.append(f'<sup>{content}</sup>')
        elif match.group("sub_tilde"):
            content = html.escape(match.group("sub_text"))
            parts.append(f'<sub>{content}</sub>')
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
        chunk = html.escape(text[pos:]).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")
        parts.append(chunk)

    return "".join(parts)


def parse_markdown_runs(text: str) -> List[TextRun]:
    """
    Parses inline Markdown into a sequence of TextRun objects.
    Used by pptx_renderer to construct formatted PowerPoint text runs.
    """
    if not text:
        return []

    pos = 0
    runs: List[TextRun] = []

    def _append_text_with_newlines(raw: str, **kwargs):
        normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")
        for idx, line in enumerate(lines):
            if idx > 0:
                runs.append(TextRun(text="", is_break=True))
            if line:
                runs.append(TextRun(text=line, **kwargs))

    for match in INLINE_TOKEN_RE.finditer(text):
        start, end = match.span()
        if start > pos:
            _append_text_with_newlines(text[pos:start])

        if match.group("br"):
            runs.append(TextRun(text="", is_break=True))
        elif match.group("link"):
            link_text = match.group("link_text")
            link_url = match.group("link_url")
            _append_text_with_newlines(f"{link_text} ({link_url})", is_link=True, is_italic=True, link_url=link_url)
        elif match.group("raw_url"):
            url = match.group("raw_url")
            _append_text_with_newlines(url, is_link=True, is_italic=True, link_url=url)
        elif match.group("strike"):
            _append_text_with_newlines(match.group("strike_text"), is_strike=True)
        elif match.group("highlight"):
            _append_text_with_newlines(match.group("highlight_text"), is_highlight=True, is_bold=True)
        elif match.group("sup_caret"):
            _append_text_with_newlines(match.group("sup_text"), is_sup=True)
        elif match.group("sub_tilde"):
            _append_text_with_newlines(match.group("sub_text"), is_sub=True)
        elif match.group("bold_star"):
            _append_text_with_newlines(match.group("bold_star_text"), is_bold=True)
        elif match.group("bold_under"):
            _append_text_with_newlines(match.group("bold_under_text"), is_bold=True)
        elif match.group("code_tick"):
            _append_text_with_newlines(match.group("code_text"), is_code=True)
        elif match.group("italic_star"):
            _append_text_with_newlines(match.group("italic_star_text"), is_italic=True)
        elif match.group("italic_under"):
            _append_text_with_newlines(match.group("italic_under_text"), is_italic=True)

        pos = end

    if pos < len(text):
        _append_text_with_newlines(text[pos:])

    return runs
