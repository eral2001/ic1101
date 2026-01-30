from models import LayoutChildCallback, MeasureChildCallback, MeasureSpec, RenderContext, View
from views.android.text_view import layout_text_view, measure_text_view


def layout_button(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """Layout a Button (delegates to TextView)."""
    layout_text_view(view, parent_x, parent_y, parent_width, parent_height, ctx, layout_child)


def measure_button(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure a Button.

    Button is a TextView subclass that doesn't override measurement logic.
    The only differences from TextView are in default styling from buttonStyle:
    - minHeight: 48dip (touch target size)
    - minWidth: 64dip (normal) or 48dip (small)
    - Different background drawable (btn_default_holo_dark)
    - Different text appearance (bold, centered)

    Button delegates to TextView's measurement implementation.
    """
    # Button uses TextView's measurement logic directly
    measure_text_view(view, width_spec, height_spec, ctx, measure_child)
