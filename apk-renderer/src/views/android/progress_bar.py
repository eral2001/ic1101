from models import LayoutChildCallback, MeasureChildCallback, MeasureSpec, MeasureSpecMode, RenderContext, View
from resources import (
    deref_bool,
    deref_dimension_to_pixels,
    get_drawable_size,
    get_padding,
)
from measure_spec import constrain_to_spec


# TODO: These defaults should come from the theme's progressBarStyle
# From Android 4.2.2 ProgressBar.initProgressBar():
DEFAULT_MIN_WIDTH = 24
DEFAULT_MAX_WIDTH = 48
DEFAULT_MIN_HEIGHT = 24
DEFAULT_MAX_HEIGHT = 48


def layout_progress_bar(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """Layout a ProgressBar (leaf node)."""
    view.x = parent_x
    view.y = parent_y


def measure_progress_bar(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure a ProgressBar.

    ProgressBar sizes to its drawable's intrinsic size (progressDrawable or
    indeterminateDrawable depending on indeterminate attribute), clamped
    between min/max width/height constraints.

    Horizontal progress bars typically only constrain height (allowing width
    to stretch), while circular/spinner progress bars have fixed dimensions.
    """

    # Determine which drawable to use based on indeterminate attribute
    # Default is indeterminate=false for horizontal, true for circular (from style)
    indeterminate = deref_bool(view.attributes.get("android:indeterminate"), ctx)

    # Select the appropriate drawable
    if indeterminate:
        drawable_attr = view.attributes.get("android:indeterminateDrawable")
    else:
        drawable_attr = view.attributes.get("android:progressDrawable")

    # Get drawable's intrinsic dimensions
    intrinsic_width = 0
    intrinsic_height = 0
    if drawable_attr:
        intrinsic_width, intrinsic_height = get_drawable_size(drawable_attr, ctx)

    # Get min/max constraints
    # TODO: These should fall back to theme's progressBarStyle defaults
    min_width = deref_dimension_to_pixels(
        view.attributes.get("android:minWidth"), ctx, DEFAULT_MIN_WIDTH
    )
    max_width = deref_dimension_to_pixels(
        view.attributes.get("android:maxWidth"), ctx, DEFAULT_MAX_WIDTH
    )
    min_height = deref_dimension_to_pixels(
        view.attributes.get("android:minHeight"), ctx, DEFAULT_MIN_HEIGHT
    )
    max_height = deref_dimension_to_pixels(
        view.attributes.get("android:maxHeight"), ctx, DEFAULT_MAX_HEIGHT
    )

    # Clamp drawable dimensions between min/max
    # From Android 4.2.2 ProgressBar.onMeasure():
    # dw = Math.max(mMinWidth, Math.min(mMaxWidth, d.getIntrinsicWidth()))
    desired_width = max(min_width, min(max_width, intrinsic_width))
    desired_height = max(min_height, min(max_height, intrinsic_height))

    # Add padding
    padding = get_padding(view.attributes, ctx)
    desired_width += padding.left + padding.right
    desired_height += padding.top + padding.bottom

    # Resolve against MeasureSpec
    view.width = constrain_to_spec(desired_width, width_spec)
    view.height = constrain_to_spec(desired_height, height_spec)
