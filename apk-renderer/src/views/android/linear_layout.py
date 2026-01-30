from models import DimensionPixels, LayoutChildCallback, MeasureChildCallback, MeasureSpec, MeasureSpecMode, Padding, RenderContext, View
from gravity import Gravity, get_horizontal_gravity, get_vertical_gravity
from resources import (
    deref_bool,
    deref_dimension,
    deref_dimension_to_pixels,
    deref_float,
    deref_gravity,
    get_margins,
    get_padding,
)
from measure_spec import constrain_to_spec, get_child_measure_spec

# TODO: Doesnt handle baselineAligned
# TODO: Doesnt handle baselineAlignedChildIndex
# TODO: Doesnt handle RTL layout direction for START/END gravity


def layout_linear_layout(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """
    Layout a LinearLayout and its children.

    Dispatches to vertical or horizontal layout based on orientation attribute.
    """
    # Set our own position
    view.x = parent_x
    view.y = parent_y

    padding = get_padding(view.attributes, ctx)
    orientation = view.attributes.get("android:orientation", "vertical")

    if orientation == "horizontal":
        layout_children_horizontal(view, ctx, padding, layout_child)
    else:
        layout_children_vertical(view, ctx, padding, layout_child)


def measure_linear_layout(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure a LinearLayout and all its children.

    Dispatches to vertical or horizontal measurement based on orientation attribute.
    """
    orientation = view.attributes.get("android:orientation", "vertical")
    if orientation == "horizontal":
        measure_linear_layout_horizontal(view, width_spec, height_spec, ctx, measure_child)
    else:
        measure_linear_layout_vertical(view, width_spec, height_spec, ctx, measure_child)


def measure_linear_layout_vertical(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure a vertical LinearLayout and all its children.
    
    Vertical LinearLayout stacks children top-to-bottom.
    Main axis = vertical (height), cross axis = horizontal (width).
    """
    
    padding = get_padding(view.attributes, ctx)
    
    # LinearLayout attributes
    weight_sum_attr = deref_float(view.attributes.get("android:weightSum"), ctx)
    measure_with_largest = deref_bool(view.attributes.get("android:measureWithLargestChild"), ctx)
    
    # Track totals during measurement
    total_length = 0
    total_weight = 0.0
    max_width = 0
    largest_child_height = 0
    
    # Available height for children
    available_height = (
        height_spec.size - padding.top - padding.bottom
        if height_spec.mode != MeasureSpecMode.UNSPECIFIED
        else 0
    )
    
    # First pass: measure children, accumulate total length
    # Track weighted children for second pass
    weighted_children: list[tuple[View, float, bool]] = []  # (child, weight, measured_with_zero_height)
    
    for child in view.children:
        if child.attributes.get("android:visibility") == "gone":
            continue
        
        margins = get_margins(child.attributes, ctx)
        child_width_dim = deref_dimension(child.attributes.get("android:layout_width"), ctx)
        child_height_dim = deref_dimension(child.attributes.get("android:layout_height"), ctx)
        weight = deref_float(child.attributes.get("android:layout_weight"), ctx) or 0.0
        
        total_weight += weight
        
        # Calculate width spec for child
        child_width_spec = get_child_measure_spec(
            width_spec,
            padding.left + padding.right + margins.left + margins.right,
            child_width_dim
        )
        
        # Check for optimization: weight > 0 and height = 0
        # In this case, skip height measurement and assign entirely from weight
        use_zero_height = (
            weight > 0 and
            isinstance(child_height_dim, DimensionPixels) and
            child_height_dim.value == 0 and
            height_spec.mode != MeasureSpecMode.UNSPECIFIED
        )
        
        if use_zero_height:
            # Measure with zero height just to get width
            child_height_spec = MeasureSpec(MeasureSpecMode.EXACTLY, 0)
            measure_child(child, child_width_spec, child_height_spec, ctx)
            
            total_length += margins.top + margins.bottom
            weighted_children.append((child, weight, True))
        else:
            # Measure child with remaining space
            used_height = total_length
            remaining_for_child = max(0, available_height - used_height)
            
            if height_spec.mode == MeasureSpecMode.UNSPECIFIED:
                child_height_spec = get_child_measure_spec(
                    MeasureSpec(MeasureSpecMode.UNSPECIFIED, 0),
                    margins.top + margins.bottom,
                    child_height_dim
                )
            else:
                child_height_spec = get_child_measure_spec(
                    MeasureSpec(height_spec.mode, remaining_for_child),
                    margins.top + margins.bottom,
                    child_height_dim
                )
            
            measure_child(child, child_width_spec, child_height_spec, ctx)
            
            child_height = child.height
            total_length += child_height + margins.top + margins.bottom
            
            if weight > 0:
                weighted_children.append((child, weight, False))
            
            # Track largest for measureWithLargestChild
            largest_child_height = max(largest_child_height, child_height)
        
        # Track max width (cross axis)
        child_total_width = child.width + margins.left + margins.right
        max_width = max(max_width, child_total_width)
    
    # Add padding to total length
    total_length += padding.top + padding.bottom
    
    # Handle measureWithLargestChild - recalculate total_length using largest
    if measure_with_largest and largest_child_height > 0:
        recalculated_length = padding.top + padding.bottom
        for child in view.children:
            if child.attributes.get("android:visibility") == "gone":
                continue
            margins = get_margins(child.attributes, ctx)
            recalculated_length += largest_child_height + margins.top + margins.bottom
        total_length = recalculated_length
    
    # Determine our height
    match height_spec.mode:
        case MeasureSpecMode.EXACTLY:
            measured_height = height_spec.size
        case MeasureSpecMode.AT_MOST:
            measured_height = min(total_length, height_spec.size)
        case MeasureSpecMode.UNSPECIFIED:
            measured_height = total_length
    
    # Second pass: distribute remaining space to weighted children
    remaining = measured_height - total_length
    
    if total_weight > 0 and remaining != 0:
        weight_sum = weight_sum_attr if weight_sum_attr is not None else total_weight
        
        for child, weight, was_zero_height in weighted_children:
            share = int((weight / weight_sum) * remaining)
            
            margins = get_margins(child.attributes, ctx)
            
            # Re-measure with new height
            child_width_dim = deref_dimension(child.attributes.get("android:layout_width"), ctx)
            child_width_spec = get_child_measure_spec(
                width_spec,
                padding.left + padding.right + margins.left + margins.right,
                child_width_dim
            )
            
            if was_zero_height:
                new_height = max(0, share)
            else:
                new_height = max(0, child.height + share)
            
            child_height_spec = MeasureSpec(MeasureSpecMode.EXACTLY, new_height)
            measure_child(child, child_width_spec, child_height_spec, ctx)
            
            # Update max width (might have changed with new height)
            child_total_width = child.width + margins.left + margins.right
            max_width = max(max_width, child_total_width)
    
    # Calculate our width (cross axis)
    measured_width = max_width + padding.left + padding.right
    
    # Apply min/max constraints
    min_width = deref_dimension_to_pixels(view.attributes.get("android:minWidth"), ctx, 0)
    min_height = deref_dimension_to_pixels(view.attributes.get("android:minHeight"), ctx, 0)
    max_width_attr = deref_dimension_to_pixels(
        view.attributes.get("android:maxWidth"), ctx,
        width_spec.size if width_spec.mode != MeasureSpecMode.UNSPECIFIED else measured_width
    )
    max_height_attr = deref_dimension_to_pixels(
        view.attributes.get("android:maxHeight"), ctx,
        height_spec.size if height_spec.mode != MeasureSpecMode.UNSPECIFIED else measured_height
    )
    
    measured_width = max(min_width, min(max_width_attr, measured_width))
    measured_height = max(min_height, min(max_height_attr, measured_height))
    
    # Final constrain to spec
    view.width = constrain_to_spec(measured_width, width_spec)
    view.height = constrain_to_spec(measured_height, height_spec)


def layout_children_vertical(
    view: View,
    ctx: RenderContext,
    padding: Padding,
    layout_child: LayoutChildCallback,
) -> None:
    """
    Position children within a vertical LinearLayout.

    Children are stacked top-to-bottom with positioning determined by gravity.
    """
    gravity = deref_gravity(view.attributes.get("android:gravity"), ctx, Gravity.TOP | Gravity.LEFT)

    # Calculate total content height (sum of children + margins)
    content_height = 0
    for child in view.children:
        if child.attributes.get("android:visibility") == "gone":
            continue
        margins = get_margins(child.attributes, ctx)
        content_height += child.height + margins.top + margins.bottom

    # Available space for children
    available_height = view.height - padding.top - padding.bottom
    available_width = view.width - padding.left - padding.right

    # Starting Y based on vertical gravity
    v_gravity = get_vertical_gravity(gravity)
    if v_gravity == Gravity.BOTTOM:
        child_top = view.y + padding.top + (available_height - content_height)
    elif v_gravity == Gravity.CENTER_VERTICAL:
        child_top = view.y + padding.top + (available_height - content_height) // 2
    else:  # TOP or default
        child_top = view.y + padding.top

    # Position each child
    for child in view.children:
        if child.attributes.get("android:visibility") == "gone":
            continue

        margins = get_margins(child.attributes, ctx)

        # Determine horizontal gravity for this child
        # layout_gravity on child takes precedence over parent gravity
        layout_gravity = deref_gravity(child.attributes.get("android:layout_gravity"), ctx, Gravity.NONE)
        h_gravity = get_horizontal_gravity(layout_gravity)
        if h_gravity == Gravity.NONE:
            h_gravity = get_horizontal_gravity(gravity)

        # Calculate X position based on horizontal gravity
        child_available_width = available_width - margins.left - margins.right

        if h_gravity == Gravity.RIGHT:
            child_x = view.x + padding.left + margins.left + (child_available_width - child.width)
        elif h_gravity == Gravity.CENTER_HORIZONTAL:
            child_x = view.x + padding.left + margins.left + (child_available_width - child.width) // 2
        else:  # LEFT or default
            child_x = view.x + padding.left + margins.left

        # Y position
        child_y = child_top + margins.top

        # Layout the child at the calculated position
        layout_child(child, child_x, child_y, available_width, available_height, ctx)

        # Advance for next child
        child_top += margins.top + child.height + margins.bottom


def measure_linear_layout_horizontal(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure a horizontal LinearLayout and all its children.
    
    Horizontal LinearLayout arranges children left-to-right.
    Main axis = horizontal (width), cross axis = vertical (height).
    """
    
    padding = get_padding(view.attributes, ctx)
    
    # LinearLayout attributes
    weight_sum_attr = deref_float(view.attributes.get("android:weightSum"), ctx)
    measure_with_largest = deref_bool(view.attributes.get("android:measureWithLargestChild"), ctx)
    
    # Track totals during measurement
    total_length = 0
    total_weight = 0.0
    max_height = 0
    largest_child_width = 0
    
    # Available width for children
    available_width = (
        width_spec.size - padding.left - padding.right
        if width_spec.mode != MeasureSpecMode.UNSPECIFIED
        else 0
    )
    
    # First pass: measure children, accumulate total length
    # Track weighted children for second pass
    weighted_children: list[tuple[View, float, bool]] = []  # (child, weight, measured_with_zero_width)
    
    for child in view.children:
        if child.attributes.get("android:visibility") == "gone":
            continue
        
        margins = get_margins(child.attributes, ctx)
        child_width_dim = deref_dimension(child.attributes.get("android:layout_width"), ctx)
        child_height_dim = deref_dimension(child.attributes.get("android:layout_height"), ctx)
        weight = deref_float(child.attributes.get("android:layout_weight"), ctx) or 0.0
        
        total_weight += weight
        
        # Calculate height spec for child
        child_height_spec = get_child_measure_spec(
            height_spec,
            padding.top + padding.bottom + margins.top + margins.bottom,
            child_height_dim
        )
        
        # Check for optimization: weight > 0 and width = 0
        # In this case, skip width measurement and assign entirely from weight
        use_zero_width = (
            weight > 0 and
            isinstance(child_width_dim, DimensionPixels) and
            child_width_dim.value == 0 and
            width_spec.mode != MeasureSpecMode.UNSPECIFIED
        )
        
        if use_zero_width:
            # Measure with zero width just to get height
            child_width_spec = MeasureSpec(MeasureSpecMode.EXACTLY, 0)
            measure_child(child, child_width_spec, child_height_spec, ctx)
            
            total_length += margins.left + margins.right
            weighted_children.append((child, weight, True))
        else:
            # Measure child with remaining space
            used_width = total_length
            remaining_for_child = max(0, available_width - used_width)
            
            if width_spec.mode == MeasureSpecMode.UNSPECIFIED:
                child_width_spec = get_child_measure_spec(
                    MeasureSpec(MeasureSpecMode.UNSPECIFIED, 0),
                    margins.left + margins.right,
                    child_width_dim
                )
            else:
                child_width_spec = get_child_measure_spec(
                    MeasureSpec(width_spec.mode, remaining_for_child),
                    margins.left + margins.right,
                    child_width_dim
                )
            
            measure_child(child, child_width_spec, child_height_spec, ctx)
            
            child_width = child.width
            total_length += child_width + margins.left + margins.right
            
            if weight > 0:
                weighted_children.append((child, weight, False))
            
            # Track largest for measureWithLargestChild
            largest_child_width = max(largest_child_width, child_width)
        
        # Track max height (cross axis)
        child_total_height = child.height + margins.top + margins.bottom
        max_height = max(max_height, child_total_height)
    
    # Add padding to total length
    total_length += padding.left + padding.right
    
    # Handle measureWithLargestChild - recalculate total_length using largest
    if measure_with_largest and largest_child_width > 0:
        recalculated_length = padding.left + padding.right
        for child in view.children:
            if child.attributes.get("android:visibility") == "gone":
                continue
            margins = get_margins(child.attributes, ctx)
            recalculated_length += largest_child_width + margins.left + margins.right
        total_length = recalculated_length
    
    # Determine our width
    match width_spec.mode:
        case MeasureSpecMode.EXACTLY:
            measured_width = width_spec.size
        case MeasureSpecMode.AT_MOST:
            measured_width = min(total_length, width_spec.size)
        case MeasureSpecMode.UNSPECIFIED:
            measured_width = total_length
    
    # Second pass: distribute remaining space to weighted children
    remaining = measured_width - total_length
    
    if total_weight > 0 and remaining != 0:
        weight_sum = weight_sum_attr if weight_sum_attr is not None else total_weight
        
        for child, weight, was_zero_width in weighted_children:
            share = int((weight / weight_sum) * remaining)
            
            margins = get_margins(child.attributes, ctx)
            
            # Re-measure with new width
            child_height_dim = deref_dimension(child.attributes.get("android:layout_height"), ctx)
            child_height_spec = get_child_measure_spec(
                height_spec,
                padding.top + padding.bottom + margins.top + margins.bottom,
                child_height_dim
            )
            
            if was_zero_width:
                new_width = max(0, share)
            else:
                new_width = max(0, child.width + share)
            
            child_width_spec = MeasureSpec(MeasureSpecMode.EXACTLY, new_width)
            measure_child(child, child_width_spec, child_height_spec, ctx)
            
            # Update max height (might have changed with new width)
            child_total_height = child.height + margins.top + margins.bottom
            max_height = max(max_height, child_total_height)
    
    # Calculate our height (cross axis)
    measured_height = max_height + padding.top + padding.bottom
    
    # Apply min/max constraints
    min_width = deref_dimension_to_pixels(view.attributes.get("android:minWidth"), ctx, 0)
    min_height = deref_dimension_to_pixels(view.attributes.get("android:minHeight"), ctx, 0)
    max_width_attr = deref_dimension_to_pixels(
        view.attributes.get("android:maxWidth"), ctx,
        width_spec.size if width_spec.mode != MeasureSpecMode.UNSPECIFIED else measured_width
    )
    max_height_attr = deref_dimension_to_pixels(
        view.attributes.get("android:maxHeight"), ctx,
        height_spec.size if height_spec.mode != MeasureSpecMode.UNSPECIFIED else measured_height
    )
    
    measured_width = max(min_width, min(max_width_attr, measured_width))
    measured_height = max(min_height, min(max_height_attr, measured_height))
    
    # Final constrain to spec
    view.width = constrain_to_spec(measured_width, width_spec)
    view.height = constrain_to_spec(measured_height, height_spec)


def layout_children_horizontal(
    view: View,
    ctx: RenderContext,
    padding: Padding,
    layout_child: LayoutChildCallback,
) -> None:
    """
    Position children within a horizontal LinearLayout.

    Children are arranged left-to-right with positioning determined by gravity.
    """
    gravity = deref_gravity(view.attributes.get("android:gravity"), ctx, Gravity.TOP | Gravity.LEFT)

    # Calculate total content width (sum of children + margins)
    content_width = 0
    for child in view.children:
        if child.attributes.get("android:visibility") == "gone":
            continue
        margins = get_margins(child.attributes, ctx)
        content_width += child.width + margins.left + margins.right

    # Available space for children
    available_width = view.width - padding.left - padding.right
    available_height = view.height - padding.top - padding.bottom

    # Starting X based on horizontal gravity
    h_gravity = get_horizontal_gravity(gravity)
    if h_gravity == Gravity.RIGHT:
        child_left = view.x + padding.left + (available_width - content_width)
    elif h_gravity == Gravity.CENTER_HORIZONTAL:
        child_left = view.x + padding.left + (available_width - content_width) // 2
    else:  # LEFT or default
        child_left = view.x + padding.left

    # Position each child
    for child in view.children:
        if child.attributes.get("android:visibility") == "gone":
            continue

        margins = get_margins(child.attributes, ctx)

        # Determine vertical gravity for this child
        # layout_gravity on child takes precedence over parent gravity
        layout_gravity = deref_gravity(child.attributes.get("android:layout_gravity"), ctx, Gravity.NONE)
        v_gravity = get_vertical_gravity(layout_gravity)
        if v_gravity == Gravity.NONE:
            v_gravity = get_vertical_gravity(gravity)

        # Calculate Y position based on vertical gravity
        child_available_height = available_height - margins.top - margins.bottom

        if v_gravity == Gravity.BOTTOM:
            child_y = view.y + padding.top + margins.top + (child_available_height - child.height)
        elif v_gravity == Gravity.CENTER_VERTICAL:
            child_y = view.y + padding.top + margins.top + (child_available_height - child.height) // 2
        else:  # TOP or default
            child_y = view.y + padding.top + margins.top

        # X position
        child_x = child_left + margins.left

        # Layout the child at the calculated position
        layout_child(child, child_x, child_y, available_width, available_height, ctx)

        # Advance for next child
        child_left += margins.left + child.width + margins.right
