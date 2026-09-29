from pathlib import Path
from typing import Optional
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from ..models import PresentationData, SlideData, SlideType, ThemeConfig, ArchetypeType


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
        if slide_data.slide_type == SlideType.TITLE:
            _render_pptx_title_slide(
                slide, slide_data, theme,
                primary_text_rgb, secondary_text_rgb, accent_rgb, badge_bg_rgb, badge_text_rgb
            )
        elif slide_data.slide_type == SlideType.DEFINITION:
            _render_pptx_definition_slide(
                slide, slide_data, theme,
                card_bg_rgb, card_border_rgb, primary_text_rgb, secondary_text_rgb, accent_rgb
            )
        elif slide_data.slide_type == SlideType.CARDS:
            _render_pptx_cards_slide(
                slide, slide_data, theme,
                card_bg_rgb, card_border_rgb, primary_text_rgb, secondary_text_rgb, accent_rgb, badge_bg_rgb, badge_text_rgb
            )
        else:
            _render_pptx_standard_slide(
                slide, slide_data, theme,
                card_bg_rgb, card_border_rgb, primary_text_rgb, secondary_text_rgb, accent_rgb
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
                             primary_rgb, secondary_rgb, accent_rgb, badge_bg_rgb, badge_text_rgb):
    font_name = _get_font_name(theme)
    arch = theme.archetype

    # 1. Category badge
    if arch == ArchetypeType.EDITORIAL:
        # Subtle non-enclosed text with fine underline
        cat_box = slide.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(4.5), Inches(0.45))
        p = cat_box.text_frame.paragraphs[0]
        p.text = "PISA KUTATÁS • MATEMATIKA"
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
        p.text = "PISA KUTATÁS • MATEMATIKA"
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
        p.text = f"{prefix}PISA KUTATÁS • MATEMATIKA"
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
    tp.text = slide_data.title
    tp.font.name = font_name
    tp.font.size = Pt(44)
    tp.font.bold = True
    tp.font.color.rgb = primary_rgb

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
        ap.text = author_text
        ap.font.name = font_name
        ap.font.size = Pt(22)
        ap.font.color.rgb = secondary_rgb


def _render_pptx_definition_slide(slide, slide_data: SlideData, theme: ThemeConfig,
                                  card_bg_rgb, card_border_rgb, primary_rgb, secondary_rgb, accent_rgb):
    _add_header(slide, "ALAPFOGALMAK", slide_data.title, accent_rgb, primary_rgb, theme)
    font_name = _get_font_name(theme)
    arch = theme.archetype
    first_para = slide_data.paragraphs[0] if slide_data.paragraphs else ""

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
        p.text = first_para
        p.font.name = font_name
        p.font.size = Pt(22)
        p.font.italic = True
        p.font.color.rgb = primary_rgb
        p.line_spacing = 1.4

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
        p.text = first_para
        p.font.name = font_name
        p.font.size = Pt(20)
        p.font.color.rgb = primary_rgb
        p.line_spacing = 1.35

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
        p.text = first_para
        p.font.name = font_name
        p.font.size = Pt(22)
        p.font.color.rgb = primary_rgb
        p.line_spacing = 1.4

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
        p.text = first_para
        p.font.name = font_name
        p.font.size = Pt(19)
        p.font.color.rgb = primary_rgb
        p.line_spacing = 1.35

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
        p.text = first_para
        p.font.name = font_name
        p.font.size = Pt(19)
        p.font.color.rgb = primary_rgb
        p.line_spacing = 1.35


def _render_pptx_cards_slide(slide, slide_data: SlideData, theme: ThemeConfig,
                             card_bg_rgb, card_border_rgb, primary_rgb, secondary_rgb, accent_rgb, badge_bg_rgb, badge_text_rgb):
    _add_header(slide, "MÉRÉSI TERÜLETEK", slide_data.title, accent_rgb, primary_rgb, theme)
    font_name = _get_font_name(theme)
    arch = theme.archetype

    num_cards = len(slide_data.cards)
    card_w = Inches(5.45) if num_cards == 2 else Inches(11.333) / max(1, num_cards) - Inches(0.3)
    gap = Inches(0.43) if num_cards == 2 else Inches(0.3)
    top = Inches(2.2)
    height = Inches(4.3)

    for i, c in enumerate(slide_data.cards):
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
            tp.text = c.title
            tp.font.name = font_name
            tp.font.size = Pt(21)
            tp.font.bold = True
            tp.font.color.rgb = primary_rgb

            # Desc
            desc_box = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(1.8), card_w - Inches(0.3), Inches(2.2))
            tf_d = desc_box.text_frame
            tf_d.word_wrap = True
            dp = tf_d.paragraphs[0]
            dp.text = c.description
            dp.font.name = font_name
            dp.font.size = Pt(16)
            dp.font.color.rgb = secondary_rgb
            dp.line_spacing = 1.35

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
            tp.text = c.title
            tp.font.name = font_name
            tp.font.size = Pt(20)
            tp.font.bold = True
            tp.font.color.rgb = primary_rgb

            desc_box = slide.shapes.add_textbox(left + Inches(0.4), top + Inches(2.2), card_w - Inches(0.8), Inches(1.8))
            tf_d = desc_box.text_frame
            tf_d.word_wrap = True
            dp = tf_d.paragraphs[0]
            dp.text = c.description
            dp.font.name = font_name
            dp.font.size = Pt(16)
            dp.font.color.rgb = secondary_rgb
            dp.line_spacing = 1.3

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
            tp.text = c.title
            tp.font.name = font_name
            tp.font.size = Pt(21)
            tp.font.bold = True
            tp.font.color.rgb = primary_rgb

            desc_box = slide.shapes.add_textbox(left, top + Inches(1.9), card_w, Inches(2.2))
            tf_d = desc_box.text_frame
            tf_d.word_wrap = True
            dp = tf_d.paragraphs[0]
            dp.text = c.description
            dp.font.name = font_name
            dp.font.size = Pt(16)
            dp.font.color.rgb = secondary_rgb
            dp.line_spacing = 1.35

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
            tp.text = c.title
            tp.font.name = font_name
            tp.font.size = Pt(20)
            tp.font.bold = True
            tp.font.color.rgb = primary_rgb

            desc_box = slide.shapes.add_textbox(left + Inches(0.35), top + Inches(2.1), card_w - Inches(0.7), Inches(1.9))
            tf_d = desc_box.text_frame
            tf_d.word_wrap = True
            dp = tf_d.paragraphs[0]
            dp.text = c.description
            dp.font.name = font_name
            dp.font.size = Pt(15)
            dp.font.color.rgb = secondary_rgb
            dp.line_spacing = 1.3

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
            tp.text = f"{title_prefix}{c.title}"
            tp.font.name = font_name
            tp.font.size = Pt(20)
            tp.font.bold = True
            tp.font.color.rgb = primary_rgb

            desc_box = slide.shapes.add_textbox(left + Inches(0.4), top + Inches(2.2), card_w - Inches(0.8), Inches(1.8))
            tf_d = desc_box.text_frame
            tf_d.word_wrap = True
            dp = tf_d.paragraphs[0]
            dp.text = c.description
            dp.font.name = font_name
            dp.font.size = Pt(16)
            dp.font.color.rgb = secondary_rgb
            dp.line_spacing = 1.3


def _render_pptx_standard_slide(slide, slide_data: SlideData, theme: ThemeConfig,
                                card_bg_rgb, card_border_rgb, primary_rgb, secondary_rgb, accent_rgb):
    _add_header(slide, "ÁTTEKINTÉS", slide_data.title, accent_rgb, primary_rgb, theme)
    font_name = _get_font_name(theme)
    tb = slide.shapes.add_textbox(Inches(1.0), Inches(2.2), Inches(11.333), Inches(4.3))
    tf = tb.text_frame
    tf.word_wrap = True
    for p_text in slide_data.paragraphs:
        p = tf.add_paragraph()
        p.text = p_text
        p.font.name = font_name
        p.font.size = Pt(18)
        p.font.color.rgb = primary_rgb


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
    tp.text = title
    tp.font.name = font_name
    tp.font.size = Pt(28)
    tp.font.bold = True
    tp.font.color.rgb = primary_rgb

    # Editorial hairline header separator
    if arch == ArchetypeType.EDITORIAL:
        hdr_rule = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(1.95), Inches(11.333), Inches(0.015))
        hdr_rule.fill.solid()
        hdr_rule.fill.fore_color.rgb = RGBColor(*theme.hex_to_rgb(theme.colors.get('card_border', '#EADBCE')))
        hdr_rule.line.fill.background()

