from models import LayoutChildCallback, MeasureChildCallback, MeasureSpec, RenderContext, View
from views.android.view import layout_view, measure_view


def layout_space(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """
    Layout a Space view.

    Space delegates to View's layout logic.
    """
    layout_view(view, parent_x, parent_y, parent_width, parent_height, ctx, layout_child)


def measure_space(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure a Space view.

    Space is a lightweight View subclass used to create gaps between components.
    It has the same measurement behavior as a generic View (no intrinsic size).
    """
    # Space delegates to the generic View measurement logic
    measure_view(view, width_spec, height_spec, ctx, measure_child)
