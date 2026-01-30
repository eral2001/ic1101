"""
AbsoluteLayoutExtState - Mitsubishi's extended AbsoluteLayout with state support.

This appears to be a custom AbsoluteLayout variant. AbsoluteLayout positions
children at explicit x,y coordinates specified by android:layout_x and android:layout_y.

Since we don't have a full AbsoluteLayout implementation yet, we'll implement
basic positioning here.
"""

from models import LayoutChildCallback, MeasureChildCallback, MeasureSpec, MeasureSpecMode, RenderContext, View
from resources import deref_dimension, deref_dimension_to_pixels, get_padding
from measure_spec import constrain_to_spec, get_child_measure_spec


def measure_absolute_layout_ext_state(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure AbsoluteLayoutExtState.

    Measures all children and sizes the container to either:
    - The specified size (if EXACTLY)
    - The minimum size needed to contain all children (if AT_MOST or UNSPECIFIED)
    """
    padding = get_padding(view.attributes, ctx)

    # Measure all children
    max_width = 0
    max_height = 0

    for child in view.children:
        if child.attributes.get("android:visibility") == "gone":
            continue

        # Get child's layout params
        child_width_dim = deref_dimension(child.attributes.get("android:layout_width"), ctx)
        child_height_dim = deref_dimension(child.attributes.get("android:layout_height"), ctx)

        # Calculate available space for child (parent's content area)
        available_width = max(0, width_spec.size - padding.left - padding.right) if width_spec.mode != MeasureSpecMode.UNSPECIFIED else 0
        available_height = max(0, height_spec.size - padding.top - padding.bottom) if height_spec.mode != MeasureSpecMode.UNSPECIFIED else 0

        # Create child MeasureSpecs based on layout params
        child_width_spec = get_child_measure_spec(
            MeasureSpec(width_spec.mode, available_width),
            0,  # AbsoluteLayout doesn't use margins
            child_width_dim
        )
        child_height_spec = get_child_measure_spec(
            MeasureSpec(height_spec.mode, available_height),
            0,  # AbsoluteLayout doesn't use margins
            child_height_dim
        )

        # Measure child with proper specs
        measure_child(child, child_width_spec, child_height_spec, ctx)

        # Get child's position (android:layout_x, android:layout_y)
        child_x = deref_dimension_to_pixels(child.attributes.get("android:layout_x"), ctx, 0)
        child_y = deref_dimension_to_pixels(child.attributes.get("android:layout_y"), ctx, 0)

        # Calculate required size to contain this child
        max_width = max(max_width, child_x + child.width)
        max_height = max(max_height, child_y + child.height)

    # Add padding
    desired_width = max_width + padding.left + padding.right
    desired_height = max_height + padding.top + padding.bottom

    # Resolve against MeasureSpec
    view.width = constrain_to_spec(desired_width, width_spec)
    view.height = constrain_to_spec(desired_height, height_spec)


def layout_absolute_layout_ext_state(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """
    Layout AbsoluteLayoutExtState.

    Positions children at their specified x,y coordinates relative to the container.
    """
    view.x = parent_x
    view.y = parent_y

    padding = get_padding(view.attributes, ctx)

    # Position each child at its specified coordinates
    for child in view.children:
        if child.attributes.get("android:visibility") == "gone":
            continue

        # Get child's position (android:layout_x, android:layout_y)
        child_x = deref_dimension_to_pixels(child.attributes.get("android:layout_x"), ctx, 0)
        child_y = deref_dimension_to_pixels(child.attributes.get("android:layout_y"), ctx, 0)

        # Position child at absolute coordinates (relative to parent, with padding)
        absolute_x = view.x + padding.left + child_x
        absolute_y = view.y + padding.top + child_y

        # Calculate available space for child
        available_width = view.width - padding.left - padding.right
        available_height = view.height - padding.top - padding.bottom

        layout_child(child, absolute_x, absolute_y, available_width, available_height, ctx)
