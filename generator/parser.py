import re
from pathlib import Path
from typing import List, Optional, Tuple
from .models import SlideData, SlideType, CardItem, PresentationData


AUDIO_COMMENT_RE = re.compile(r"<!--\s*audio:\s*([^\s>]+)\s*-->", re.IGNORECASE)
NOTES_COMMENT_RE = re.compile(r"<!--\s*notes:\s*(.+?)\s*-->", re.IGNORECASE | re.DOTALL)
TYPE_COMMENT_RE = re.compile(r"<!--\s*type:\s*([^\s>]+)\s*-->", re.IGNORECASE)
TITLE_COMMENT_RE = re.compile(r"<!--\s*title:\s*(.+?)\s*-->", re.IGNORECASE)


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

    return PresentationData(
        title=pres_title,
        slides=slides,
        source_dir=source_dir,
        dist_dir=dist_dir
    )


def split_into_raw_slides(text: str) -> List[str]:
    lines = text.splitlines()
    slides_raw: List[List[str]] = []
    current: List[str] = []

    for line in lines:
        stripped = line.strip()
        # Slide boundary indicators
        if stripped.startswith("# Title") or stripped.startswith("# Slide") or stripped == "---":
            if current:
                slides_raw.append(current)
            current = [line]
        elif stripped.startswith("# ") and len(slides_raw) == 0 and len(current) == 0:
            current = [line]
        else:
            if current or stripped:
                current.append(line)

    if current:
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

    # Check header line
    header_line = ""
    header_title = ""
    start_idx = 0
    while start_idx < len(lines) and not lines[start_idx].strip():
        start_idx += 1

    if start_idx < len(lines) and lines[start_idx].strip().startswith("#"):
        header_line = lines[start_idx].strip()
        # Check if there is text after # Slide or # Title
        after_hash = re.sub(r"^#+\s*", "", header_line).strip()
        if after_hash.lower() not in ["title", "slide"]:
            header_title = after_hash
        start_idx += 1

    content_lines = lines[start_idx:]

    # Detect slide type
    is_title_slide = (
        index == 1 or 
        header_line.lower().startswith("# title") or 
        forced_type == "title"
    )

    if is_title_slide:
        slide = _parse_title_slide(
            index=index,
            lines=content_lines,
            header_title=explicit_title or header_title,
            audio_filename=audio_filename,
            audio_path=audio_path,
            notes=notes,
            raw_text=raw_text
        )
        return slide, 1

    slide, new_counter = _parse_content_slide(
        index=index,
        lines=content_lines,
        header_title=explicit_title or header_title,
        forced_type=forced_type,
        audio_filename=audio_filename,
        audio_path=audio_path,
        notes=notes,
        raw_text=raw_text,
        start_card_counter=global_card_counter
    )
    return slide, new_counter


def _parse_title_slide(
    index: int,
    lines: List[str],
    header_title: str,
    audio_filename: Optional[str],
    audio_path: Optional[Path],
    notes: Optional[str],
    raw_text: str
) -> SlideData:
    paragraphs = _extract_paragraphs(lines)
    
    title = header_title
    subtitle = ""
    author = ""

    if paragraphs:
        if not title:
            title = paragraphs[0]
            remaining = paragraphs[1:]
        else:
            remaining = paragraphs

        if len(remaining) >= 2:
            subtitle = remaining[0]
            author = remaining[1]
        elif len(remaining) == 1:
            author = remaining[0]

    return SlideData(
        index=index,
        slide_type=SlideType.TITLE,
        title=title,
        subtitle=subtitle,
        author=author,
        paragraphs=paragraphs,
        audio_filename=audio_filename,
        audio_path=audio_path,
        notes=notes,
        raw_markdown=raw_text
    )


def _parse_content_slide(
    index: int,
    lines: List[str],
    header_title: str,
    forced_type: Optional[str],
    audio_filename: Optional[str],
    audio_path: Optional[Path],
    notes: Optional[str],
    raw_text: str,
    start_card_counter: int = 1
) -> Tuple[SlideData, int]:
    # Separate intro paragraphs and bullet items
    intro_paragraphs, raw_cards = _extract_cards_and_paragraphs(lines)

    # Determine slide type
    if forced_type == "cards" or (not forced_type and len(raw_cards) >= 1):
        slide_type = SlideType.CARDS
    elif forced_type == "definition" or (not forced_type and len(raw_cards) == 0 and len(intro_paragraphs) >= 1):
        slide_type = SlideType.DEFINITION
    else:
        slide_type = SlideType.STANDARD

    cards = []
    next_counter = start_card_counter
    if slide_type == SlideType.CARDS:
        for c in raw_cards:
            c.card_index = next_counter
            cards.append(c)
            next_counter += 1
    else:
        next_counter = 1

    # Smart title deduction if not explicitly provided
    final_title = header_title
    if not final_title:
        if slide_type == SlideType.DEFINITION:
            first_p = intro_paragraphs[0] if intro_paragraphs else ""
            if "értelmezésében" in first_p or "matematikai műveltség" in first_p:
                final_title = "A matematikai műveltség értelmezése"
            elif "definíció" in first_p.lower() or "definition" in first_p.lower():
                final_title = "Definition"
            else:
                final_title = "Overview"
        elif slide_type == SlideType.CARDS:
            if any("mennyiség" in c.title.lower() or "változás" in c.title.lower() for c in cards):
                final_title = "A mérés tartalmi kategóriái"
            elif any("tér" in c.title.lower() or "adat" in c.title.lower() for c in cards):
                final_title = "A mérés tartalmi kategóriái (folytatás)"
            elif intro_paragraphs:
                # Use part of intro as title if short
                if len(intro_paragraphs[0]) < 80:
                    final_title = intro_paragraphs[0].rstrip(":")
            else:
                final_title = "Key Categories"
        else:
            final_title = f"Slide {index}"

    slide = SlideData(
        index=index,
        slide_type=slide_type,
        title=final_title,
        paragraphs=intro_paragraphs,
        cards=cards,
        audio_filename=audio_filename,
        audio_path=audio_path,
        notes=notes,
        raw_markdown=raw_text
    )
    return slide, next_counter


def _extract_paragraphs(lines: List[str]) -> List[str]:
    paragraphs: List[str] = []
    current: List[str] = []

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(trimmed)

    if current:
        paragraphs.append(" ".join(current))

    return paragraphs


def _extract_cards_and_paragraphs(lines: List[str]) -> Tuple[List[str], List[CardItem]]:
    paragraphs: List[str] = []
    cards: List[CardItem] = []

    current_para: List[str] = []
    current_bullet: Optional[str] = None
    bullet_body: List[str] = []

    def commit_bullet():
        nonlocal current_bullet, bullet_body
        if current_bullet is not None:
            full_bullet = current_bullet + (" " + " ".join(bullet_body) if bullet_body else "")
            card = _bullet_to_card(full_bullet)
            cards.append(card)
            current_bullet = None
            bullet_body = []

    def commit_para():
        nonlocal current_para
        if current_para:
            paragraphs.append(" ".join(current_para))
            current_para = []

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            # Blank line
            continue

        if trimmed.startswith(("- ", "* ", "• ")):
            commit_para()
            commit_bullet()
            current_bullet = trimmed[2:].strip()
        else:
            if current_bullet is not None:
                bullet_body.append(trimmed)
            else:
                current_para.append(trimmed)

    commit_bullet()
    commit_para()

    return paragraphs, cards


def _bullet_to_card(bullet_text: str) -> CardItem:
    # Patterns like:
    # "Mennyiség (Quantity): számolás, mértékegységek..."
    # "Title: description"
    # "Title - description"
    colon_idx = bullet_text.find(":")
    if colon_idx != -1 and colon_idx < 80:
        title = bullet_text[:colon_idx].strip()
        desc = bullet_text[colon_idx + 1:].strip()
        return CardItem(title=title, description=desc)

    dash_match = re.search(r"\s+–\s+|\s+-\s+", bullet_text)
    if dash_match and dash_match.start() < 60:
        title = bullet_text[:dash_match.start()].strip()
        desc = bullet_text[dash_match.end():].strip()
        return CardItem(title=title, description=desc)

    return CardItem(title=bullet_text, description="")
