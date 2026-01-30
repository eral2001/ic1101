from models import LayoutChildCallback, MeasureChildCallback, MeasureSpec, MeasureSpecMode, RenderContext, View
from resources import (
    deref_bool,
    deref_dimension_to_pixels,
    get_drawable_size,
    get_padding,
)
from measure_spec import constrain_to_spec


# TODO: These defaults should come from the theme's ratingBarStyle
# From Android 4.2.2 styles.xml:
# Widget.RatingBar (interactive): minHeight=57dip, maxHeight=57dip
# Widget.RatingBar.Indicator: minHeight=38dip, maxHeight=38dip
# Widget.RatingBar.Small: minHeight=14dip, maxHeight=14dip
DEFAULT_MIN_HEIGHT_INTERACTIVE = 57
DEFAULT_MAX_HEIGHT_INTERACTIVE = 57
DEFAULT_MIN_HEIGHT_INDICATOR = 38
DEFAULT_MAX_HEIGHT_INDICATOR = 38

# Default number of stars
DEFAULT_NUM_STARS = 5


def layout_rating_bar(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """Layout a RatingBar (leaf node)."""
    view.x = parent_x
    view.y = parent_y


def measure_rating_bar(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure a RatingBar.

    RatingBar is a specialized ProgressBar that displays a star rating.
    Width is calculated as: single_star_width × numStars
    Height comes from the style's min/max height constraints (57dip interactive, 38dip indicator).

    The measurement follows Android 4.2.2 RatingBar.onMeasure():
    1. Call super.onMeasure() (ProgressBar logic) for height
    2. Override width with: mSampleTile.getWidth() * mNumStars
    """

    # Get numStars attribute (default 5)
    num_stars_attr = view.attributes.get("android:numStars")
    if num_stars_attr:
        try:
            num_stars = int(num_stars_attr)
        except (ValueError, TypeError):
            num_stars = DEFAULT_NUM_STARS
    else:
        num_stars = DEFAULT_NUM_STARS

    # Determine if this is an indicator (affects default height)
    is_indicator = deref_bool(view.attributes.get("android:isIndicator"), ctx)

    # Get the progress drawable (provides intrinsic dimensions)
    drawable_attr = view.attributes.get("android:progressDrawable")
    intrinsic_width = 0
    intrinsic_height = 0
    if drawable_attr:
        intrinsic_width, intrinsic_height = get_drawable_size(drawable_attr, ctx)

    # Calculate per-star width from drawable
    # The drawable's intrinsic width typically represents the full width for default stars
    # We divide by DEFAULT_NUM_STARS to get per-star width, then multiply by actual numStars
    per_star_width = 0
    if intrinsic_width > 0:
        # Assume drawable is designed for 5 stars, scale proportionally
        per_star_width = intrinsic_width // DEFAULT_NUM_STARS
    else:
        # If no intrinsic width, estimate based on height (stars are roughly square)
        # Use the min height as a guide for star size
        if is_indicator:
            per_star_width = DEFAULT_MIN_HEIGHT_INDICATOR
        else:
            per_star_width = DEFAULT_MIN_HEIGHT_INTERACTIVE

    # Calculate desired width: per_star_width × numStars
    desired_width = per_star_width * num_stars

    # Get height constraints from style
    # TODO: These should come from theme's ratingBarStyle / ratingBarStyleIndicator
    if is_indicator:
        default_min_height = DEFAULT_MIN_HEIGHT_INDICATOR
        default_max_height = DEFAULT_MAX_HEIGHT_INDICATOR
    else:
        default_min_height = DEFAULT_MIN_HEIGHT_INTERACTIVE
        default_max_height = DEFAULT_MAX_HEIGHT_INTERACTIVE

    min_height = deref_dimension_to_pixels(
        view.attributes.get("android:minHeight"), ctx, default_min_height
    )
    max_height = deref_dimension_to_pixels(
        view.attributes.get("android:maxHeight"), ctx, default_max_height
    )

    # Use drawable's intrinsic height if available, otherwise use default
    if intrinsic_height > 0:
        desired_height = max(min_height, min(max_height, intrinsic_height))
    else:
        desired_height = default_min_height

    # Add padding
    padding = get_padding(view.attributes, ctx)
    desired_width += padding.left + padding.right
    desired_height += padding.top + padding.bottom

    # Resolve against MeasureSpec
    view.width = constrain_to_spec(desired_width, width_spec)
    view.height = constrain_to_spec(desired_height, height_spec)
