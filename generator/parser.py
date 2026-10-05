import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from .models import SlideData, SlideType, CardItem, PresentationData, TableData, ImageData, calculate_density_tier
from .markdown_utils import INLINE_TOKEN_RE, strip_markdown


AUDIO_COMMENT_RE = re.compile(r"<!--\s*audio:\s*([^\s>]+)\s*-->", re.IGNORECASE)
NOTES_COMMENT_RE = re.compile(r"<!--\s*notes:\s*(.+?)\s*-->", re.IGNORECASE | re.DOTALL)
TYPE_COMMENT_RE = re.compile(r"<!--\s*(?:type|layout):\s*([^\s>]+)\s*-->", re.IGNORECASE)
TITLE_COMMENT_RE = re.compile(r"<!--\s*title:\s*(.+?)\s*-->", re.IGNORECASE)
AUTHOR_RE = re.compile(r"^(?:készítette|szerző|author|by)\s*:\s*(.+)$", re.IGNORECASE)
IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)")
TABLE_SEP_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*(?::?-+:?)?\s*\|?\s*$")
# Trailing colon, optionally followed by closing emphasis markers ('Title:', '_Title:_', '**Title:**')
TRAILING_COLON_RE = re.compile(r"\s*:\s*([*_]*)\s*$")
# Leading emphasis span with the colon inside it ('**Key:** value', '_Key:_ value')
LEADING_EMPHASIS_COLON_RE = re.compile(r"^(?P<m>\*\*|__|\*|_)(?P<title>(?:(?!(?P=m))[^:])+?)\s*:\s*(?P=m)\s*(?P<desc>.*)$")
CODE_FENCE_RE = re.compile(r"(^[ \t]*```.*?^[ \t]*```[^\n]*$)", re.MULTILINE | re.DOTALL)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
# A comment occupying whole line(s), removed together with its line break
FULL_LINE_COMMENT_RE = re.compile(r"^[ \t]*<!--(?:(?!-->)[\s\S])*-->[ \t]*(?:\n|\Z)", re.MULTILINE)


def _strip_trailing_colon(text: str) -> str:
    """Removes a trailing colon from a title, keeping any closing emphasis markers after it."""
    return TRAILING_COLON_RE.sub(r"\1", text.strip()).strip()


def _strip_html_comments(text: str) -> str:
    """Removes HTML comments (incl. multi-line) outside fenced code blocks; comment-only lines are dropped entirely.

    Renderers split card bodies per line, so a multi-line comment must not survive parsing.
    """
    segments = CODE_FENCE_RE.split(text)
    for idx in range(0, len(segments), 2):  # even indices are outside code fences
        segment = FULL_LINE_COMMENT_RE.sub("", segments[idx])
        segments[idx] = HTML_COMMENT_RE.sub("", segment)
    return "".join(segments)


def parse_slides_file(slides_path: Path) -> PresentationData:
    text = slides_path.read_text(encoding="utf-8")
    source_dir = slides_path.parent
    dist_dir = source_dir / "dist"

    raw_slides = split_into_raw_slides(text)
    slides: List[SlideData] = []
    pres_title = "Presentation"
    global_card_counter = 1
    prev_title = ""

    for idx, raw_slide in enumerate(raw_slides, start=1):
        slide, global_card_counter = parse_single_slide(
            idx, raw_slide, source_dir, global_card_counter, prev_title=prev_title
        )
        if slide.slide_type == SlideType.TITLE and slide.title:
            pres_title = strip_markdown(slide.title)
        prev_title = slide.title
        slides.append(slide)

    # Ensure presentation title is well-formed
    if pres_title == "Presentation" and slides and slides[0].title:
        pres_title = strip_markdown(slides[0].title)

    return PresentationData(
        title=pres_title,
        slides=slides,
        source_dir=source_dir,
        dist_dir=dist_dir
    )


def split_into_raw_slides(text: str) -> List[str]:
    """
    Intelligently splits markdown into raw slide blocks.
    - If document contains explicit delimiters ('---' or '# Slide' / '# Title'), it splits ONLY at them.
    - If document contains neither, top-level '# ' (H1) headings delimit slides.
    - Fenced code blocks are tracked so code comments never falsely split slides.
    """
    lines = text.splitlines()

    # 1. Detect delimiter strategy
    has_hr = False
    has_legacy = False
    in_code = False
    for line in lines:
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if s == "---":
            has_hr = True
        elif re.match(r"^#\s+(?:slide|title)\b", s, re.IGNORECASE):
            has_legacy = True

    slides_raw: List[List[str]] = []
    current: List[str] = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Fenced code block tracking
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            current.append(line)
            continue

        if in_code_block:
            current.append(line)
            continue

        is_delimiter = False
        start_new_slide_with_line = False

        if has_hr or has_legacy:
            if stripped == "---":
                is_delimiter = True
                start_new_slide_with_line = False
            elif re.match(r"^#\s+(?:slide|title)\b", stripped, re.IGNORECASE):
                is_delimiter = True
                start_new_slide_with_line = True
        else:
            # Pure Markdown: only H1 headings delimit slides
            if re.match(r"^#\s+", stripped) and not stripped.startswith("##"):
                is_delimiter = True
                start_new_slide_with_line = True

        if is_delimiter:
            # Check if current has real content before splitting to avoid empty slides
            has_real_content = any(
                l.strip() and not re.match(r"^#\s+(?:slide|title)\s*$", l.strip(), re.IGNORECASE)
                for l in current
            )
            if has_real_content:
                slides_raw.append(current)
                current = [line] if start_new_slide_with_line else []
            else:
                current = [line] if start_new_slide_with_line else []
            continue

        if current or stripped:
            current.append(line)

    if any(l.strip() for l in current):
        slides_raw.append(current)

    return ["\n".join(s) for s in slides_raw if "\n".join(s).strip()]


def parse_single_slide(index: int, raw_text: str, source_dir: Path, global_card_counter: int = 1, prev_title: str = "") -> Tuple[SlideData, int]:
    # 1. Extract metadata comments
    audio_match = AUDIO_COMMENT_RE.search(raw_text)
    audio_filename = audio_match.group(1).strip() if audio_match else None
    audio_path = (source_dir / audio_filename) if audio_filename else None

    notes_match = NOTES_COMMENT_RE.search(raw_text)
    notes = notes_match.group(1).strip() if notes_match else None

    type_match = TYPE_COMMENT_RE.search(raw_text)
    forced_type = type_match.group(1).strip().lower() if type_match else None

    title_match = TITLE_COMMENT_RE.search(raw_text)
    explicit_title = title_match.group(1).strip() if title_match else None

    # Clean text from metadata comments
    cleaned_text = AUDIO_COMMENT_RE.sub("", raw_text)
    cleaned_text = NOTES_COMMENT_RE.sub("", cleaned_text)
    cleaned_text = TYPE_COMMENT_RE.sub("", cleaned_text)
    cleaned_text = TITLE_COMMENT_RE.sub("", cleaned_text)
    cleaned_text = _strip_html_comments(cleaned_text)

    lines = [l.rstrip() for l in cleaned_text.splitlines()]

    # 2. Consume leading slide marker lines (e.g. '# Slide' or '# Title')
    start_idx = 0
    while start_idx < len(lines):
        s = lines[start_idx].strip()
        if not s:
            start_idx += 1
            continue
        if re.match(r"^#\s+(?:slide|title)\s*$", s, re.IGNORECASE):
            start_idx += 1
            continue
        m_marker = re.match(r"^#\s+(?:slide|title)\s*:\s*(.+)$", s, re.IGNORECASE)
        if m_marker:
            if not explicit_title:
                explicit_title = m_marker.group(1).strip()
            start_idx += 1
            continue
        break

    remaining_lines = lines[start_idx:]

    # 3. Detect and extract slide title from headings, bold lines, or terms
    header_title = ""
    header_line_idx = -1

    # Check for Markdown heading (# or ##)
    for i, line in enumerate(remaining_lines):
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^#{1,2}\s+(.*)", s)
        if m:
            raw_title = _strip_trailing_colon(m.group(1))
            candidate = strip_markdown(raw_title)
            if candidate and candidate.lower() not in ["title", "slide"]:
                header_title = raw_title
                header_line_idx = i
                break
        else:
            break

    # If no heading, check if first non-blank line is bold text
    if not header_title and remaining_lines:
        for i, line in enumerate(remaining_lines):
            s = line.strip()
            if not s:
                continue
            if (s.startswith("**") and s.endswith("**")) or (s.startswith("__") and s.endswith("__")):
                candidate = _strip_trailing_colon(strip_markdown(s))
                if candidate and len(candidate) < 70:
                    header_title = _strip_trailing_colon(s)
                    header_line_idx = i
                    break
            break

    # If still no heading, check if first non-blank is a standalone title line
    if not header_title and remaining_lines:
        first_non_blank_idx = -1
        for i, line in enumerate(remaining_lines):
            if line.strip():
                first_non_blank_idx = i
                break
        if first_non_blank_idx != -1:
            first_s = remaining_lines[first_non_blank_idx].strip()
            # Do NOT treat as header if it's the start of a definition list (: on next line)
            has_definition_on_next = (
                first_non_blank_idx + 1 < len(remaining_lines)
                and remaining_lines[first_non_blank_idx + 1].strip().startswith(": ")
            )
            if not has_definition_on_next and not first_s.startswith(("#", "- ", "* ", "• ", ">", "```", ": ", "|", "![")) and (index == 1 or len(first_s) < 55):
                candidate = _strip_trailing_colon(strip_markdown(first_s))
                if candidate and not (index > 1 and re.search(r"[.!?]$", candidate) and len(candidate) > 40):
                    header_title = _strip_trailing_colon(first_s)
                    header_line_idx = first_non_blank_idx

    # Content lines with the title line removed
    if header_line_idx != -1:
        content_lines = remaining_lines[:header_line_idx] + remaining_lines[header_line_idx + 1:]
    else:
        content_lines = remaining_lines

    # 4. Parse content structures: code blocks, blockquotes, definition lists, cards, tables, images, lists, paragraphs
    parsed_content = _parse_content_structures(content_lines, source_dir)

    code_snippet = parsed_content["code_snippet"]
    quote = parsed_content["quote"]
    raw_cards = parsed_content["cards"]
    list_items = parsed_content["list_items"]
    paragraphs = parsed_content["paragraphs"]
    table = parsed_content["table"]
    images = parsed_content["images"]
    extracted_author = parsed_content.get("author")

    # 5. Detect slide type
    is_first_slide = (index == 1)
    has_explicit_title_type = (forced_type == "title")

    if has_explicit_title_type or (is_first_slide and not raw_cards and not quote and not code_snippet and not table and not images):
        slide_type = SlideType.TITLE
    elif forced_type:
        try:
            slide_type = SlideType(forced_type)
        except ValueError:
            slide_type = SlideType.STANDARD
    elif table:
        slide_type = SlideType.TABLE
    elif code_snippet:
        slide_type = SlideType.CODE
    elif quote:
        slide_type = SlideType.DEFINITION
    elif images and not raw_cards and not list_items and len(paragraphs) <= 1:
        slide_type = SlideType.IMAGE
    elif len(raw_cards) >= 1 and not images and (len(raw_cards) >= 2 or not list_items):
        slide_type = SlideType.CARDS
    elif len(paragraphs) == 1 and not list_items and not images and len(paragraphs[0]) > 80 and not ("http://" in paragraphs[0] or "https://" in paragraphs[0]):
        slide_type = SlideType.DEFINITION
    else:
        slide_type = SlideType.STANDARD

    # If slide is not CARDS, re-integrate any raw_cards into list_items
    if slide_type != SlideType.CARDS and raw_cards:
        for c in raw_cards:
            if not c.description:
                list_items.append(c.title)
            elif strip_markdown(c.title) == c.title:
                list_items.append(f"**{c.title}**: {c.description}")
            else:
                # Title already carries inline markup; wrapping it again would corrupt it
                list_items.append(f"{c.title}: {c.description}")
        raw_cards = []

    # 6. Title, subtitle, and author resolution
    final_title = explicit_title or header_title
    subtitle = ""
    author = extracted_author or ""

    if slide_type == SlideType.TITLE:
        if not final_title:
            if paragraphs:
                final_title = _strip_trailing_colon(strip_markdown(paragraphs[0]))
                remaining = paragraphs[1:]
            else:
                final_title = "Title Slide"
                remaining = []
        else:
            remaining = paragraphs

        if len(remaining) >= 2:
            subtitle = remaining[0]
            if not author:
                author = remaining[1]
        elif len(remaining) == 1:
            if not author:
                author = remaining[0]

    else:
        if not final_title:
            # Intelligent fallback deduction
            if slide_type == SlideType.DEFINITION:
                p_text = quote or (paragraphs[0] if paragraphs else "")
                if "értelmezésében" in p_text or "matematikai műveltség" in p_text:
                    final_title = "A matematikai műveltség értelmezése"
                elif "definíció" in p_text.lower() or "definition" in p_text.lower():
                    final_title = "Definíció"
                elif paragraphs:
                    cand = paragraphs[0].split(".")[0].strip()
                    final_title = cand if len(cand) <= 50 else "Alapfogalom"
                else:
                    final_title = "Alapfogalom"

            elif slide_type == SlideType.CARDS:
                if any("mennyiség" in c.title.lower() or "változás" in c.title.lower() for c in raw_cards):
                    final_title = "A mérés tartalmi kategóriái"
                elif any("tér" in c.title.lower() or "adat" in c.title.lower() for c in raw_cards):
                    final_title = "A mérés tartalmi kategóriái (folytatás)"
                elif raw_cards and len(raw_cards) <= 3:
                    final_title = ", ".join(c.title for c in raw_cards)
                elif paragraphs:
                    final_title = _strip_trailing_colon(strip_markdown(paragraphs[0]))
                    paragraphs = paragraphs[1:]
                else:
                    final_title = "Főbb témakörök"

            elif slide_type == SlideType.TABLE:
                final_title = "Összehasonlító táblázat"

            elif slide_type == SlideType.IMAGE:
                if images and images[0].alt:
                    final_title = images[0].alt
                else:
                    final_title = "Illusztráció"

            elif slide_type == SlideType.CODE:
                final_title = f"Kódrészlet ({code_snippet.get('language', 'code')})"
            else:
                if paragraphs:
                    cand = paragraphs[0].split(".")[0].strip()
                    if len(cand) <= 50:
                        final_title = cand
                    else:
                        final_title = f"Dia {index}"
                else:
                    final_title = f"Dia {index}"

    # 7. Card numbering: only continue counter if title matches previous slide
    # ponytail: card numbering resets to 1 unless title continues previous slide
    norm_cur = re.sub(r"\s*\((?:folytatás|folyt\.|continuation|cont\.|part\s*\d+|\d+/\d+)\)", "", final_title, flags=re.IGNORECASE).strip().lower()
    norm_prev = re.sub(r"\s*\((?:folytatás|folyt\.|continuation|cont\.|part\s*\d+|\d+/\d+)\)", "", prev_title, flags=re.IGNORECASE).strip().lower()
    is_continuation = bool(prev_title and norm_cur and norm_cur == norm_prev)

    cards = []
    next_counter = global_card_counter if is_continuation else 1
    if slide_type == SlideType.CARDS:
        for c in raw_cards:
            c.card_index = next_counter
            cards.append(c)
            next_counter += 1
    else:
        next_counter = 1

    slide = SlideData(
        index=index,
        slide_type=slide_type,
        title=final_title,
        subtitle=subtitle,
        author=author,
        quote=quote,
        paragraphs=paragraphs,
        cards=cards,
        list_items=list_items,
        code_snippet=code_snippet,
        table=table,
        images=images,
        audio_filename=audio_filename,
        audio_path=audio_path,
        notes=notes,
        raw_markdown=raw_text
    )
    slide.density_tier = calculate_density_tier(slide)
    return slide, next_counter


def _parse_content_structures(lines: List[str], source_dir: Path) -> Dict[str, Any]:
    """
    Parses content lines into:
    - code_snippet: Optional[Dict[str, str]]
    - quote: Optional[str]
    - cards: List[CardItem]
    - list_items: List[str]
    - paragraphs: List[str]
    - table: Optional[TableData]
    - images: List[ImageData]
    - author: Optional[str]
    """
    code_snippet = None
    quote_lines: List[str] = []
    cards: List[CardItem] = []
    list_items: List[str] = []
    paragraphs: List[str] = []
    table: Optional[TableData] = None
    images: List[ImageData] = []
    detected_author: Optional[str] = None

    in_code_block = False
    code_lang = ""
    code_lines: List[str] = []

    current_para: List[str] = []

    def commit_para():
        nonlocal current_para
        if current_para:
            text = " ".join(current_para).strip()
            if text:
                paragraphs.append(text)
            current_para = []

    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 1. Fenced Code Block
        if stripped.startswith("```"):
            commit_para()
            if not in_code_block:
                in_code_block = True
                code_lang = stripped[3:].strip()
                code_lines = []
            else:
                in_code_block = False
                code_snippet = {
                    "language": code_lang or "code",
                    "code": "\n".join(code_lines)
                }
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # 2. Blank line
        if not stripped:
            commit_para()
            i += 1
            continue

        # 3. Blockquote (> text)
        if stripped.startswith(">"):
            commit_para()
            quote_lines.append(stripped.lstrip(">").strip())
            i += 1
            continue

        # 4. Images: ![alt](src)
        img_matches = list(IMAGE_RE.finditer(stripped))
        if img_matches:
            for im in img_matches:
                alt = im.group("alt")
                src = im.group("src").strip()
                resolved = (source_dir / src).resolve() if (source_dir / src).exists() else None
                images.append(ImageData(alt=alt, src=src, resolved_path=resolved))
            # Check if line contains ONLY images
            cleaned_line = IMAGE_RE.sub("", stripped).strip()
            if not cleaned_line:
                commit_para()
                i += 1
                continue
            stripped = cleaned_line

        # 5. Tables: header row contains '|' and next row is separator
        if "|" in stripped and i + 1 < n and TABLE_SEP_RE.match(lines[i + 1].strip()):
            commit_para()
            raw_headers = [c.strip() for c in stripped.strip().strip("|").split("|")]
            sep_parts = [c.strip() for c in lines[i + 1].strip().strip("|").split("|")]
            alignments = []
            for sp in sep_parts:
                s = sp.strip()
                if s.startswith(":") and s.endswith(":"):
                    alignments.append("center")
                elif s.endswith(":"):
                    alignments.append("right")
                else:
                    alignments.append("left")
            i += 2
            rows = []
            while i < n and lines[i].strip() and "|" in lines[i]:
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                while len(row) < len(raw_headers):
                    row.append("")
                rows.append(row[:len(raw_headers)])
                i += 1
            table = TableData(headers=raw_headers, rows=rows, alignments=alignments)
            continue

        # 6. Author line (e.g. Készítette: Jámbor Dorián)
        m_auth = AUTHOR_RE.match(stripped)
        if m_auth:
            commit_para()
            detected_author = stripped
            i += 1
            continue

        # 7. H2/H3 Card or Section Header (### Card Title or ## Section Title)
        if stripped.startswith("### ") or (stripped.startswith("## ") and not stripped.startswith("### ")):
            commit_para()
            # ponytail: keep inline markdown for card titles
            card_title = _strip_trailing_colon(stripped.lstrip("#"))
            i += 1
            # The body may be separated from its heading by blank lines (standard Markdown spacing)
            while i < n and not lines[i].strip():
                i += 1
            body_lines = []
            while i < n and lines[i].strip() and not lines[i].strip().startswith(("### ", "## ", "# ", "---", ">", "```", "|", "![")) and not (strip_markdown(lines[i].strip()).endswith(":") and len(lines[i].strip()) < 40):
                body_lines.append(lines[i].strip())
                i += 1
            cards.append(CardItem(title=card_title, description="\n".join(body_lines)))
            continue

        # 8. Definition List Pattern:
        # A term line followed by lines starting with ': '
        if i + 1 < n and lines[i + 1].strip().startswith(": "):
            commit_para()
            # ponytail: keep inline markdown for card titles
            term = _strip_trailing_colon(stripped)
            i += 1
            def_lines = []
            while i < n and lines[i].strip().startswith(": "):
                def_lines.append(lines[i].strip()[2:].strip())
                i += 1
            cards.append(CardItem(title=term, description="\n".join(def_lines)))
            continue

        # 9. Bullet items (standard bullets, task lists, cards with colon, or indented sub-properties)
        bullet_match = re.match(r"^(?:[-*•]|\d+\.)\s+(.*)", stripped)
        if bullet_match:
            commit_para()
            bullet_first_line = bullet_match.group(1).strip()

            # Task list check: [x] or [ ]
            task_match = re.match(r"^\[([ xX])\]\s+(.*)", bullet_first_line)
            if task_match:
                is_checked = task_match.group(1).lower() == "x"
                task_text = task_match.group(2).strip()
                tag = "[x] " if is_checked else "[ ] "
                list_items.append(f"{tag}{task_text}")
                i += 1
                continue

            i += 1
            sub_lines = []
            # Gather indented lines belonging to this bullet
            while i < n and (lines[i].startswith(("  ", "\t")) or (not lines[i].strip() and i + 1 < n and lines[i + 1].startswith(("  ", "\t")))):
                if lines[i].strip():
                    sub_lines.append(lines[i].strip())
                i += 1

            if sub_lines:
                # Multi-line bullet with sub-properties -> CardItem
                # ponytail: keep inline markdown for card titles
                card_title = _strip_trailing_colon(bullet_first_line)
                card_desc = "\n".join(sub_lines)
                cards.append(CardItem(title=card_title, description=card_desc))
            else:
                # Single-line bullet: check if formatted as Title: Description
                card_item = _try_parse_card_from_bullet(bullet_first_line)
                if card_item:
                    cards.append(card_item)
                else:
                    list_items.append(bullet_first_line)
            continue

        # 10. Single-line Term: Description card (e.g. 'Összehúzódás: vért pumpál az artériákba')
        colon_line_match = re.match(r"^([A-ZÁÉÍÓÖŐÚÜŰa-záéíóöőúüű0-9\s_*–-]{2,35}):\s+(.+)$", stripped)
        if colon_line_match and not stripped.startswith(("- ", "* ", "• ", "http", "https")) and not stripped.lower().startswith(("források:", "forrás:", "megjegyzés:")):
            commit_para()
            # ponytail: keep inline markdown for card titles
            term = colon_line_match.group(1).strip()
            desc = colon_line_match.group(2).strip()
            cards.append(CardItem(title=term, description=desc))
            i += 1
            continue

        # 11. Unbulleted Key-Value block (e.g. 'Artéria, verőér, ütőér:\nFeladata: ...')
        clean_stripped = strip_markdown(stripped)
        if (stripped.endswith(":") or clean_stripped.endswith(":")) and len(clean_stripped) < 60 and not stripped.startswith("#"):
            next_idx = i + 1
            while next_idx < n and not lines[next_idx].strip():
                next_idx += 1
            if next_idx < n:
                next_s = lines[next_idx].strip()
                if not next_s.startswith(("#", "---", "###", "![", "<img", "- ", "* ", "• ", "|")):
                    commit_para()
                    # ponytail: keep inline markdown for card titles
                    term = _strip_trailing_colon(stripped)
                    i = next_idx
                    desc_lines = []
                    while i < n and lines[i].strip() and not lines[i].strip().endswith(":") and not strip_markdown(lines[i].strip()).endswith(":") and not lines[i].strip().startswith(("#", "---", "###", "- ", "* ", "• ", "![", "<img", "|")):
                        desc_lines.append(lines[i].strip())
                        i += 1
                    cards.append(CardItem(title=term, description="\n".join(desc_lines)))
                    continue

        # 12. Links and Sources list entries (e.g. URLs or lines starting with Források:)
        if "http://" in stripped or "https://" in stripped or stripped.lower().startswith(("források:", "forrás:", "sources:", "source:")):
            commit_para()
            list_items.append(stripped)
            i += 1
            continue

        # 13. Standalone short items (Slide 8 style: Szívdobogásérzés, Extraszisztolé, Pitvarremegés)
        if len(stripped) < 40 and not re.search(r"[.!?]$", stripped) and not stripped.startswith(("#", "---")):
            prev_blank = (i == 0 or not lines[i - 1].strip())
            next_blank = (i + 1 == n or not lines[i + 1].strip())
            if prev_blank and next_blank:
                commit_para()
                list_items.append(stripped)
                i += 1
                continue

        # Regular paragraph line
        current_para.append(stripped)
        i += 1

    commit_para()

    quote = " ".join(quote_lines).strip() if quote_lines else None

    return {
        "code_snippet": code_snippet,
        "quote": quote,
        "cards": cards,
        "list_items": list_items,
        "paragraphs": paragraphs,
        "table": table,
        "images": images,
        "author": detected_author
    }


def _find_colon_outside_markup(text: str) -> int:
    """Returns the index of the first colon not inside an inline Markdown token (emphasis, code, link, URL), or -1."""
    pos = 0
    for match in INLINE_TOKEN_RE.finditer(text):
        idx = text.find(":", pos, match.start())
        if idx != -1:
            return idx
        pos = match.end()
    return text.find(":", pos)


def _try_parse_card_from_bullet(text: str) -> Optional[CardItem]:
    """Tries to extract a structured card (Title & Description) from a bullet item."""
    # ponytail: keep inline markdown for card titles
    lead = LEADING_EMPHASIS_COLON_RE.match(text)
    if lead:
        title = f"{lead.group('m')}{lead.group('title').strip()}{lead.group('m')}"
        desc = lead.group("desc").strip()
        if desc and len(title) < 60:
            return CardItem(title=title, description=desc)

    colon_idx = _find_colon_outside_markup(text)
    if colon_idx != -1 and 2 < colon_idx < 60:
        title = text[:colon_idx].strip()
        desc = text[colon_idx + 1:].strip()
        if desc:
            return CardItem(title=title, description=desc)

    dash_match = re.search(r"\s+–\s+|\s+-\s+", text)
    if dash_match and 2 < dash_match.start() < 60:
        title = text[:dash_match.start()].strip()
        desc = text[dash_match.end():].strip()
        if desc:
            return CardItem(title=title, description=desc)

    return None
