from models import LayoutChildCallback, MeasureChildCallback, MeasureSpec, RenderContext, View
from resources import deref_dimension_to_pixels, deref_color, deref_drawable_path
from measure_spec import constrain_to_spec
from PIL import Image, ImageDraw
from drawable_loader import get_drawable_path, load_drawable_image
from ninepatch import is_ninepatch, render_ninepatch
from drawable_xml_parser import get_selector_default_reference
from typing import Callable


def layout_view(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """
    Layout a generic View (set x, y coordinates).

    Generic Views are leaf nodes with no children, so they just
    accept their position from the parent.

    Args:
        view: The view to layout
        parent_x: X coordinate where this view should be positioned
        parent_y: Y coordinate where this view should be positioned
        parent_width: Parent container's width (for reference)
        parent_height: Parent container's height (for reference)
        ctx: Rendering context
        layout_child: Callback for laying out children (not used for leaf views)
    """
    # Leaf view - just accept the position from parent
    view.x = parent_x
    view.y = parent_y


def measure_view(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure a generic View.

    Generic View is a lightweight component that draws nothing and has no content.
    It participates in layout by taking up space according to its layout_width
    and layout_height. Often used as invisible spacers or dividers.
    """

    # Generic View has no intrinsic size - it sizes purely based on layout_width/height
    # If dimensions are 0 or unspecified, it collapses to 0
    desired_width = 0
    desired_height = 0

    # Check if explicit dimensions are set
    # View typically doesn't use wrap_content meaningfully since it has no content
    width_attr = view.attributes.get("android:layout_width")
    height_attr = view.attributes.get("android:layout_height")

    # If explicit pixel dimensions are specified, use them
    if width_attr and width_attr not in ("match_parent", "wrap_content"):
        desired_width = deref_dimension_to_pixels(width_attr, ctx, 0)

    if height_attr and height_attr not in ("match_parent", "wrap_content"):
        desired_height = deref_dimension_to_pixels(height_attr, ctx, 0)

    # Resolve against MeasureSpec
    # For match_parent or wrap_content, constrain_to_spec will handle it
    view.width = constrain_to_spec(desired_width, width_spec)
    view.height = constrain_to_spec(desired_height, height_spec)


def draw_view(
    view: View,
    canvas: Image.Image,
    ctx: RenderContext,
    draw_child: Callable[[View, Image.Image, RenderContext], None],
) -> None:
    """
    Draw a generic View to the canvas.

    This handles:
    1. Drawing background (color or drawable)
    2. Recursively drawing children

    Args:
        view: The view to draw
        canvas: PIL Image to draw onto
        ctx: Rendering context
        draw_child: Callback for drawing children
    """
    # Skip if view has no size
    if view.width <= 0 or view.height <= 0:
        return

    # Draw background
    draw_background(view, canvas, ctx)

    # Draw children (for container views)
    for child in view.children:
        draw_child(child, canvas, ctx)


def draw_background(view: View, canvas: Image.Image, ctx: RenderContext) -> None:
    """
    Draw the background for a view.

    Handles both solid colors and drawable images.
    """
    background = view.attributes.get("android:background")
    if not background:
        return

    # Check for theme attributes first and try to resolve as drawable
    # (to avoid "cannot parse color value" warnings for drawable references)
    if background.startswith("?"):
        drawable_path = deref_drawable_path(background, ctx)

        if drawable_path:
            # Check if it's an XML selector
            if drawable_path.suffix.lower() == '.xml':
                # Get the selector's default reference
                selector_ref = get_selector_default_reference(drawable_path)
                if selector_ref:
                    # Check if it's a color reference
                    if selector_ref.startswith("@color/") or selector_ref.startswith("@android:color/"):
                        color = deref_color(selector_ref, ctx)
                        if color:
                            # Draw solid color background from selector
                            draw = ImageDraw.Draw(canvas, "RGBA")
                            draw.rectangle(
                                [view.x, view.y, view.x + view.width - 1, view.y + view.height - 1],
                                fill=color
                            )
                            return
                    # If it's a drawable reference, resolve it
                    elif selector_ref.startswith("@drawable/") or selector_ref.startswith("@android:drawable/"):
                        # Resolve the drawable reference
                        final_drawable_path = get_drawable_path(selector_ref, ctx.app_drawables, ctx.framework_drawables)
                        if final_drawable_path:
                            bg_image = load_drawable_image(final_drawable_path)
                            if bg_image:
                                if is_ninepatch(final_drawable_path):
                                    bg_image = render_ninepatch(bg_image, view.width, view.height)
                                else:
                                    bg_image = bg_image.resize((view.width, view.height), Image.Resampling.LANCZOS)
                                canvas.paste(bg_image, (view.x, view.y), bg_image)
                                return
                return  # XML selector couldn't be resolved

            # Not an XML file, load directly
            bg_image = load_drawable_image(drawable_path)
            if bg_image:
                if is_ninepatch(drawable_path):
                    bg_image = render_ninepatch(bg_image, view.width, view.height)
                else:
                    bg_image = bg_image.resize((view.width, view.height), Image.Resampling.LANCZOS)
                canvas.paste(bg_image, (view.x, view.y), bg_image)
                return

        # If drawable resolution failed, try as color
        color = deref_color(background, ctx)
        if color:
            draw = ImageDraw.Draw(canvas, "RGBA")
            draw.rectangle(
                [view.x, view.y, view.x + view.width - 1, view.y + view.height - 1],
                fill=color
            )
        return

    # Check if it's a drawable reference first (to avoid warnings)
    if background.startswith("@drawable/") or background.startswith("@android:drawable/"):
        # Manually resolve the drawable to get the path (before get_drawable_path filters it)
        ref = background[1:]  # Strip @ prefix
        drawable_name = None
        if ref.startswith("android:drawable/"):
            drawable_name = ref[len("android:drawable/"):]
            raw_path = ctx.framework_drawables.get(drawable_name)
        elif ref.startswith("drawable/"):
            drawable_name = ref[len("drawable/"):]
            raw_path = ctx.app_drawables.get(drawable_name)
            if raw_path is None:
                raw_path = ctx.framework_drawables.get(drawable_name)
        else:
            raw_path = None

        # Check if it's an XML selector that might reference a color
        if raw_path and raw_path.suffix.lower() == '.xml':
            # Get the selector's default reference (could be @color or @drawable)
            selector_ref = get_selector_default_reference(raw_path)
            if selector_ref:
                # Check if it's a color reference
                if selector_ref.startswith("@color/") or selector_ref.startswith("@android:color/"):
                    color = deref_color(selector_ref, ctx)
                    if color:
                        # Draw solid color background from selector
                        draw = ImageDraw.Draw(canvas, "RGBA")
                        draw.rectangle(
                            [view.x, view.y, view.x + view.width - 1, view.y + view.height - 1],
                            fill=color
                        )
                        return
                # If it's a drawable reference, resolve it recursively
                elif selector_ref.startswith("@drawable/") or selector_ref.startswith("@android:drawable/"):
                    # Recursively handle the drawable reference
                    drawable_path = get_drawable_path(selector_ref, ctx.app_drawables, ctx.framework_drawables)
                    if drawable_path:
                        bg_image = load_drawable_image(drawable_path)
                        if bg_image:
                            if is_ninepatch(drawable_path):
                                bg_image = render_ninepatch(bg_image, view.width, view.height)
                            else:
                                bg_image = bg_image.resize((view.width, view.height), Image.Resampling.LANCZOS)
                            canvas.paste(bg_image, (view.x, view.y), bg_image)
                            return
            return  # XML selector couldn't be resolved

        # Use standard path resolution for non-XML drawables
        drawable_path = get_drawable_path(background, ctx.app_drawables, ctx.framework_drawables)
        if drawable_path:
            bg_image = load_drawable_image(drawable_path)
            if bg_image:
                # Handle 9-patch images specially
                if is_ninepatch(drawable_path):
                    bg_image = render_ninepatch(bg_image, view.width, view.height)
                else:
                    # Regular image - resize to fit view dimensions
                    bg_image = bg_image.resize((view.width, view.height), Image.Resampling.LANCZOS)

                # Paste onto canvas
                canvas.paste(bg_image, (view.x, view.y), bg_image)
                return
        # Drawable reference didn't resolve, skip it
        return

    # Try to parse as color (for hex colors, @color/ refs)
    color = deref_color(background, ctx)
    if color:
        # Draw solid color background
        draw = ImageDraw.Draw(canvas, "RGBA")
        draw.rectangle(
            [view.x, view.y, view.x + view.width - 1, view.y + view.height - 1],
            fill=color
        )

    # If we couldn't resolve the background, just skip it
