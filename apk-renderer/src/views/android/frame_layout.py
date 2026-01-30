from typing import Callable

from PIL import Image

from models import LayoutChildCallback, MeasureChildCallback, MeasureSpec, MeasureSpecMode, RenderContext, View
from resources import (
    deref_dimension,
    deref_dimension_to_pixels,
    deref_gravity,
    get_margins,
    get_padding,
)
from measure_spec import constrain_to_spec, get_child_measure_spec
from gravity import Gravity, apply_gravity


def layout_frame_layout(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """
    Layout a FrameLayout and its children.

    FrameLayout stacks children on top of each other. Each child's position
    is determined by its layout_gravity attribute (defaulting to top-left).
    """
    # Set our own position
    view.x = parent_x
    view.y = parent_y

    # Get padding
    padding = get_padding(view.attributes, ctx)

    # Calculate content area
    content_left = view.x + padding.left
    content_top = view.y + padding.top
    content_width = view.width - padding.left - padding.right
    content_height = view.height - padding.top - padding.bottom

    # Layout each child (stacked on top of each other)
    for child in view.children:
        # Skip gone children
        if child.attributes.get("android:visibility") == "gone":
            continue

        # Get child's margins and layout_gravity
        margins = get_margins(child.attributes, ctx)
        layout_gravity = deref_gravity(child.attributes.get("android:layout_gravity"), ctx, Gravity.TOP | Gravity.LEFT)

        # Apply gravity to position child within content area
        # Note: apply_gravity expects container bounds as (left, top, right, bottom) coordinates
        container_left = content_left + margins.left
        container_top = content_top + margins.top
        container_right = content_left + content_width - margins.right
        container_bottom = content_top + content_height - margins.bottom

        child_left, child_top, child_right, child_bottom = apply_gravity(
            layout_gravity,
            child.width,
            child.height,
            container_left,
            container_top,
            container_right,
            container_bottom
        )

        # Layout the child at the calculated position
        layout_child(child, child_left, child_top, content_width, content_height, ctx)


def measure_frame_layout(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure a FrameLayout and all its children.

    FrameLayout is a simple container that stacks children on top of each other.
    This function only determines dimensions (width/height), not positions (x/y).
    """

    padding = get_padding(view.attributes, ctx)

    # Track maximum child dimensions for wrap_content
    max_child_width = 0
    max_child_height = 0

    for child in view.children:
        if child.attributes.get("android:visibility") == "gone":
            continue

        margins = get_margins(child.attributes, ctx)
        child_width_dim = deref_dimension(child.attributes.get("android:layout_width"), ctx)
        child_height_dim = deref_dimension(child.attributes.get("android:layout_height"), ctx)

        # Calculate child MeasureSpecs
        child_width_spec = get_child_measure_spec(
            width_spec,
            padding.left + padding.right + margins.left + margins.right,
            child_width_dim
        )
        child_height_spec = get_child_measure_spec(
            height_spec,
            padding.top + padding.bottom + margins.top + margins.bottom,
            child_height_dim
        )

        # Measure child
        measure_child(child, child_width_spec, child_height_spec, ctx)

        # Track maximum dimensions (including margins)
        child_total_width = child.width + margins.left + margins.right
        child_total_height = child.height + margins.top + margins.bottom

        max_child_width = max(max_child_width, child_total_width)
        max_child_height = max(max_child_height, child_total_height)

    # Calculate our desired size
    desired_width = max_child_width + padding.left + padding.right
    desired_height = max_child_height + padding.top + padding.bottom

    # Apply min/max constraints
    min_width = deref_dimension_to_pixels(view.attributes.get("android:minWidth"), ctx, 0)
    min_height = deref_dimension_to_pixels(view.attributes.get("android:minHeight"), ctx, 0)
    max_width = deref_dimension_to_pixels(
        view.attributes.get("android:maxWidth"), ctx,
        width_spec.size if width_spec.mode != MeasureSpecMode.UNSPECIFIED else desired_width
    )
    max_height = deref_dimension_to_pixels(
        view.attributes.get("android:maxHeight"), ctx,
        height_spec.size if height_spec.mode != MeasureSpecMode.UNSPECIFIED else desired_height
    )

    desired_width = max(min_width, min(max_width, desired_width))
    desired_height = max(min_height, min(max_height, desired_height))

    # Resolve against MeasureSpec
    view.width = constrain_to_spec(desired_width, width_spec)
    view.height = constrain_to_spec(desired_height, height_spec)


def draw_frame_layout(
    view: View,
    canvas: Image.Image,
    ctx: RenderContext,
    draw_child: Callable[[View, Image.Image, RenderContext], None],
) -> None:
    """
    Draw a FrameLayout to the canvas.

    FrameLayout stacks all children on top of each other. In practice,
    FrameLayouts with multiple children are almost always tab/view-switcher
    containers where only one child is visible at a time (controlled by Java
    at runtime). Since we render statically, we draw only the first visible
    child as a reasonable approximation.
    """
    from views.android.view import draw_background

    if view.width <= 0 or view.height <= 0:
        return

    draw_background(view, canvas, ctx)

    # Draw only the first visible child (static approximation of tab switching)
    for child in view.children:
        if child.attributes.get("android:visibility") not in ("gone", "invisible"):
            draw_child(child, canvas, ctx)
            break
