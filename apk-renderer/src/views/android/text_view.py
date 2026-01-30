from models import LayoutChildCallback, MeasureChildCallback, MeasureSpec, MeasureSpecMode, RenderContext, View
from resources import (
    deref_bool,
    deref_color,
    deref_dimension_to_offset,
    deref_dimension_to_pixels,
    deref_float,
    deref_string,
    get_drawable_size,
    get_padding,
    get_style_chain,
    get_text_size,
)
from measure_spec import constrain_to_spec
from text_utils import calculate_text_bounds
from views.android.view import draw_background
from gravity import parse_gravity, Gravity
from PIL import Image, ImageDraw, ImageFont
from typing import Callable


# All attributes that can come from textAppearance.
# Values are the hardcoded defaults from TextView.java, or None if no default.
# TODO: Verify hardcoded defaults in TextView.java.
# TODO: Verify that this list of attributes is comprehensive.
TEXTVIEW_DEFAULTS: dict[str, str | int | None] = {
    "textSize": 15,         # Set explicitly in Java
    "textStyle": "normal",  # Set explicitly in Java
    "textAllCaps": "false", # Set explicitly in Java
    "typeface": None,
    "fontFamily": None,
    "textColor": None,
    "textColorHint": None,
    "textColorLink": None,
    "letterSpacing": None,
    "shadowColor": None,
    "shadowDx": None,
    "shadowDy": None,
    "shadowRadius": None,
}


def get_text_attributes(view: View, ctx: RenderContext) -> dict[str, str | int | None]:
    """
    Get text attributes for a TextView with proper precedence:

    1. Explicit attributes on view         (highest priority)
    2. textAppearance style chain
    3. View's style attribute
    4. Theme's textViewStyle chain
    5. Hardcoded TextView.java defaults    (lowest priority)

    Returns dict with all textAppearance-related keys.
    """

    # Priority 5: Hardcoded defaults
    resolved: dict[str, str | int | None] = dict(TEXTVIEW_DEFAULTS)

    # Priority 4: Theme's default textViewStyle (if defined)
    text_view_style_ref = ctx.resolve_theme_attr("textViewStyle")
    if text_view_style_ref is not None:
        style_attrs = get_style_chain(text_view_style_ref, ctx)
        for key in resolved:
            if key in style_attrs:
                resolved[key] = style_attrs[key]

    # Priority 3: View's style attribute (if specified)
    style_ref = view.attributes.get("style")
    if style_ref is not None:
        style_attrs = get_style_chain(style_ref, ctx)
        for key in resolved:
            if key in style_attrs:
                resolved[key] = style_attrs[key]

    # Priority 2: textAppearance (if specified on view)
    text_appearance_ref = view.attributes.get("android:textAppearance")
    if text_appearance_ref is not None:
        ta_attrs = get_style_chain(text_appearance_ref, ctx)
        for key in resolved:
            if key in ta_attrs:
                resolved[key] = ta_attrs[key]

    # Priority 1: Explicit attributes on view (highest priority)
    for key in resolved:
        explicit = view.attributes.get(f"android:{key}")
        if explicit is not None:
            resolved[key] = explicit

    return resolved


def layout_text_view(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """Layout a TextView (leaf node)."""
    view.x = parent_x
    view.y = parent_y


# TODO: Missing proper handling of android:hint
# TODO: Android by default adds extra space above/below for ascenders/descenders. Pillow's getbbox() may not match this exactly.
# TODO: Should support ems
# TODO: Should support ellipsize
# TODO: Should support tracking Baseline
# TODO: If both text and hint are empty, Android still reserves space based on font metrics (one line height). We'd return (0, 0).
# TODO: drawableStart/drawableEnd — RTL-aware versions of drawableLeft/drawableRight. We only handle the LTR variants.
def measure_text_view(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure a TextView.

    TextView sizes to fit its text content, respecting compound drawables,
    textAppearance styling, and line spacing settings.
    """

    # Determine if we need to compute intrinsic size
    # (needed for AT_MOST and UNSPECIFIED modes)
    needs_intrinsic = (
        width_spec.mode != MeasureSpecMode.EXACTLY or
        height_spec.mode != MeasureSpecMode.EXACTLY
    )

    intrinsic_width = 0
    intrinsic_height = 0

    if needs_intrinsic:
        # Resolve text appearance attributes (handles textAppearance, theme, defaults)
        text_attrs = get_text_attributes(view, ctx)
        
        # Text content (not part of textAppearance, always from view)
        text = deref_string(view.attributes.get("android:text"), ctx)
        
        # Text styling from resolved attributes
        typeface = text_attrs.get("typeface")
        text_style = text_attrs.get("textStyle")
        text_size = text_attrs.get("textSize")
        text_size_parsed = get_text_size(text_size, ctx)
        letter_spacing = text_attrs.get("letterSpacing")
        letter_spacing_parsed = deref_float(letter_spacing, ctx)

        # Line spacing (not part of textAppearance, always from view)
        line_spacing_extra = view.attributes.get("android:lineSpacingExtra")
        line_spacing_extra_parsed = deref_dimension_to_pixels(line_spacing_extra, ctx, 0) if line_spacing_extra else None
        line_spacing_multiplier = view.attributes.get("android:lineSpacingMultiplier")
        line_spacing_multiplier_parsed = deref_float(line_spacing_multiplier, ctx) or 1.0
        single_line = view.attributes.get("android:singleLine")
        single_line_parsed = deref_bool(single_line, ctx)

        # TODO: maxLines attribute affects height calculation
        max_lines = view.attributes.get("android:maxLines")
        if max_lines:
            print(f"Warning: maxLines={max_lines} ignored (not implemented)")
        
        # TODO: minLines attribute affects height calculation
        min_lines = view.attributes.get("android:minLines")
        if min_lines:
            print(f"Warning: minLines={min_lines} ignored (not implemented)")
        
        # TODO: lines attribute affects height calculation
        lines = view.attributes.get("android:lines")
        if lines:
            print(f"Warning: lines={lines} ignored (not implemented)")
        
        # Determine max width for text wrapping
        # Only constrain when spec is bounded and not single line
        text_max_width: int | None = None
        if not single_line_parsed and width_spec.mode != MeasureSpecMode.UNSPECIFIED:
            text_max_width = width_spec.size
        
        # Measure text
        # TODO: This is an approximate measurement as we're rendering text on a different platform to get its size
        text_width, text_height = calculate_text_bounds(
            text=text,
            typeface=typeface,
            text_style=text_style,
            text_size=text_size_parsed,
            font_config=ctx.font_config,
            letter_spacing=letter_spacing_parsed,
            line_spacing_extra=line_spacing_extra_parsed,
            line_spacing_multiplier=line_spacing_multiplier_parsed,
            max_width=text_max_width,
            use_single_line=single_line_parsed,
        )

        # Get compound drawables (not part of textAppearance, always from view)
        drawable_left = view.attributes.get("android:drawableLeft")
        drawable_right = view.attributes.get("android:drawableRight")
        drawable_top = view.attributes.get("android:drawableTop")
        drawable_bottom = view.attributes.get("android:drawableBottom")
        drawable_padding = view.attributes.get("android:drawablePadding")
        drawable_padding_parsed = deref_dimension_to_offset(drawable_padding, ctx, 0)
        
        drawable_left_w, drawable_left_h = get_drawable_size(drawable_left, ctx) if drawable_left else (0, 0)
        drawable_right_w, drawable_right_h = get_drawable_size(drawable_right, ctx) if drawable_right else (0, 0)
        drawable_top_w, drawable_top_h = get_drawable_size(drawable_top, ctx) if drawable_top else (0, 0)
        drawable_bottom_w, drawable_bottom_h = get_drawable_size(drawable_bottom, ctx) if drawable_bottom else (0, 0)
        
        # Calculate intrinsic width
        text_row_width = text_width
        if drawable_left_w > 0:
            text_row_width += drawable_left_w + drawable_padding_parsed
        if drawable_right_w > 0:
            text_row_width += drawable_right_w + drawable_padding_parsed
        
        intrinsic_width = max(text_row_width, drawable_top_w, drawable_bottom_w)

        # Calculate intrinsic height
        text_row_height = max(text_height, drawable_left_h, drawable_right_h)
        intrinsic_height = text_row_height
        if drawable_top_h > 0:
            intrinsic_height += drawable_top_h + drawable_padding_parsed
        if drawable_bottom_h > 0:
            intrinsic_height += drawable_bottom_h + drawable_padding_parsed

    padding = get_padding(view.attributes, ctx)

    # Desired size is intrinsic + padding
    desired_width = intrinsic_width + padding.left + padding.right
    desired_height = intrinsic_height + padding.top + padding.bottom

    # Apply min/max constraints
    min_width = deref_dimension_to_pixels(view.attributes.get("android:minWidth"), ctx, 0)
    min_height = deref_dimension_to_pixels(view.attributes.get("android:minHeight"), ctx, 0)
    max_width_default = width_spec.size if width_spec.mode != MeasureSpecMode.UNSPECIFIED else desired_width
    max_height_default = height_spec.size if height_spec.mode != MeasureSpecMode.UNSPECIFIED else desired_height
    max_width = deref_dimension_to_pixels(view.attributes.get("android:maxWidth"), ctx, max_width_default)
    max_height = deref_dimension_to_pixels(view.attributes.get("android:maxHeight"), ctx, max_height_default)

    desired_width = max(min_width, min(max_width, desired_width))
    desired_height = max(min_height, min(max_height, desired_height))

    # Resolve against MeasureSpec
    view.width = constrain_to_spec(desired_width, width_spec)
    view.height = constrain_to_spec(desired_height, height_spec)


def _draw_text_with_size(
    view: View,
    canvas: Image.Image,
    ctx: RenderContext,
    text: str,
    text_attrs: dict[str, str | int | None],
    text_size_px: int,
) -> None:
    """
    Core text rendering logic shared by draw_text_view and draw_auto_adjust_text_view.

    Renders the given text at text_size_px, positioned according to gravity and padding.
    """
    # Get text color (default to black if not specified)
    text_color = deref_color(text_attrs.get("textColor"), ctx)
    if not text_color:
        text_color = (0, 0, 0, 255)  # Black

    # Resolve font using the same path as the measure pass
    typeface = text_attrs.get("typeface")
    text_style = text_attrs.get("textStyle")
    font_path = ctx.font_config.resolve_font(typeface, text_style)
    try:
        font = ImageFont.truetype(str(font_path), text_size_px)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # Get padding
    padding = get_padding(view.attributes, ctx)

    # Get gravity from attribute or style chain
    gravity_str = view.attributes.get("android:gravity")
    if gravity_str is None:
        # Check if gravity is defined in the style
        style_ref = view.attributes.get("style")
        if style_ref:
            style_attrs = get_style_chain(style_ref, ctx)
            gravity_str = style_attrs.get("gravity")

    if gravity_str is None:
        # Default to center for Button, top|left otherwise
        if view.tag == "Button":
            gravity_str = "center"
        else:
            gravity_str = "top|left"

    gravity = parse_gravity(gravity_str)

    # Calculate available space for text (view size minus padding)
    content_width = view.width - padding.left - padding.right
    content_height = view.height - padding.top - padding.bottom

    # Get text bounding box
    img_draw = ImageDraw.Draw(canvas, "RGBA")
    bbox = img_draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    # PIL's textbbox returns (left, top, right, bottom) with offsets
    # We need to account for these offsets when positioning
    bbox_offset_x = bbox[0]
    bbox_offset_y = bbox[1]

    # Calculate text position based on gravity
    # Horizontal alignment
    if Gravity.CENTER_HORIZONTAL in gravity or Gravity.CENTER in gravity:
        text_x = view.x + padding.left + (content_width - text_width) // 2
    elif Gravity.RIGHT in gravity or Gravity.END in gravity:
        text_x = view.x + padding.left + content_width - text_width
    else:  # LEFT or default
        text_x = view.x + padding.left

    # Vertical alignment
    if Gravity.CENTER_VERTICAL in gravity or Gravity.CENTER in gravity:
        text_y = view.y + padding.top + (content_height - text_height) // 2
    elif Gravity.BOTTOM in gravity:
        text_y = view.y + padding.top + content_height - text_height
    else:  # TOP or default
        text_y = view.y + padding.top

    # Clamp to content bounds so overflowing text doesn't bleed leftward/upward
    # (Android clips drawing to view bounds; we approximate by clamping position)
    text_x = max(text_x, view.x + padding.left)
    text_y = max(text_y, view.y + padding.top)

    # Adjust for PIL's bounding box offsets
    text_x -= bbox_offset_x
    text_y -= bbox_offset_y

    # Draw text
    img_draw.text((text_x, text_y), text, fill=text_color, font=font)


def draw_text_view(
    view: View,
    canvas: Image.Image,
    ctx: RenderContext,
    draw_child: Callable[[View, Image.Image, RenderContext], None],
) -> None:
    """
    Draw a TextView to the canvas.

    This renders the background and text content.
    """
    # Skip if view has no size
    if view.width <= 0 or view.height <= 0:
        return

    # Draw background first
    draw_background(view, canvas, ctx)

    # Get text to draw
    text = deref_string(view.attributes.get("android:text"), ctx)
    if not text:
        return

    # Get text attributes and size
    text_attrs = get_text_attributes(view, ctx)
    text_size_px = get_text_size(text_attrs.get("textSize"), ctx)

    _draw_text_with_size(view, canvas, ctx, text, text_attrs, text_size_px)
