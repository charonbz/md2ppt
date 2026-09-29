from pathlib import Path
from typing import Optional
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from ..models import PresentationData, SlideData, SlideType, ThemeConfig, ArchetypeType
from ..markdown_utils import parse_markdown_runs


def _get_font_name(theme: ThemeConfig) -> str:
    if theme.archetype == ArchetypeType.EDITORIAL:
        return "Georgia"
    elif theme.archetype == ArchetypeType.TERMINAL:
        return "Consolas"
    elif theme.archetype == ArchetypeType.NEUBRUTALISM:
        return "Arial Black"
    elif theme.archetype == ArchetypeType.MINIMAL:
        return "Arial"
    elif theme.archetype == ArchetypeType.CORPORATE:
        return "Calibri"
    return "Calibri"


def _add_formatted_runs(paragraph, text: str, default_font: str, default_size: Pt, default_color: RGBColor, is_title: bool = False):
    """Parses inline Markdown and appends formatted TextRun objects to a PPTX paragraph."""
    runs_data = parse_markdown_runs(text)
    if not runs_data:
        run = paragraph.add_run()
        run.text = ""
        return

    for chunk_text, is_bold, is_italic, is_code in runs_data:
        run = paragraph.add_run()
        run.text = chunk_text
        run.font.name = "Consolas" if is_code else default_font
        run.font.size = default_size
        run.font.color.rgb = default_color
        run.font.bold = is_bold or is_title
        run.font.italic = is_italic


def render_pptx_presentation(pres: PresentationData, theme: ThemeConfig, dist_dir: Path) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    out_file = dist_dir / "presentation.pptx"

    prs = Presentation()
    # 16:9 Widescreen dimensions
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6]

    bg_rgb = RGBColor(*theme.hex_to_rgb(theme.colors['background']))
    card_bg_rgb = RGBColor(*theme.hex_to_rgb(theme.colors['card_bg']))
    card_border_rgb = RGBColor(*theme.hex_to_rgb(theme.colors.get('card_border', '#E2E8F0')))
    primary_text_rgb = RGBColor(*theme.hex_to_rgb(theme.colors['primary_text']))
    secondary_text_rgb = RGBColor(*theme.hex_to_rgb(theme.colors['secondary_text']))
    accent_rgb = RGBColor(*theme.hex_to_rgb(theme.colors['accent']))
    badge_bg_rgb = RGBColor(*theme.hex_to_rgb(theme.colors.get('badge_bg', '#DBEAFE')))
    badge_text_rgb = RGBColor(*theme.hex_to_rgb(theme.colors.get('badge_text', '#1E40AF')))

    total_slides = len(pres.slides)

    for slide_data in pres.slides:
        slide = prs.slides.add_slide(blank_layout)

        # 1. Slide background shape
        bg_shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg_shape.fill.solid()
        bg_shape.fill.fore_color.rgb = bg_rgb
        bg_shape.line.fill.background()  # no line

        # 2. Add Audio shape if present
        if slide_data.audio_path and slide_data.audio_path.exists():
            _add_audio_widget(slide, slide_data.audio_path, accent_rgb, badge_bg_rgb, badge_text_rgb, theme)

        # 3. Slide counter in bottom right
        counter_box = slide.shapes.add_textbox(Inches(11.5), Inches(6.8), Inches(1.2), Inches(0.4))
        cp = counter_box.text_frame.paragraphs[0]
        cp.text = f"{slide_data.index} / {total_slides}"
        cp.font.name = _get_font_name(theme)
        cp.font.size = Pt(11)
        cp.font.color.rgb = secondary_text_rgb
        cp.alignment = PP_ALIGN.RIGHT

        # 4. Render according to slide type and archetype
        deck_title = pres.title
        if slide_data.slide_type == SlideType.TITLE:
            _render_pptx_title_slide(
                slide, slide_data, theme,
                primary_text_rgb, secondary_text_rgb, accent_rgb, badge_bg_rgb, badge_text_rgb,
                deck_title=deck_title
            )
        elif slide_data.slide_type == SlideType.DEFINITION:
            _render_pptx_definition_slide(
                slide, slide_data, theme,
                card_bg_rgb, card_border_rgb, primary_text_rgb, secondary_text_rgb, accent_rgb,
                deck_title=deck_title
            )
        elif slide_data.slide_type == SlideType.CARDS:
            _render_pptx_cards_slide(
                slide, slide_data, theme,
                card_bg_rgb, card_border_rgb, primary_text_rgb, secondary_text_rgb, accent_rgb, badge_bg_rgb, badge_text_rgb,
                deck_title=deck_title
            )
        elif slide_data.slide_type == SlideType.CODE:
            _render_pptx_code_slide(
                slide, slide_data, theme,
                primary_text_rgb, secondary_text_rgb, accent_rgb,
                deck_title=deck_title
            )
        else:
            _render_pptx_standard_slide(
                slide, slide_data, theme,
                card_bg_rgb, card_border_rgb, primary_text_rgb, secondary_text_rgb, accent_rgb,
                deck_title=deck_title
            )

    prs.save(out_file)
    return out_file


def _add_audio_widget(slide, audio_path: Path, accent_rgb, badge_bg_rgb, badge_text_rgb, theme: ThemeConfig):
    font_name = _get_font_name(theme)
    # If neubrutalism, hard shadow for audio badge
    if theme.archetype == ArchetypeType.NEUBRUTALISM:
        sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(10.24), Inches(0.59), Inches(2.2), Inches(0.6))
        sh.fill.solid()
        sh.fill.fore_color.rgb = RGBColor(0, 0, 0)
        sh.line.fill.background()

    shape_type = MSO_SHAPE.RECTANGLE if theme.archetype in (ArchetypeType.NEUBRUTALISM, ArchetypeType.TERMINAL, ArchetypeType.CORPORATE) else MSO_SHAPE.ROUNDED_RECTANGLE
    badge = slide.shapes.add_shape(shape_type, Inches(10.2), Inches(0.55), Inches(2.2), Inches(0.6))
    badge.fill.solid()
    badge.fill.fore_color.rgb = badge_bg_rgb
    
    if theme.archetype == ArchetypeType.NEUBRUTALISM:
        badge.line.color.rgb = RGBColor(0, 0, 0)
        badge.line.width = Pt(2)
    else:
        badge.line.color.rgb = accent_rgb
        badge.line.width = Pt(1)
    
    tf = badge.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "  🔊 Audio Narration"
    p.font.name = font_name
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = badge_text_rgb
    p.alignment = PP_ALIGN.LEFT

    # Add native movie/audio shape (loudspeaker icon that plays on click)
    try:
        slide.shapes.add_movie(
            movie_file=str(audio_path),
            left=Inches(11.8),
            top=Inches(0.58),
            width=Inches(0.52),
            height=Inches(0.52),
            mime_type="audio/mp4"
        )
    except Exception as e:
        print(f"[PPTX] Warning: Could not embed audio {audio_path.name}: {e}")


def _render_pptx_title_slide(slide, slide_data: SlideData, theme: ThemeConfig,
                             primary_rgb, secondary_rgb, accent_rgb, badge_bg_rgb, badge_text_rgb,
                             deck_title: str = ""):
    font_name = _get_font_name(theme)
    arch = theme.archetype
    badge_label = deck_title.upper() if deck_title else "PREZENTÁCIÓ"

    # 1. Category badge
    if arch == ArchetypeType.EDITORIAL:
        # Subtle non-enclosed text with fine underline
        cat_box = slide.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(4.5), Inches(0.45))
        p = cat_box.text_frame.paragraphs[0]
        p.text = badge_label
        p.font.name = font_name
        p.font.size = Pt(12)
        p.font.bold = True
        p.font.color.rgb = accent_rgb
    elif arch == ArchetypeType.NEUBRUTALISM:
        # Shadow + thick border
        sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.04), Inches(1.84), Inches(3.4), Inches(0.45))
        sh.fill.solid()
        sh.fill.fore_color.rgb = RGBColor(0, 0, 0)
        sh.line.fill.background()

        cat_badge = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(1.8), Inches(3.4), Inches(0.45))
        cat_badge.fill.solid()
        cat_badge.fill.fore_color.rgb = badge_bg_rgb
        cat_badge.line.color.rgb = RGBColor(0, 0, 0)
        cat_badge.line.width = Pt(2)
        p = cat_badge.text_frame.paragraphs[0]
        p.text = badge_label
        p.font.name = font_name
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = badge_text_rgb
        p.alignment = PP_ALIGN.CENTER
    else:
        shape_type = MSO_SHAPE.RECTANGLE if arch in (ArchetypeType.TERMINAL, ArchetypeType.CORPORATE, ArchetypeType.MINIMAL) else MSO_SHAPE.ROUNDED_RECTANGLE
        cat_badge = slide.shapes.add_shape(shape_type, Inches(1.0), Inches(1.8), Inches(3.4), Inches(0.45))
        cat_badge.fill.solid()
        cat_badge.fill.fore_color.rgb = badge_bg_rgb
        cat_badge.line.fill.background()
        p = cat_badge.text_frame.paragraphs[0]
        prefix = "[INIT] " if arch == ArchetypeType.TERMINAL else ""
        p.text = f"{prefix}{badge_label}"
        p.font.name = font_name
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = badge_text_rgb
        p.alignment = PP_ALIGN.CENTER

    # 2. Main Title
    title_box = slide.shapes.add_textbox(Inches(1.0), Inches(2.5), Inches(11.0), Inches(2.2))
    tf = title_box.text_frame
    tf.word_wrap = True
    tp = tf.paragraphs[0]
    _add_formatted_runs(tp, slide_data.title, font_name, Pt(44), primary_rgb, is_title=True)

    # 3. Accent decorative line
    if arch != ArchetypeType.MINIMAL:
        line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(5.0), Inches(1.2), Inches(0.06))
        line.fill.solid()
        line.fill.fore_color.rgb = accent_rgb
        line.line.fill.background()

    # 4. Author / Subtitle
    if slide_data.author or slide_data.subtitle:
        author_text = slide_data.author or slide_data.subtitle
        author_box = slide.shapes.add_textbox(Inches(1.0), Inches(5.2), Inches(10.0), Inches(0.8))
        ap = author_box.text_frame.paragraphs[0]
        _add_formatted_runs(ap, author_text, font_name, Pt(22), secondary_rgb)


def _render_pptx_definition_slide(slide, slide_data: SlideData, theme: ThemeConfig,
                                  card_bg_rgb, card_border_rgb, primary_rgb, secondary_rgb, accent_rgb,
                                  deck_title: str = ""):
    cat_label = deck_title.upper() if deck_title else "DEFINÍCIÓ"
    _add_header(slide, cat_label, slide_data.title, accent_rgb, primary_rgb, theme)
    font_name = _get_font_name(theme)
    arch = theme.archetype
    first_para = slide_data.quote or (slide_data.paragraphs[0] if slide_data.paragraphs else "")

    if arch == ArchetypeType.EDITORIAL:
        # Elegant hairline top & bottom dividers, serif italic text, transparent card
        top_line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(2.4), Inches(11.333), Inches(0.015))
        top_line.fill.solid()
        top_line.fill.fore_color.rgb = card_border_rgb
        top_line.line.fill.background()

        bottom_line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(6.2), Inches(11.333), Inches(0.015))
        bottom_line.fill.solid()
        bottom_line.fill.fore_color.rgb = card_border_rgb
        bottom_line.line.fill.background()

        text_box = slide.shapes.add_textbox(Inches(1.0), Inches(2.8), Inches(11.333), Inches(3.2))
        tf = text_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.line_spacing = 1.4
        _add_formatted_runs(p, first_para, font_name, Pt(22), primary_rgb)

    elif arch == ArchetypeType.NEUBRUTALISM:
        # Black hard shadow offset rectangle
        sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.07), Inches(2.27), Inches(11.333), Inches(4.3))
        sh.fill.solid()
        sh.fill.fore_color.rgb = RGBColor(0, 0, 0)
        sh.line.fill.background()

        card = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(2.2), Inches(11.333), Inches(4.3))
        card.fill.solid()
        card.fill.fore_color.rgb = card_bg_rgb
        card.line.color.rgb = RGBColor(0, 0, 0)
        card.line.width = Pt(3)

        # Thick black left bar
        left_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(2.2), Inches(0.2), Inches(4.3))
        left_bar.fill.solid()
        left_bar.fill.fore_color.rgb = RGBColor(0, 0, 0)
        left_bar.line.fill.background()

        text_box = slide.shapes.add_textbox(Inches(1.5), Inches(2.6), Inches(10.3), Inches(3.5))
        tf = text_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.line_spacing = 1.35
        _add_formatted_runs(p, first_para, font_name, Pt(20), primary_rgb)

    elif arch == ArchetypeType.MINIMAL:
        # Transparent card, bold left vertical bar
        left_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(2.2), Inches(0.08), Inches(4.3))
        left_bar.fill.solid()
        left_bar.fill.fore_color.rgb = accent_rgb
        left_bar.line.fill.background()

        text_box = slide.shapes.add_textbox(Inches(1.4), Inches(2.4), Inches(10.9), Inches(3.8))
        tf = text_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.line_spacing = 1.4
        _add_formatted_runs(p, first_para, font_name, Pt(22), primary_rgb)

    elif arch == ArchetypeType.CORPORATE:
        # Sharp rectangle + top accent banner strip
        card = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(2.2), Inches(11.333), Inches(4.3))
        card.fill.solid()
        card.fill.fore_color.rgb = card_bg_rgb
        card.line.color.rgb = card_border_rgb
        card.line.width = Pt(1)

        banner = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(2.2), Inches(11.333), Inches(0.08))
        banner.fill.solid()
        banner.fill.fore_color.rgb = accent_rgb
        banner.line.fill.background()

        text_box = slide.shapes.add_textbox(Inches(1.5), Inches(2.6), Inches(10.3), Inches(3.5))
        tf = text_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.line_spacing = 1.35
        _add_formatted_runs(p, first_para, font_name, Pt(19), primary_rgb)

    else:
        # Terminal & Cards (modern cards)
        shape_type = MSO_SHAPE.RECTANGLE if arch == ArchetypeType.TERMINAL else MSO_SHAPE.ROUNDED_RECTANGLE
        card = slide.shapes.add_shape(shape_type, Inches(1.0), Inches(2.2), Inches(11.333), Inches(4.3))
        card.fill.solid()
        card.fill.fore_color.rgb = card_bg_rgb
        card.line.color.rgb = card_border_rgb
        card.line.width = Pt(1)

        left_bar = slide.shapes.add_shape(shape_type, Inches(1.0), Inches(2.2), Inches(0.12), Inches(4.3))
        left_bar.fill.solid()
        left_bar.fill.fore_color.rgb = accent_rgb
        left_bar.line.fill.background()

        text_box = slide.shapes.add_textbox(Inches(1.5), Inches(2.6), Inches(10.3), Inches(3.5))
        tf = text_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.line_spacing = 1.35
        _add_formatted_runs(p, first_para, font_name, Pt(19), primary_rgb)


def _render_pptx_cards_slide(slide, slide_data: SlideData, theme: ThemeConfig,
                             card_bg_rgb, card_border_rgb, primary_rgb, secondary_rgb, accent_rgb, badge_bg_rgb, badge_text_rgb,
                             deck_title: str = ""):
    cat_label = deck_title.upper() if deck_title else "ÁTTEKINTÉS"
    _add_header(slide, cat_label, slide_data.title, accent_rgb, primary_rgb, theme)
    font_name = _get_font_name(theme)
    arch = theme.archetype

    has_intro = bool(slide_data.paragraphs)
    top = Inches(2.9) if has_intro else Inches(2.2)
    height = Inches(3.7) if has_intro else Inches(4.3)

    if has_intro:
        intro_box = slide.shapes.add_textbox(Inches(1.0), Inches(2.1), Inches(11.333), Inches(0.65))
        itf = intro_box.text_frame
        itf.word_wrap = True
        ip = itf.paragraphs[0]
        _add_formatted_runs(ip, slide_data.paragraphs[0], font_name, Pt(16), secondary_rgb)

    num_cards = max(1, min(4, len(slide_data.cards)))
    if num_cards == 1:
        card_w = Inches(11.333)
        gap = Inches(0)
    elif num_cards == 2:
        card_w = Inches(5.45)
        gap = Inches(0.43)
    elif num_cards == 3:
        card_w = Inches(3.5)
        gap = Inches(0.41)
    else:  # 4 cards
        card_w = Inches(2.6)
        gap = Inches(0.31)

    for i, c in enumerate(slide_data.cards[:4]):
        left = Inches(1.0) + i * (card_w + gap)

        if arch == ArchetypeType.EDITORIAL:
            # Transparent cards, left vertical hairline accent
            left_line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top + Inches(0.1), Inches(0.03), height - Inches(0.2))
            left_line.fill.solid()
            left_line.fill.fore_color.rgb = accent_rgb
            left_line.line.fill.background()

            # Elegant Roman / numeric index
            idx_box = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.1), Inches(1.5), Inches(0.4))
            ip = idx_box.text_frame.paragraphs[0]
            ip.text = f"{c.card_index}."
            ip.font.name = font_name
            ip.font.size = Pt(14)
            ip.font.bold = True
            ip.font.color.rgb = accent_rgb

            # Title
            title_box = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.55), card_w - Inches(0.3), Inches(1.2))
            tf_t = title_box.text_frame
            tf_t.word_wrap = True
            tp = tf_t.paragraphs[0]
            _add_formatted_runs(tp, c.title, font_name, Pt(21), primary_rgb, is_title=True)

            # Desc
            desc_box = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(1.8), card_w - Inches(0.3), Inches(2.2))
            tf_d = desc_box.text_frame
            tf_d.word_wrap = True
            dp = tf_d.paragraphs[0]
            dp.line_spacing = 1.35
            _add_formatted_runs(dp, c.description, font_name, Pt(16), secondary_rgb)

        elif arch == ArchetypeType.NEUBRUTALISM:
            # Hard black shadow shape
            sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left + Inches(0.07), top + Inches(0.07), card_w, height)
            sh.fill.solid()
            sh.fill.fore_color.rgb = RGBColor(0, 0, 0)
            sh.line.fill.background()

            # Card shape on top
            card = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, card_w, height)
            card.fill.solid()
            card.fill.fore_color.rgb = card_bg_rgb
            card.line.color.rgb = RGBColor(0, 0, 0)
            card.line.width = Pt(2.5)

            # Badge shadow + badge
            b_sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left + Inches(0.44), top + Inches(0.44), Inches(0.55), Inches(0.45))
            b_sh.fill.solid()
            b_sh.fill.fore_color.rgb = RGBColor(0, 0, 0)
            b_sh.line.fill.background()

            badge = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left + Inches(0.4), top + Inches(0.4), Inches(0.55), Inches(0.45))
            badge.fill.solid()
            badge.fill.fore_color.rgb = accent_rgb
            badge.line.color.rgb = RGBColor(0, 0, 0)
            badge.line.width = Pt(2)
            bp = badge.text_frame.paragraphs[0]
            bp.text = f"0{c.card_index}" if c.card_index < 10 else str(c.card_index)
            bp.font.name = font_name
            bp.font.size = Pt(13)
            bp.font.bold = True
            bp.font.color.rgb = RGBColor(0, 0, 0)
            bp.alignment = PP_ALIGN.CENTER

            title_box = slide.shapes.add_textbox(left + Inches(0.4), top + Inches(1.05), card_w - Inches(0.8), Inches(1.1))
            tf_t = title_box.text_frame
            tf_t.word_wrap = True
            tp = tf_t.paragraphs[0]
            _add_formatted_runs(tp, c.title, font_name, Pt(20), primary_rgb, is_title=True)

            desc_box = slide.shapes.add_textbox(left + Inches(0.4), top + Inches(2.2), card_w - Inches(0.8), Inches(1.8))
            tf_d = desc_box.text_frame
            tf_d.word_wrap = True
            dp = tf_d.paragraphs[0]
            dp.line_spacing = 1.3
            _add_formatted_runs(dp, c.description, font_name, Pt(16), secondary_rgb)

        elif arch == ArchetypeType.MINIMAL:
            # Transparent cards, oversized numeric badge above title
            idx_box = slide.shapes.add_textbox(left, top, card_w, Inches(0.7))
            ip = idx_box.text_frame.paragraphs[0]
            ip.text = f"0{c.card_index}" if c.card_index < 10 else str(c.card_index)
            ip.font.name = font_name
            ip.font.size = Pt(36)
            ip.font.bold = True
            ip.font.color.rgb = accent_rgb

            title_box = slide.shapes.add_textbox(left, top + Inches(0.75), card_w, Inches(1.1))
            tf_t = title_box.text_frame
            tf_t.word_wrap = True
            tp = tf_t.paragraphs[0]
            _add_formatted_runs(tp, c.title, font_name, Pt(21), primary_rgb, is_title=True)

            desc_box = slide.shapes.add_textbox(left, top + Inches(1.9), card_w, Inches(2.2))
            tf_d = desc_box.text_frame
            tf_d.word_wrap = True
            dp = tf_d.paragraphs[0]
            dp.line_spacing = 1.35
            _add_formatted_runs(dp, c.description, font_name, Pt(16), secondary_rgb)

        elif arch == ArchetypeType.CORPORATE:
            # Sharp rectangle + top accent banner
            card = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, card_w, height)
            card.fill.solid()
            card.fill.fore_color.rgb = card_bg_rgb
            card.line.color.rgb = card_border_rgb
            card.line.width = Pt(1)

            banner = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, card_w, Inches(0.08))
            banner.fill.solid()
            banner.fill.fore_color.rgb = accent_rgb
            banner.line.fill.background()

            badge = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left + Inches(0.35), top + Inches(0.35), Inches(0.55), Inches(0.4))
            badge.fill.solid()
            badge.fill.fore_color.rgb = accent_rgb
            badge.line.fill.background()
            bp = badge.text_frame.paragraphs[0]
            bp.text = f"0{c.card_index}" if c.card_index < 10 else str(c.card_index)
            bp.font.name = font_name
            bp.font.size = Pt(11)
            bp.font.bold = True
            bp.font.color.rgb = RGBColor(255, 255, 255)
            bp.alignment = PP_ALIGN.CENTER

            title_box = slide.shapes.add_textbox(left + Inches(0.35), top + Inches(0.95), card_w - Inches(0.7), Inches(1.1))
            tf_t = title_box.text_frame
            tf_t.word_wrap = True
            tp = tf_t.paragraphs[0]
            _add_formatted_runs(tp, c.title, font_name, Pt(20), primary_rgb, is_title=True)

            desc_box = slide.shapes.add_textbox(left + Inches(0.35), top + Inches(2.1), card_w - Inches(0.7), Inches(1.9))
            tf_d = desc_box.text_frame
            tf_d.word_wrap = True
            dp = tf_d.paragraphs[0]
            dp.line_spacing = 1.3
            _add_formatted_runs(dp, c.description, font_name, Pt(15), secondary_rgb)

        else:
            # Terminal & Modern Cards
            shape_type = MSO_SHAPE.RECTANGLE if arch == ArchetypeType.TERMINAL else MSO_SHAPE.ROUNDED_RECTANGLE
            card = slide.shapes.add_shape(shape_type, left, top, card_w, height)
            card.fill.solid()
            card.fill.fore_color.rgb = card_bg_rgb
            card.line.color.rgb = card_border_rgb
            card.line.width = Pt(1)

            badge = slide.shapes.add_shape(shape_type, left + Inches(0.4), top + Inches(0.4), Inches(0.55), Inches(0.45))
            badge.fill.solid()
            badge.fill.fore_color.rgb = badge_bg_rgb
            badge.line.fill.background()
            bp = badge.text_frame.paragraphs[0]
            bp.text = f"0{c.card_index}" if c.card_index < 10 else str(c.card_index)
            bp.font.name = font_name
            bp.font.size = Pt(12)
            bp.font.bold = True
            bp.font.color.rgb = badge_text_rgb
            bp.alignment = PP_ALIGN.CENTER

            title_box = slide.shapes.add_textbox(left + Inches(0.4), top + Inches(1.05), card_w - Inches(0.8), Inches(1.1))
            tf_t = title_box.text_frame
            tf_t.word_wrap = True
            tp = tf_t.paragraphs[0]
            title_prefix = "> " if arch == ArchetypeType.TERMINAL else ""
            _add_formatted_runs(tp, f"{title_prefix}{c.title}", font_name, Pt(20), primary_rgb, is_title=True)

            desc_box = slide.shapes.add_textbox(left + Inches(0.4), top + Inches(2.2), card_w - Inches(0.8), Inches(1.8))
            tf_d = desc_box.text_frame
            tf_d.word_wrap = True
            dp = tf_d.paragraphs[0]
            dp.line_spacing = 1.3
            _add_formatted_runs(dp, c.description, font_name, Pt(16), secondary_rgb)


def _render_pptx_code_slide(slide, slide_data: SlideData, theme: ThemeConfig,
                            primary_rgb, secondary_rgb, accent_rgb,
                            deck_title: str = ""):
    _add_header(slide, "KÓDRÉSZLET", slide_data.title, accent_rgb, primary_rgb, theme)
    lang = (slide_data.code_snippet.get("language") if slide_data.code_snippet else "code") or "code"
    code_text = (slide_data.code_snippet.get("code") if slide_data.code_snippet else "") or ""

    box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(2.2), Inches(11.333), Inches(4.3))
    box.fill.solid()
    box.fill.fore_color.rgb = RGBColor(13, 17, 23)
    box.line.color.rgb = accent_rgb
    box.line.width = Pt(1)

    lbl = slide.shapes.add_textbox(Inches(1.2), Inches(2.3), Inches(4.0), Inches(0.4))
    lp = lbl.text_frame.paragraphs[0]
    lp.text = f"// LANGUAGE: {lang.upper()}"
    lp.font.name = "Consolas"
    lp.font.size = Pt(11)
    lp.font.bold = True
    lp.font.color.rgb = accent_rgb

    code_box = slide.shapes.add_textbox(Inches(1.2), Inches(2.8), Inches(10.9), Inches(3.5))
    tf = code_box.text_frame
    tf.word_wrap = True
    lines = code_text.splitlines()[:14]
    for idx, line in enumerate(lines):
        p = tf.add_paragraph() if idx > 0 else tf.paragraphs[0]
        p.text = line
        p.font.name = "Consolas"
        p.font.size = Pt(13)
        p.font.color.rgb = RGBColor(230, 237, 243)


def _render_pptx_standard_slide(slide, slide_data: SlideData, theme: ThemeConfig,
                                card_bg_rgb, card_border_rgb, primary_rgb, secondary_rgb, accent_rgb,
                                deck_title: str = ""):
    cat_label = deck_title.upper() if deck_title else "ÁTTEKINTÉS"
    _add_header(slide, cat_label, slide_data.title, accent_rgb, primary_rgb, theme)
    font_name = _get_font_name(theme)
    tb = slide.shapes.add_textbox(Inches(1.0), Inches(2.2), Inches(11.333), Inches(4.3))
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for p_text in slide_data.paragraphs:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(12)
        _add_formatted_runs(p, p_text, font_name, Pt(18), primary_rgb)

    for item_text in slide_data.list_items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(8)
        p.level = 0
        bullet_run = p.add_run()
        bullet_run.text = "• "
        bullet_run.font.name = font_name
        bullet_run.font.size = Pt(18)
        bullet_run.font.bold = True
        bullet_run.font.color.rgb = accent_rgb
        _add_formatted_runs(p, item_text, font_name, Pt(18), primary_rgb)


def _add_header(slide, category: str, title: str, accent_rgb, primary_rgb, theme: ThemeConfig):
    font_name = _get_font_name(theme)
    arch = theme.archetype

    # Category lead
    cat_box = slide.shapes.add_textbox(Inches(1.0), Inches(0.5), Inches(8.0), Inches(0.35))
    cp = cat_box.text_frame.paragraphs[0]
    prefix = "root@slides:~# " if arch == ArchetypeType.TERMINAL else ""
    cp.text = f"{prefix}{category}"
    cp.font.name = font_name
    cp.font.size = Pt(11)
    cp.font.bold = True
    cp.font.color.rgb = accent_rgb

    # Slide Title
    title_box = slide.shapes.add_textbox(Inches(1.0), Inches(0.85), Inches(9.0), Inches(1.1))
    tf = title_box.text_frame
    tf.word_wrap = True
    tp = tf.paragraphs[0]
    _add_formatted_runs(tp, title, font_name, Pt(28), primary_rgb, is_title=True)

    # Editorial hairline header separator
    if arch == ArchetypeType.EDITORIAL:
        hdr_rule = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(1.95), Inches(11.333), Inches(0.015))
        hdr_rule.fill.solid()
        hdr_rule.fill.fore_color.rgb = RGBColor(*theme.hex_to_rgb(theme.colors.get('card_border', '#EADBCE')))
        hdr_rule.line.fill.background()


