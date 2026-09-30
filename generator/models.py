from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any


class SlideType(str, Enum):
    TITLE = "title"
    DEFINITION = "definition"
    CARDS = "cards"
    CODE = "code"
    TABLE = "table"
    IMAGE = "image"
    STANDARD = "standard"


class ArchetypeType(str, Enum):
    EDITORIAL = "editorial"
    CARDS = "cards"
    NEUBRUTALISM = "neubrutalism"
    TERMINAL = "terminal"
    MINIMAL = "minimal"
    CORPORATE = "corporate"


class DensityTier(str, Enum):
    SPACIOUS = "spacious"
    BALANCED = "balanced"
    COMPACT = "compact"


@dataclass
class CardItem:
    title: str
    description: str
    tag: Optional[str] = None
    card_index: int = 1


@dataclass
class TableData:
    headers: List[str]
    rows: List[List[str]]
    alignments: List[str] = field(default_factory=list)  # "left", "center", "right"


@dataclass
class ImageData:
    alt: str
    src: str
    resolved_path: Optional[Path] = None


@dataclass
class SlideData:
    index: int
    slide_type: SlideType
    title: str = ""
    subtitle: str = ""
    author: str = ""
    quote: Optional[str] = None
    paragraphs: List[str] = field(default_factory=list)
    cards: List[CardItem] = field(default_factory=list)
    list_items: List[str] = field(default_factory=list)
    code_snippet: Optional[Dict[str, str]] = None
    table: Optional[TableData] = None
    images: List[ImageData] = field(default_factory=list)
    density_tier: DensityTier = DensityTier.BALANCED
    audio_filename: Optional[str] = None
    audio_path: Optional[Path] = None
    notes: Optional[str] = None
    raw_markdown: str = ""


def calculate_density_tier(slide: SlideData) -> DensityTier:
    """Classifies a slide into spacious (light content), balanced (standard), or compact (dense content)."""
    if slide.slide_type == SlideType.TITLE:
        return DensityTier.SPACIOUS

    if slide.slide_type == SlideType.DEFINITION:
        q_len = len(slide.quote or (slide.paragraphs[0] if slide.paragraphs else ""))
        return DensityTier.SPACIOUS if q_len < 180 else DensityTier.BALANCED

    if slide.slide_type == SlideType.CARDS:
        num_cards = len(slide.cards)
        total_card_text = sum(len(c.title) + len(c.description) for c in slide.cards)
        if num_cards <= 2 and total_card_text < 280:
            return DensityTier.SPACIOUS
        elif num_cards <= 4 and total_card_text < 550:
            return DensityTier.BALANCED
        else:
            return DensityTier.COMPACT

    if slide.slide_type == SlideType.IMAGE:
        return DensityTier.SPACIOUS if len(slide.paragraphs) <= 1 else DensityTier.BALANCED

    if slide.slide_type == SlideType.TABLE:
        if slide.table and len(slide.table.rows) <= 3 and len(slide.table.headers) <= 3:
            return DensityTier.BALANCED
        return DensityTier.COMPACT

    if slide.slide_type == SlideType.CODE:
        code_lines = (slide.code_snippet.get("code", "") if slide.code_snippet else "").count("\n") + 1
        return DensityTier.BALANCED if code_lines <= 8 else DensityTier.COMPACT

    # Standard slide: paragraphs + list_items
    num_items = len(slide.list_items)
    total_para_len = sum(len(p) for p in slide.paragraphs)
    total_list_len = sum(len(item) for item in slide.list_items)
    total_text = total_para_len + total_list_len

    if (num_items <= 3 and total_text < 240) or (num_items == 0 and total_text < 180):
        return DensityTier.SPACIOUS
    elif num_items <= 5 and total_text < 520:
        return DensityTier.BALANCED
    else:
        return DensityTier.COMPACT


@dataclass
class PresentationData:
    title: str
    slides: List[SlideData]
    source_dir: Path
    dist_dir: Path


@dataclass
class ThemeConfig:
    id: str
    name: str
    description: str
    colors: Dict[str, str]
    fonts: Dict[str, str]
    styles: Dict[str, Any]
    archetype: ArchetypeType = ArchetypeType.CARDS

    def hex_to_rgb(self, hex_code: str) -> tuple[int, int, int]:
        hex_code = hex_code.lstrip("#")
        if len(hex_code) == 3:
            hex_code = "".join(c * 2 for c in hex_code)
        return int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16)
