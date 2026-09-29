from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any


class SlideType(str, Enum):
    TITLE = "title"
    DEFINITION = "definition"
    CARDS = "cards"
    STANDARD = "standard"


class ArchetypeType(str, Enum):
    EDITORIAL = "editorial"
    CARDS = "cards"
    NEUBRUTALISM = "neubrutalism"
    TERMINAL = "terminal"
    MINIMAL = "minimal"
    CORPORATE = "corporate"


@dataclass
class CardItem:
    title: str
    description: str
    tag: Optional[str] = None
    card_index: int = 1


@dataclass
class SlideData:
    index: int
    slide_type: SlideType
    title: str = ""
    subtitle: str = ""
    author: str = ""
    paragraphs: List[str] = field(default_factory=list)
    cards: List[CardItem] = field(default_factory=list)
    audio_filename: Optional[str] = None
    audio_path: Optional[Path] = None
    notes: Optional[str] = None
    raw_markdown: str = ""


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
