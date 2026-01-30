from models import MeasureChildCallback, MeasureSpec, MeasureSpecMode, RenderContext, View
from resources import deref_dimension_to_pixels, get_padding
from measure_spec import constrain_to_spec


def measure_list_view(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure a ListView.
    
    ListView is a view group that displays a scrollable list of items.
    Since items are added dynamically, we can't measure actual content.
    For wrap_content height, we use a reasonable default.
    """
    padding = get_padding(view.attributes, ctx)
    
    # For width, behave like a normal view
    desired_width = 0
    width_attr = view.attributes.get("android:layout_width")
    if width_attr and width_attr not in ("match_parent", "wrap_content", "fill_parent"):
        desired_width = deref_dimension_to_pixels(width_attr, ctx, 0)
    
    # For height, use a reasonable default when wrap_content
    # If height is constrained (AT_MOST or EXACTLY), use that
    # Otherwise, use a default list item height for visualization
    desired_height = 0
    height_attr = view.attributes.get("android:layout_height")
    
    if height_attr and height_attr not in ("match_parent", "wrap_content", "fill_parent"):
        desired_height = deref_dimension_to_pixels(height_attr, ctx, 0)
    elif height_spec.mode == MeasureSpecMode.UNSPECIFIED or (
        height_spec.mode == MeasureSpecMode.AT_MOST and height_attr in ("wrap_content",)
    ):
        # For wrap_content with no constraint, use a reasonable default
        # (e.g., 3 list items at 48dp each = 144dp)
        desired_height = 144
    
    # Resolve against MeasureSpec
    view.width = constrain_to_spec(desired_width, width_spec)
    view.height = constrain_to_spec(desired_height, height_spec)
