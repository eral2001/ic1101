"""
Drawing/rendering orchestration for Android views.

This module provides the third pass of Android's layout system:
1. Measure: Calculate width/height (measurer.py)
2. Layout: Calculate x/y positions (layouter.py)
3. Draw: Render to canvas (this module)
"""

from models import RenderContext, View
from typing import Callable, TYPE_CHECKING
from PIL import Image

if TYPE_CHECKING:
    from registry import Registry

# Type aliases for drawing function signatures
DrawChildCallback = Callable[['View', 'Image.Image', 'RenderContext'], None]
ViewDrawFunc = Callable[['View', 'Image.Image', 'RenderContext', DrawChildCallback], None]


def draw(
    view: View,
    canvas: Image.Image,
    ctx: RenderContext,
    registry: 'Registry'
) -> None:
    """
    Draw a view and its children to a canvas.

    This is the third pass of Android's layout system. Unlike measure/layout
    which use callbacks, drawing uses direct recursion since we need to draw
    in z-order (parent first, then children on top).

    Args:
        view: The view to draw (must already be measured and laid out)
        canvas: PIL Image to draw onto
        ctx: Rendering context with resources and configuration
        registry: Unified view registry
    """
    # Skip invisible views
    visibility = view.attributes.get("android:visibility", "visible")
    if visibility == "gone" or visibility == "invisible":
        return

    # Look up draw function for this view type
    entry = registry.get(view.tag)

    if entry is not None:
        draw_func = entry.draw
    else:
        # Try to find a fallback for custom views
        draw_func = None
        if "ImageView" in view.tag:
            fallback = registry.get("ImageView")
            if fallback:
                draw_func = fallback.draw
        elif "TextView" in view.tag or "Button" in view.tag:
            fallback = registry.get("TextView")
            if fallback:
                draw_func = fallback.draw
        else:
            fallback = registry.get("View")
            if fallback:
                draw_func = fallback.draw

        if draw_func is None:
            raise NotImplementedError(f"No draw function registered for view type '{view.tag}'")

    # Create a closure that captures the registry for recursive drawing
    def draw_child(child: View, child_canvas: Image.Image, child_ctx: RenderContext) -> None:
        draw(child, child_canvas, child_ctx, registry)

    # Draw this view
    draw_func(view, canvas, ctx, draw_child)
