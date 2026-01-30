from models import LayoutChildCallback, MeasureChildCallback, MeasureSpec, MeasureSpecMode, RenderContext, View
from resources import (
    deref_dimension,
    deref_dimension_to_offset,
    deref_dimension_to_pixels,
    get_padding,
)
from measure_spec import constrain_to_spec, get_child_measure_spec


def layout_absolute_layout(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """
    Layout an AbsoluteLayout and its children.

    AbsoluteLayout positions children at explicit (layout_x, layout_y) coordinates
    relative to the container's content area (after padding).
    """
    # Set our own position
    view.x = parent_x
    view.y = parent_y

    # Get padding
    padding = get_padding(view.attributes, ctx)

    # Layout each child at its specified position
    for child in view.children:
        # Skip gone children
        if child.attributes.get("android:visibility") == "gone":
            continue

        # Get child's explicit position
        layout_x = deref_dimension_to_offset(child.attributes.get("android:layout_x"), ctx, 0)
        layout_y = deref_dimension_to_offset(child.attributes.get("android:layout_y"), ctx, 0)

        # Calculate child's absolute position
        child_x = view.x + padding.left + layout_x
        child_y = view.y + padding.top + layout_y

        # Layout the child at its position
        layout_child(child, child_x, child_y, view.width - padding.left - padding.right, view.height - padding.top - padding.bottom, ctx)


def measure_absolute_layout(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure an AbsoluteLayout and all its children.
    
    AbsoluteLayout positions children at explicit (layout_x, layout_y) coordinates.
    For wrap_content, it sizes to enclose all children.
    """
    
    padding = get_padding(view.attributes, ctx)
    
    # Track bounds for wrap_content calculation
    max_child_right = 0
    max_child_bottom = 0
    
    for child in view.children:
        # Skip gone children
        if child.attributes.get("android:visibility") == "gone":
            continue

        # Get child's layout params
        child_width_dim = deref_dimension(child.attributes.get("android:layout_width"), ctx)
        child_height_dim = deref_dimension(child.attributes.get("android:layout_height"), ctx)

        # Calculate available space for child (parent's content area)
        available_width = max(0, width_spec.size - padding.left - padding.right) if width_spec.mode != MeasureSpecMode.UNSPECIFIED else 0
        available_height = max(0, height_spec.size - padding.top - padding.bottom) if height_spec.mode != MeasureSpecMode.UNSPECIFIED else 0

        # Create child MeasureSpecs
        child_width_spec = get_child_measure_spec(
            MeasureSpec(width_spec.mode, available_width),
            0,  # AbsoluteLayout doesn't use margins
            child_width_dim
        )
        child_height_spec = get_child_measure_spec(
            MeasureSpec(height_spec.mode, available_height),
            0,  # AbsoluteLayout doesn't use margins
            child_height_dim
        )

        # Measure child
        measure_child(child, child_width_spec, child_height_spec, ctx)

        # Get child position (needed for wrap_content calculation)
        layout_x = deref_dimension_to_offset(child.attributes.get("android:layout_x"), ctx, 0)
        layout_y = deref_dimension_to_offset(child.attributes.get("android:layout_y"), ctx, 0)

        # Track bounds for wrap_content sizing
        # Note: We don't set child.x/child.y here - that's done in layout pass
        max_child_right = max(max_child_right, layout_x + child.width)
        max_child_bottom = max(max_child_bottom, layout_y + child.height)
    
    # Calculate our own size
    desired_width = max_child_right + padding.left + padding.right
    desired_height = max_child_bottom + padding.top + padding.bottom

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
