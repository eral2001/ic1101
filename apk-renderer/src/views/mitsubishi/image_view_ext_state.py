"""
ImageViewExtState - Mitsubishi's extended ImageView with state support.

This appears to be a custom ImageView variant. We delegate to the standard
ImageView implementation.
"""

from models import LayoutChildCallback, MeasureChildCallback, MeasureSpec, RenderContext, View
from views.android.image_view import measure_image_view as _measure_image_view
from views.android.image_view import layout_image_view as _layout_image_view


def measure_image_view_ext_state(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """Measure ImageViewExtState - delegates to standard ImageView."""
    _measure_image_view(view, width_spec, height_spec, ctx, measure_child)


def layout_image_view_ext_state(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """Layout ImageViewExtState - delegates to standard ImageView."""
    _layout_image_view(view, parent_x, parent_y, parent_width, parent_height, ctx, layout_child)
