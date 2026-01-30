from models import DimensionMatchParent, LayoutChildCallback, MeasureChildCallback, MeasureSpec, MeasureSpecMode, RenderContext, View
from resources import (
    deref_bool,
    deref_dimension,
    deref_dimension_to_pixels,
    get_margins,
    get_padding,
)
from measure_spec import constrain_to_spec, get_child_measure_spec


def layout_scroll_view(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """
    Layout a ScrollView and its single child.

    The child is positioned at the top-left of the content area (after padding).
    The child may be taller than the ScrollView (scrollable), but we position
    it at (0, 0) within the content area.
    """
    # Set our own position
    view.x = parent_x
    view.y = parent_y

    # Get padding
    padding = get_padding(view.attributes, ctx)

    # Layout the single child (if any) at content area origin
    for child in view.children:
        # Skip gone children
        if child.attributes.get("android:visibility") == "gone":
            continue

        # Position child at top-left of content area
        child_x = view.x + padding.left
        child_y = view.y + padding.top

        # Layout the child
        layout_child(child, child_x, child_y, view.width - padding.left - padding.right, view.height - padding.top - padding.bottom, ctx)

        # ScrollView should have only one child, break after first
        break


def measure_scroll_view(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure a ScrollView and its single child.

    ScrollView allows vertical scrolling by measuring its child with
    UNSPECIFIED height, letting the child be as tall as needed.
    The ScrollView itself sizes to its constraints (the viewport),
    which can be smaller than the child's height (the scrollable content).
    """

    padding = get_padding(view.attributes, ctx)

    # ScrollView should have exactly one child
    if len(view.children) == 0:
        # No child, just size to padding
        view.width = constrain_to_spec(padding.left + padding.right, width_spec)
        view.height = constrain_to_spec(padding.top + padding.bottom, height_spec)
        return

    if len(view.children) > 1:
        # Android allows this but only the first child is scrollable
        print("Warning: ScrollView should have only one child")

    child = view.children[0]

    # Skip gone children
    if child.attributes.get("android:visibility") == "gone":
        view.width = constrain_to_spec(padding.left + padding.right, width_spec)
        view.height = constrain_to_spec(padding.top + padding.bottom, height_spec)
        return

    # Get child's layout params
    margins = get_margins(child.attributes, ctx)
    child_width_dim = deref_dimension(child.attributes.get("android:layout_width"), ctx)
    child_height_dim = deref_dimension(child.attributes.get("android:layout_height"), ctx)

    # Width: pass through parent constraints (minus padding/margins)
    child_width_spec = get_child_measure_spec(
        width_spec,
        padding.left + padding.right + margins.left + margins.right,
        child_width_dim
    )

    # Height: measure with UNSPECIFIED to let child be as tall as it wants
    # Exception: if child explicitly wants MATCH_PARENT, give it parent's height constraint
    if isinstance(child_height_dim, DimensionMatchParent):
        # Child wants to match parent - give it parent's height constraint
        child_height_spec = get_child_measure_spec(
            height_spec,
            padding.top + padding.bottom + margins.top + margins.bottom,
            child_height_dim
        )
    else:
        # Let child measure naturally (WRAP_CONTENT or fixed size)
        child_height_spec = MeasureSpec(MeasureSpecMode.UNSPECIFIED, 0)

    # Measure the child
    measure_child(child, child_width_spec, child_height_spec, ctx)

    # Calculate ScrollView's desired size
    # Width includes child + margins + padding
    desired_width = child.width + margins.left + margins.right + padding.left + padding.right

    # Height includes child + margins + padding
    desired_height = child.height + margins.top + margins.bottom + padding.top + padding.bottom

    # Handle fillViewport attribute
    # If true and child is smaller than available space, stretch child to fill
    fill_viewport = deref_bool(view.attributes.get("android:fillViewport"), ctx)
    if fill_viewport and height_spec.mode != MeasureSpecMode.UNSPECIFIED:
        # Ensure child is at least as tall as the viewport
        min_content_height = height_spec.size - padding.top - padding.bottom
        if child.height < min_content_height:
            # Re-measure child with EXACTLY to fill viewport
            child_height_spec_fill = MeasureSpec(MeasureSpecMode.EXACTLY, min_content_height - margins.top - margins.bottom)
            measure_child(child, child_width_spec, child_height_spec_fill, ctx)
            desired_height = child.height + margins.top + margins.bottom + padding.top + padding.bottom

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
