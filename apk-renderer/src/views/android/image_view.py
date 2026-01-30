from models import LayoutChildCallback, MeasureChildCallback, MeasureSpec, MeasureSpecMode, RenderContext, View
from resources import (
    deref_dimension_to_pixels,
    get_drawable_size,
    get_padding,
)
from measure_spec import constrain_to_spec
from drawable_loader import get_drawable_path, load_drawable_image
from views.android.view import draw_background
from ninepatch import is_ninepatch, render_ninepatch
from PIL import Image
from typing import Callable


def layout_image_view(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """Layout an ImageView (leaf node)."""
    view.x = parent_x
    view.y = parent_y


def measure_image_view(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure an ImageView.

    ImageView sizes to its drawable's intrinsic size, respecting
    adjustViewBounds for aspect ratio preservation.
    """

    # Get intrinsic size from drawable
    intrinsic_width = 0
    intrinsic_height = 0
    src = view.attributes.get("android:src")
    if src:
        intrinsic_width, intrinsic_height = get_drawable_size(src, ctx)

    padding = get_padding(view.attributes, ctx)

    # Desired size is intrinsic + padding
    desired_width = intrinsic_width + padding.left + padding.right
    desired_height = intrinsic_height + padding.top + padding.bottom

    # adjustViewBounds: scale to maintain aspect ratio
    adjust_view_bounds = view.attributes.get("android:adjustViewBounds") == "true"
    
    if adjust_view_bounds and intrinsic_width > 0 and intrinsic_height > 0:
        aspect_ratio = intrinsic_width / intrinsic_height
        
        # If width is constrained (EXACTLY) but height is not, derive height
        if width_spec.mode == MeasureSpecMode.EXACTLY and height_spec.mode != MeasureSpecMode.EXACTLY:
            content_width = width_spec.size - padding.left - padding.right
            content_height = int(content_width / aspect_ratio)
            desired_height = content_height + padding.top + padding.bottom
        
        # If height is constrained (EXACTLY) but width is not, derive width
        elif height_spec.mode == MeasureSpecMode.EXACTLY and width_spec.mode != MeasureSpecMode.EXACTLY:
            content_height = height_spec.size - padding.top - padding.bottom
            content_width = int(content_height * aspect_ratio)
            desired_width = content_width + padding.left + padding.right

    # Apply min/max constraints
    min_width = deref_dimension_to_pixels(view.attributes.get("android:minWidth"), ctx, 0)
    min_height = deref_dimension_to_pixels(view.attributes.get("android:minHeight"), ctx, 0)
    max_width = deref_dimension_to_pixels(view.attributes.get("android:maxWidth"), ctx, width_spec.size if width_spec.mode != MeasureSpecMode.UNSPECIFIED else desired_width)
    max_height = deref_dimension_to_pixels(view.attributes.get("android:maxHeight"), ctx, height_spec.size if height_spec.mode != MeasureSpecMode.UNSPECIFIED else desired_height)

    desired_width = max(min_width, min(max_width, desired_width))
    desired_height = max(min_height, min(max_height, desired_height))

    # Resolve against MeasureSpec
    view.width = constrain_to_spec(desired_width, width_spec)
    view.height = constrain_to_spec(desired_height, height_spec)


def draw_image_view(
    view: View,
    canvas: Image.Image,
    ctx: RenderContext,
    draw_child: Callable[[View, Image.Image, RenderContext], None],
) -> None:
    """
    Draw an ImageView to the canvas.

    This renders the android:src image with proper scaling based on scaleType.
    """
    # Skip if view has no size
    if view.width <= 0 or view.height <= 0:
        return

    # Draw background first
    draw_background(view, canvas, ctx)

    # Get the source image
    src = view.attributes.get("android:src")
    if not src:
        return

    # Resolve theme attribute if needed
    if src.startswith("?"):
        # This is a theme attribute reference - resolve it first
        attr_name = src[1:]  # Remove the '?' prefix
        resolved_src = ctx.resolve_theme_attr(attr_name)
        if not resolved_src:
            return
        src = resolved_src

    # Load the drawable
    drawable_path = get_drawable_path(src, ctx.app_drawables, ctx.framework_drawables)
    if not drawable_path:
        return

    img = load_drawable_image(drawable_path)
    if not img:
        return

    # Skip if view has invalid dimensions (0 or negative)
    if view.width <= 0 or view.height <= 0:
        return

    # Handle 9-patch images specially (ignore scaleType)
    if is_ninepatch(drawable_path):
        scaled_img = render_ninepatch(img, view.width, view.height)
    else:
        # Get scaleType (default is fitCenter)
        scale_type = view.attributes.get("android:scaleType", "fitCenter")

        # Apply scaleType transformations
        scaled_img = apply_scale_type(img, view.width, view.height, scale_type)

    # Paste the image onto the canvas
    if scaled_img:
        # Calculate position (some scaleTypes may result in smaller images)
        paste_x = view.x + (view.width - scaled_img.width) // 2
        paste_y = view.y + (view.height - scaled_img.height) // 2

        canvas.paste(scaled_img, (paste_x, paste_y), scaled_img)


def apply_scale_type(
    img: Image.Image,
    target_width: int,
    target_height: int,
    scale_type: str
) -> Image.Image:
    """
    Apply Android scaleType transformation to an image.

    Args:
        img: Source image
        target_width: Target view width
        target_height: Target view height
        scale_type: Android scaleType value

    Returns:
        Transformed image
    """
    # Validate dimensions
    if target_width <= 0 or target_height <= 0:
        return img

    src_width, src_height = img.size
    if src_width <= 0 or src_height <= 0:
        return img

    if scale_type == "center":
        # Center the image without scaling
        # If image is larger than view, crop it
        # If image is smaller, leave it as-is (will be centered during paste)
        if src_width > target_width or src_height > target_height:
            # Crop to center
            left = (src_width - target_width) // 2
            top = (src_height - target_height) // 2
            right = left + target_width
            bottom = top + target_height
            return img.crop((left, top, right, bottom))
        return img

    elif scale_type == "centerCrop":
        # Scale uniformly to fill the entire view, cropping excess
        src_aspect = src_width / src_height
        target_aspect = target_width / target_height

        if src_aspect > target_aspect:
            # Image is wider - fit to height, crop width
            scale = target_height / src_height
            scaled_width = max(1, int(src_width * scale))
            scaled = img.resize((scaled_width, target_height), Image.Resampling.LANCZOS)
            # Crop center
            left = (scaled_width - target_width) // 2
            return scaled.crop((left, 0, left + target_width, target_height))
        else:
            # Image is taller - fit to width, crop height
            scale = target_width / src_width
            scaled_height = max(1, int(src_height * scale))
            scaled = img.resize((target_width, scaled_height), Image.Resampling.LANCZOS)
            # Crop center
            top = (scaled_height - target_height) // 2
            return scaled.crop((0, top, target_width, top + target_height))

    elif scale_type == "centerInside":
        # Scale down if needed to fit inside view, but don't scale up
        if src_width <= target_width and src_height <= target_height:
            # Image fits, don't scale
            return img
        # Fall through to fitCenter logic

    # fitCenter, fitStart, fitEnd, fitXY all scale the image
    if scale_type == "fitXY":
        # Stretch to fill exactly
        return img.resize((target_width, target_height), Image.Resampling.LANCZOS)

    # fitCenter (default), fitStart, fitEnd
    # Scale uniformly to fit inside view
    src_aspect = src_width / src_height
    target_aspect = target_width / target_height

    if src_aspect > target_aspect:
        # Image is wider - fit to width
        scale = target_width / src_width
        scaled_width = target_width
        scaled_height = max(1, int(src_height * scale))
    else:
        # Image is taller - fit to height
        scale = target_height / src_height
        scaled_width = max(1, int(src_width * scale))
        scaled_height = target_height

    return img.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
