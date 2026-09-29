import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from .models import SlideData, SlideType, CardItem, PresentationData
from .markdown_utils import strip_markdown


AUDIO_COMMENT_RE = re.compile(r"<!--\s*audio:\s*([^\s>]+)\s*-->", re.IGNORECASE)
NOTES_COMMENT_RE = re.compile(r"<!--\s*notes:\s*(.+?)\s*-->", re.IGNORECASE | re.DOTALL)
TYPE_COMMENT_RE = re.compile(r"<!--\s*(?:type|layout):\s*([^\s>]+)\s*-->", re.IGNORECASE)
TITLE_COMMENT_RE = re.compile(r"<!--\s*title:\s*(.+?)\s*-->", re.IGNORECASE)
AUTHOR_RE = re.compile(r"^(?:készítette|szerző|author|by)\s*:\s*(.+)$", re.IGNORECASE)


def parse_slides_file(slides_path: Path) -> PresentationData:
    text = slides_path.read_text(encoding="utf-8")
    source_dir = slides_path.parent
    dist_dir = source_dir / "dist"

    raw_slides = split_into_raw_slides(text)
    slides: List[SlideData] = []
    pres_title = "Presentation"
    global_card_counter = 1

    for idx, raw_slide in enumerate(raw_slides, start=1):
        slide, global_card_counter = parse_single_slide(idx, raw_slide, source_dir, global_card_counter)
        if slide.slide_type == SlideType.TITLE and slide.title:
            pres_title = slide.title
        slides.append(slide)

    # Ensure presentation title is well-formed
    if pres_title == "Presentation" and slides and slides[0].title:
        pres_title = slides[0].title

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


def parse_single_slide(index: int, raw_text: str, source_dir: Path, global_card_counter: int = 1) -> Tuple[SlideData, int]:
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
            candidate = strip_markdown(m.group(1)).rstrip(":")
            if candidate and candidate.lower() not in ["title", "slide"]:
                header_title = candidate
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
                candidate = strip_markdown(s).rstrip(":")
                if candidate and len(candidate) < 70:
                    header_title = candidate
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
            if not has_definition_on_next and not first_s.startswith(("- ", "* ", "• ", ">", "```", ": ")) and (index == 1 or len(first_s) < 55):
                candidate = strip_markdown(first_s).rstrip(":")
                if candidate and not (index > 1 and re.search(r"[.!?]$", candidate) and len(candidate) > 40):
                    header_title = candidate
                    header_line_idx = first_non_blank_idx

    # Content lines with the title line removed
    if header_line_idx != -1:
        content_lines = remaining_lines[:header_line_idx] + remaining_lines[header_line_idx + 1:]
    else:
        content_lines = remaining_lines

    # 4. Parse content structures: code blocks, blockquotes, definition lists, cards, lists, paragraphs
    parsed_content = _parse_content_structures(content_lines)

    code_snippet = parsed_content["code_snippet"]
    quote = parsed_content["quote"]
    raw_cards = parsed_content["cards"]
    list_items = parsed_content["list_items"]
    paragraphs = parsed_content["paragraphs"]
    extracted_author = parsed_content.get("author")

    # 5. Detect slide type
    is_first_slide = (index == 1)
    has_explicit_title_type = (forced_type == "title")

    if has_explicit_title_type or (is_first_slide and not raw_cards and not quote and not code_snippet):
        slide_type = SlideType.TITLE
    elif forced_type:
        try:
            slide_type = SlideType(forced_type)
        except ValueError:
            slide_type = SlideType.STANDARD
    elif code_snippet:
        slide_type = SlideType.CODE
    elif quote:
        slide_type = SlideType.DEFINITION
    elif len(raw_cards) >= 1:
        slide_type = SlideType.CARDS
    elif len(paragraphs) == 1 and not list_items and len(paragraphs[0]) > 80 and not ("http://" in paragraphs[0] or "https://" in paragraphs[0]):
        slide_type = SlideType.DEFINITION
    else:
        slide_type = SlideType.STANDARD

    # 6. Continuous card numbering
    cards = []
    next_counter = global_card_counter
    if slide_type == SlideType.CARDS:
        for c in raw_cards:
            c.card_index = next_counter
            cards.append(c)
            next_counter += 1
    else:
        next_counter = 1

    # 7. Title, subtitle, and author resolution
    final_title = explicit_title or header_title
    subtitle = ""
    author = extracted_author or ""

    if slide_type == SlideType.TITLE:
        if not final_title:
            if paragraphs:
                final_title = strip_markdown(paragraphs[0]).rstrip(":")
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
                if any("mennyiség" in c.title.lower() or "változás" in c.title.lower() for c in cards):
                    final_title = "A mérés tartalmi kategóriái"
                elif any("tér" in c.title.lower() or "adat" in c.title.lower() for c in cards):
                    final_title = "A mérés tartalmi kategóriái (folytatás)"
                elif cards and len(cards) <= 3:
                    final_title = ", ".join(c.title for c in cards)
                elif paragraphs:
                    final_title = strip_markdown(paragraphs[0]).rstrip(":")
                    paragraphs = paragraphs[1:]
                else:
                    final_title = "Főbb témakörök"

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
        audio_filename=audio_filename,
        audio_path=audio_path,
        notes=notes,
        raw_markdown=raw_text
    )
    return slide, next_counter


def _parse_content_structures(lines: List[str]) -> Dict[str, Any]:
    """
    Parses content lines into:
    - code_snippet: Optional[Dict[str, str]]
    - quote: Optional[str]
    - cards: List[CardItem]
    - list_items: List[str]
    - paragraphs: List[str]
    - author: Optional[str]
    """
    code_snippet = None
    quote_lines: List[str] = []
    cards: List[CardItem] = []
    list_items: List[str] = []
    paragraphs: List[str] = []
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

        # 4. Author line (e.g. Készítette: Jámbor Dorián)
        m_auth = AUTHOR_RE.match(stripped)
        if m_auth:
            commit_para()
            detected_author = stripped
            i += 1
            continue

        # 5. H2/H3 Card or Section Header (### Card Title or ## Section Title)
        if stripped.startswith("### ") or (stripped.startswith("## ") and not stripped.startswith("### ")):
            commit_para()
            card_title = strip_markdown(stripped.lstrip("#")).rstrip(":")
            i += 1
            body_lines = []
            while i < n and lines[i].strip() and not lines[i].strip().startswith(("### ", "## ", "# ", "---", ">", "```")) and not (strip_markdown(lines[i].strip()).endswith(":") and len(lines[i].strip()) < 40):
                body_lines.append(lines[i].strip())
                i += 1
            cards.append(CardItem(title=card_title, description="<br/>".join(body_lines)))
            continue

        # 6. Definition List Pattern:
        # A term line followed by lines starting with ': '
        if i + 1 < n and lines[i + 1].strip().startswith(": "):
            commit_para()
            term = strip_markdown(stripped).rstrip(":")
            i += 1
            def_lines = []
            while i < n and lines[i].strip().startswith(": "):
                def_lines.append(lines[i].strip()[2:].strip())
                i += 1
            cards.append(CardItem(title=term, description="<br/>".join(def_lines)))
            continue

        # 7. Bullet items (standard bullets, cards with colon, or indented sub-properties)
        bullet_match = re.match(r"^(?:[-*•]|\d+\.)\s+(.*)", stripped)
        if bullet_match:
            commit_para()
            bullet_first_line = bullet_match.group(1).strip()
            i += 1
            sub_lines = []
            # Gather indented lines belonging to this bullet
            while i < n and (lines[i].startswith(("  ", "\t")) or (not lines[i].strip() and i + 1 < n and lines[i + 1].startswith(("  ", "\t")))):
                if lines[i].strip():
                    sub_lines.append(lines[i].strip())
                i += 1

            if sub_lines:
                # Multi-line bullet with sub-properties -> CardItem
                card_title = strip_markdown(bullet_first_line).rstrip(":")
                card_desc = "<br/>".join(sub_lines)
                cards.append(CardItem(title=card_title, description=card_desc))
            else:
                # Single-line bullet: check if formatted as Title: Description
                card_item = _try_parse_card_from_bullet(bullet_first_line)
                if card_item:
                    cards.append(card_item)
                else:
                    list_items.append(bullet_first_line)
            continue

        # 8. Single-line Term: Description card (e.g. 'Összehúzódás: vért pumpál az artériákba')
        colon_line_match = re.match(r"^([A-ZÁÉÍÓÖŐÚÜŰa-záéíóöőúüű0-9\s_–-]{2,35}):\s+(.+)$", stripped)
        if colon_line_match and not stripped.startswith(("- ", "* ", "• ", "http", "https")) and not stripped.lower().startswith(("források:", "forrás:", "megjegyzés:")):
            commit_para()
            term = strip_markdown(colon_line_match.group(1)).strip()
            desc = colon_line_match.group(2).strip()
            cards.append(CardItem(title=term, description=desc))
            i += 1
            continue

        # 9. Unbulleted Key-Value block (e.g. 'Artéria, verőér, ütőér:\nFeladata: ...')
        # If line ends with ':' (or markdown stripped ends with ':') and next line is non-blank descriptive text
        clean_stripped = strip_markdown(stripped)
        if (stripped.endswith(":") or clean_stripped.endswith(":")) and len(clean_stripped) < 60 and not stripped.startswith("#"):
            # Lookahead to see if next line is descriptive content
            next_idx = i + 1
            while next_idx < n and not lines[next_idx].strip():
                next_idx += 1
            if next_idx < n:
                next_s = lines[next_idx].strip()
                if not next_s.startswith(("#", "---", "###")):
                    commit_para()
                    term = clean_stripped.rstrip(":")
                    i = next_idx
                    desc_lines = []
                    while i < n and lines[i].strip() and not lines[i].strip().endswith(":") and not strip_markdown(lines[i].strip()).endswith(":") and not lines[i].strip().startswith(("#", "---", "###", "- ", "* ", "• ")):
                        desc_lines.append(lines[i].strip())
                        i += 1
                    cards.append(CardItem(title=term, description="<br/>".join(desc_lines)))
                    continue

        # 10. Links and Sources list entries (e.g. URLs or lines starting with Források:)
        if "http://" in stripped or "https://" in stripped or stripped.lower().startswith(("források:", "forrás:", "sources:", "source:")):
            commit_para()
            list_items.append(stripped)
            i += 1
            continue

        # 11. Standalone short items (Slide 8 style: Szívdobogásérzés, Extraszisztolé, Pitvarremegés)
        # If separated by blank lines and length < 40 and not a sentence
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
        "author": detected_author
    }


def _try_parse_card_from_bullet(text: str) -> Optional[CardItem]:
    """Tries to extract a structured card (Title & Description) from a bullet item."""
    colon_idx = text.find(":")
    if colon_idx != -1 and 2 < colon_idx < 60:
        title = strip_markdown(text[:colon_idx]).strip()
        desc = text[colon_idx + 1:].strip()
        if desc:
            return CardItem(title=title, description=desc)

    dash_match = re.search(r"\s+–\s+|\s+-\s+", text)
    if dash_match and 2 < dash_match.start() < 60:
        title = strip_markdown(text[:dash_match.start()]).strip()
        desc = text[dash_match.end():].strip()
        if desc:
            return CardItem(title=title, description=desc)

    return None
