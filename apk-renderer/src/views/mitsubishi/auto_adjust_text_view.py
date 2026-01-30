"""
AutoAdjustTextView - Mitsubishi's auto-sizing TextView.

This custom view automatically adjusts text size to fit within its bounds.
It scales down from android:textSize to android:downtextSize.
"""

from typing import Callable

from PIL import Image, ImageFont

from models import LayoutChildCallback, MeasureChildCallback, MeasureSpec, RenderContext, View
from resources import deref_dimension_to_pixels, deref_string, get_padding, get_text_size
from views.android.view import draw_background
from views.android.text_view import (
    measure_text_view as _measure_text_view,
    layout_text_view as _layout_text_view,
    get_text_attributes,
    _draw_text_with_size,
)


def measure_auto_adjust_text_view(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """Measure AutoAdjustTextView - delegates to standard TextView."""
    _measure_text_view(view, width_spec, height_spec, ctx, measure_child)


def layout_auto_adjust_text_view(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """Layout AutoAdjustTextView - delegates to standard TextView."""
    _layout_text_view(view, parent_x, parent_y, parent_width, parent_height, ctx, layout_child)


def draw_auto_adjust_text_view(
    view: View,
    canvas: Image.Image,
    ctx: RenderContext,
    draw_child: Callable[[View, Image.Image, RenderContext], None],
) -> None:
    """
    Draw AutoAdjustTextView with auto-sizing behavior.

    If text at textSize is wider than the content area, the font size is
    progressively reduced by 1px until it fits or reaches downtextSize.
    """
    if view.width <= 0 or view.height <= 0:
        return

    draw_background(view, canvas, ctx)

    text = deref_string(view.attributes.get("android:text"), ctx)
    if not text:
        return

    text_attrs = get_text_attributes(view, ctx)
    text_size_px = get_text_size(text_attrs.get("textSize"), ctx)

    # Resolve downtextSize (Mitsubishi custom attribute in android: namespace)
    down_text_size_raw = view.attributes.get("android:downtextSize")
    if down_text_size_raw is not None:
        down_text_size_px = deref_dimension_to_pixels(down_text_size_raw, ctx, text_size_px)
    else:
        down_text_size_px = text_size_px

    # Auto-size: shrink text to fit content width if needed
    final_size_px = text_size_px
    if down_text_size_px < text_size_px:
        padding = get_padding(view.attributes, ctx)
        content_width = view.width - padding.left - padding.right

        typeface = text_attrs.get("typeface")
        text_style = text_attrs.get("textStyle")
        font_path = ctx.font_config.resolve_font(typeface, text_style)

        current_size = text_size_px
        while current_size > down_text_size_px:
            try:
                font = ImageFont.truetype(str(font_path), current_size)
            except (OSError, IOError):
                break
            bbox = font.getbbox(text)
            text_width = bbox[2] - bbox[0]
            if text_width <= content_width:
                break
            current_size -= 1

        final_size_px = current_size

    _draw_text_with_size(view, canvas, ctx, text, text_attrs, final_size_px)
