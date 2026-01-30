from models import LayoutChildCallback, RenderContext, View
from registry import Registry


def layout(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    registry: Registry
) -> None:
    """
    Layout a view and set its x/y position.

    This is the second pass of Android's three-pass layout system:
    1. Measure: Calculate width/height (already done)
    2. Layout: Calculate x/y positions (this function)
    3. Draw: Render to canvas (not yet implemented)

    Args:
        view: The view to layout (must already have width/height set from measure pass)
        parent_x: Parent's x coordinate
        parent_y: Parent's y coordinate
        parent_width: Parent's width (for positioning within)
        parent_height: Parent's height (for positioning within)
        ctx: Rendering context with resources and configuration
        registry: Unified view registry
    """
    # Check visibility - gone views don't participate in layout
    visibility = view.attributes.get("android:visibility", "visible")
    if visibility == "gone":
        view.x = 0
        view.y = 0
        return

    # Look up layout function for this view type
    entry = registry.get(view.tag)

    if entry is not None:
        layout_func = entry.layout
    else:
        # Fall back to generic View layout for unknown view types
        layout_func = None
        fallback = registry.get("View")
        if fallback:
            layout_func = fallback.layout

        if layout_func is None:
            raise NotImplementedError(f"No layout function registered for view type '{view.tag}'")

    # Create a closure that captures the registry for recursive layout
    def layout_child(
        child: View,
        child_parent_x: int,
        child_parent_y: int,
        child_parent_width: int,
        child_parent_height: int,
        child_ctx: RenderContext
    ) -> None:
        layout(child, child_parent_x, child_parent_y, child_parent_width, child_parent_height, child_ctx, registry)

    layout_func(view, parent_x, parent_y, parent_width, parent_height, ctx, layout_child)
