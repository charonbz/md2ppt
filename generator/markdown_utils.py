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
    is_arrow: bool = False

    def __iter__(self):
        # Backward compatibility tuple unpacking: chunk, is_bold, is_italic, is_code
        return iter((self.text, self.is_bold, self.is_italic, self.is_code))


# Inline Markdown token regex with full extended syntax
# "->"/"-->" become →, "<-"/"<--" become ←; "<->" / "<-->" are left untouched (neither direction applies).
RIGHT_ARROW_PATTERN = r"(?<![<!-])(?:-->|->)"
LEFT_ARROW_PATTERN = r"(?<![<-])(?:<--|<-)(?![->])"

INLINE_TOKEN_RE = re.compile(
    r"(?P<comment><!--[\s\S]*?-->)|"
    r"(?P<link>\[(?P<link_text>[^\]]+)\]\((?P<link_url>[^)]+)\))|"
    r"(?P<raw_url>https?://[^\s<>'\"`]+)|"
    r"(?P<code_tick>`(?P<code_text>[^`]+)`)|"
    r"(?P<br><br\s*/?>)|"
    r"(?P<strike>~~(?P<strike_text>.+?)~~)|"
    r"(?P<highlight>==(?P<highlight_text>.+?)==)|"
    r"(?P<sup_caret>\^(?P<sup_text>[^^]+)\^)|"
    r"(?P<sub_tilde>(?<!~)~(?P<sub_text>[^~]+)~(?!~))|"
    r"(?P<bold_star>\*\*(?P<bold_star_text>.+?)\*\*)|"
    r"(?P<bold_under>__(?P<bold_under_text>.+?)__)|"
    r"(?P<italic_star>(?<!\*)\*(?P<italic_star_text>[^*]+?)\*(?!\*))|"
    r"(?P<italic_under>(?<!_)_(?P<italic_under_text>[^_]+?)_(?!_))|"
    rf"(?P<arrow>{RIGHT_ARROW_PATTERN}|→)|"
    rf"(?P<left_arrow>{LEFT_ARROW_PATTERN}|←)",
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
    # Convert -> / --> to → and <- / <-- to ←
    cleaned = re.sub(RIGHT_ARROW_PATTERN, "→", cleaned)
    cleaned = re.sub(LEFT_ARROW_PATTERN, "←", cleaned)
    # Strip trailing colons or excess whitespace
    cleaned = cleaned.strip()
    return cleaned


def render_markdown_html(text: str, allow_links: bool = True) -> str:
    """Converts inline Markdown (**bold**, *italic*, `code`, ~~strike~~, ==highlight==, ^sup^, ~sub~, [link](url), raw URLs, <br>, ->/<- arrows) to safe HTML.

    allow_links=False renders link and URL tokens as plain text (used for link text, so anchors never nest).
    """
    if not text:
        return ""

    pos = 0
    parts = []

    def _inner(content: str) -> str:
        return render_markdown_html(content, allow_links)

    for match in INLINE_TOKEN_RE.finditer(text):
        start, end = match.span()
        if start > pos:
            chunk = html.escape(text[pos:start]).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")
            parts.append(chunk)

        if match.group("comment"):
            pass
        elif match.group("br"):
            parts.append("<br/>")
        elif match.group("arrow"):
            parts.append('<span class="md-arrow">→</span>')
        elif match.group("left_arrow"):
            parts.append('<span class="md-arrow">←</span>')
        elif match.group("code_tick"):
            content = html.escape(match.group("code_text"))
            parts.append(f"<code>{content}</code>")
        elif match.group("link"):
            link_text = render_markdown_html(match.group("link_text"), allow_links=False)
            if allow_links:
                link_url = html.escape(match.group("link_url"))
                parts.append(f'<a href="{link_url}" target="_blank" rel="noopener">{link_text}</a>')
            else:
                parts.append(link_text)
        elif match.group("raw_url"):
            url = html.escape(match.group("raw_url"))
            parts.append(f'<a href="{url}" target="_blank" rel="noopener">{url}</a>' if allow_links else url)
        elif match.group("strike"):
            parts.append(f'<del class="md-strike">{_inner(match.group("strike_text"))}</del>')
        elif match.group("highlight"):
            parts.append(f'<mark class="md-highlight">{_inner(match.group("highlight_text"))}</mark>')
        elif match.group("sup_caret"):
            parts.append(f'<sup>{_inner(match.group("sup_text"))}</sup>')
        elif match.group("sub_tilde"):
            parts.append(f'<sub>{_inner(match.group("sub_text"))}</sub>')
        elif match.group("bold_star"):
            parts.append(f"<strong>{_inner(match.group('bold_star_text'))}</strong>")
        elif match.group("bold_under"):
            parts.append(f"<strong>{_inner(match.group('bold_under_text'))}</strong>")
        elif match.group("italic_star"):
            parts.append(f"<em>{_inner(match.group('italic_star_text'))}</em>")
        elif match.group("italic_under"):
            parts.append(f"<em>{_inner(match.group('italic_under_text'))}</em>")

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

        if match.group("comment"):
            pass
        elif match.group("br"):
            runs.append(TextRun(text="", is_break=True))
        elif match.group("arrow"):
            runs.append(TextRun(text="→", is_arrow=True))
        elif match.group("left_arrow"):
            runs.append(TextRun(text="←", is_arrow=True))
        elif match.group("code_tick"):
            _append_text_with_newlines(match.group("code_text"), is_code=True)
        elif match.group("link"):
            link_url = match.group("link_url")
            for r in parse_markdown_runs(match.group("link_text")):
                if not r.is_break:
                    r.is_link = True
                    r.is_italic = True
                    r.link_url = link_url
                runs.append(r)
            runs.append(TextRun(text=f" ({link_url})", is_link=True, is_italic=True, link_url=link_url))
        elif match.group("raw_url"):
            url = match.group("raw_url")
            _append_text_with_newlines(url, is_link=True, is_italic=True, link_url=url)
        elif match.group("strike"):
            for r in parse_markdown_runs(match.group("strike_text")):
                r.is_strike = True
                runs.append(r)
        elif match.group("highlight"):
            for r in parse_markdown_runs(match.group("highlight_text")):
                r.is_highlight = True
                r.is_bold = True
                runs.append(r)
        elif match.group("sup_caret"):
            for r in parse_markdown_runs(match.group("sup_text")):
                r.is_sup = True
                runs.append(r)
        elif match.group("sub_tilde"):
            for r in parse_markdown_runs(match.group("sub_text")):
                r.is_sub = True
                runs.append(r)
        elif match.group("bold_star"):
            for r in parse_markdown_runs(match.group("bold_star_text")):
                r.is_bold = True
                runs.append(r)
        elif match.group("bold_under"):
            for r in parse_markdown_runs(match.group("bold_under_text")):
                r.is_bold = True
                runs.append(r)
        elif match.group("italic_star"):
            for r in parse_markdown_runs(match.group("italic_star_text")):
                r.is_italic = True
                runs.append(r)
        elif match.group("italic_under"):
            for r in parse_markdown_runs(match.group("italic_under_text")):
                r.is_italic = True
                runs.append(r)

        pos = end

    if pos < len(text):
        _append_text_with_newlines(text[pos:])

    return runs
