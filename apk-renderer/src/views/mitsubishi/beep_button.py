"""
BeepButton - Mitsubishi's BeepButton with sound effects.

This appears to be a custom Button variant that likely plays a beep sound
on press. For rendering purposes, we delegate to the standard Button implementation.
"""

from models import LayoutChildCallback, MeasureChildCallback, MeasureSpec, RenderContext, View
from views.android.button import measure_button as _measure_button
from views.android.button import layout_button as _layout_button


def measure_beep_button(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """Measure BeepButton - delegates to standard Button."""
    _measure_button(view, width_spec, height_spec, ctx, measure_child)


def layout_beep_button(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """Layout BeepButton - delegates to standard Button."""
    _layout_button(view, parent_x, parent_y, parent_width, parent_height, ctx, layout_child)
