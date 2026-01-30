from dataclasses import dataclass
from graphlib import TopologicalSorter, CycleError
from models import DimensionMatchParent, LayoutChildCallback, MeasureChildCallback, MeasureSpec, MeasureSpecMode, RenderContext, View
from resources import (
    deref_bool,
    deref_dimension,
    deref_dimension_to_pixels,
    get_margins,
    get_padding,
)
from measure_spec import constrain_to_spec

# Android RelativeLayout rule constants
# Horizontal rules
LEFT_OF = "android:layout_toLeftOf"
RIGHT_OF = "android:layout_toRightOf"
START_OF = "android:layout_toStartOf"
END_OF = "android:layout_toEndOf"
ALIGN_LEFT = "android:layout_alignLeft"
ALIGN_RIGHT = "android:layout_alignRight"
ALIGN_START = "android:layout_alignStart"
ALIGN_END = "android:layout_alignEnd"
ALIGN_PARENT_LEFT = "android:layout_alignParentLeft"
ALIGN_PARENT_RIGHT = "android:layout_alignParentRight"
ALIGN_PARENT_START = "android:layout_alignParentStart"
ALIGN_PARENT_END = "android:layout_alignParentEnd"

# Vertical rules
ABOVE = "android:layout_above"
BELOW = "android:layout_below"
ALIGN_TOP = "android:layout_alignTop"
ALIGN_BOTTOM = "android:layout_alignBottom"
ALIGN_BASELINE = "android:layout_alignBaseline"  # TODO: Not implemented
ALIGN_PARENT_TOP = "android:layout_alignParentTop"
ALIGN_PARENT_BOTTOM = "android:layout_alignParentBottom"

# Center rules
CENTER_IN_PARENT = "android:layout_centerInParent"
CENTER_HORIZONTAL = "android:layout_centerHorizontal"
CENTER_VERTICAL = "android:layout_centerVertical"

# All horizontal rule names
HORIZONTAL_RULES = [
    LEFT_OF, RIGHT_OF, START_OF, END_OF,
    ALIGN_LEFT, ALIGN_RIGHT, ALIGN_START, ALIGN_END,
    ALIGN_PARENT_LEFT, ALIGN_PARENT_RIGHT, ALIGN_PARENT_START, ALIGN_PARENT_END,
    CENTER_IN_PARENT, CENTER_HORIZONTAL
]

# All vertical rule names
VERTICAL_RULES = [
    ABOVE, BELOW,
    ALIGN_TOP, ALIGN_BOTTOM, ALIGN_BASELINE,
    ALIGN_PARENT_TOP, ALIGN_PARENT_BOTTOM,
    CENTER_IN_PARENT, CENTER_VERTICAL
]


@dataclass
class ChildBounds:
    """Stores the calculated boundaries for a child view."""
    left: int = -1   # -1 means undefined
    top: int = -1
    right: int = -1
    bottom: int = -1


def layout_relative_layout(
    view: View,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    ctx: RenderContext,
    layout_child: LayoutChildCallback,
) -> None:
    """
    Layout a RelativeLayout and its children.

    Children are positioned using rules (relative to parent or siblings).
    Uses topological sort to position children in dependency order.
    """
    # Set our own position
    view.x = parent_x
    view.y = parent_y

    padding = get_padding(view.attributes, ctx)

    # Build ID lookup for children
    id_to_child: dict[str, View] = {}
    for child in view.children:
        child_id = child.attributes.get("android:id")
        if child_id:
            # Strip @+id/ or @id/ prefix
            if child_id.startswith("@+id/"):
                child_id = child_id[5:]
            elif child_id.startswith("@id/"):
                child_id = child_id[4:]
            id_to_child[child_id] = child

    # Store boundaries for each child (relative to parent)
    # Use id(child) as key since View objects are not hashable
    child_bounds: dict[int, ChildBounds] = {id(child): ChildBounds() for child in view.children}

    # Sort children by horizontal and vertical dependencies
    sorted_horizontal = sort_children_by_dependencies(view.children, id_to_child, HORIZONTAL_RULES, ctx)
    sorted_vertical = sort_children_by_dependencies(view.children, id_to_child, VERTICAL_RULES, ctx)

    # Apply horizontal positioning rules
    for child in sorted_horizontal:
        if child.attributes.get("android:visibility") == "gone":
            continue
        bounds = child_bounds[id(child)]
        apply_horizontal_layout_rules(child, id_to_child, child_bounds, bounds, view.width, padding, ctx)

    # Apply vertical positioning rules
    for child in sorted_vertical:
        if child.attributes.get("android:visibility") == "gone":
            continue
        bounds = child_bounds[id(child)]
        apply_vertical_layout_rules(child, id_to_child, child_bounds, bounds, view.height, padding, ctx)

    # Position each child using calculated bounds
    for child in view.children:
        if child.attributes.get("android:visibility") == "gone":
            continue

        bounds = child_bounds[id(child)]
        margins = get_margins(child.attributes, ctx)

        # Convert relative bounds to absolute coordinates
        if bounds.left != -1:
            child_x = view.x + bounds.left
        else:
            # Default to top-left with padding and margins
            child_x = view.x + padding.left + margins.left

        if bounds.top != -1:
            child_y = view.y + bounds.top
        else:
            # Default to top-left with padding and margins
            child_y = view.y + padding.top + margins.top

        # Calculate available space for child (for recursive layout)
        available_width = view.width - padding.left - padding.right
        available_height = view.height - padding.top - padding.bottom

        # Layout the child at the calculated position
        layout_child(child, child_x, child_y, available_width, available_height, ctx)


def measure_relative_layout(
    view: View,
    width_spec: MeasureSpec,
    height_spec: MeasureSpec,
    ctx: RenderContext,
    measure_child: MeasureChildCallback,
) -> None:
    """
    Measure a RelativeLayout and all its children.

    Children are positioned using rules (relative to parent or siblings).
    Uses topological sort to measure children in dependency order.
    """

    padding = get_padding(view.attributes, ctx)

    # Build ID lookup for children
    id_to_child: dict[str, View] = {}
    for child in view.children:
        child_id = child.attributes.get("android:id")
        if child_id:
            # Strip @+id/ or @id/ prefix
            if child_id.startswith("@+id/"):
                child_id = child_id[5:]
            elif child_id.startswith("@id/"):
                child_id = child_id[4:]
            id_to_child[child_id] = child

    # Store boundaries for each child
    # Use id(child) as key since View objects are not hashable
    child_bounds: dict[int, ChildBounds] = {id(child): ChildBounds() for child in view.children}

    # Sort children by horizontal dependencies
    sorted_horizontal = sort_children_by_dependencies(view.children, id_to_child, HORIZONTAL_RULES, ctx)

    # Sort children by vertical dependencies
    sorted_vertical = sort_children_by_dependencies(view.children, id_to_child, VERTICAL_RULES, ctx)

    # First pass: Apply horizontal rules and measure children horizontally
    for child in sorted_horizontal:
        if child.attributes.get("android:visibility") == "gone":
            continue

        bounds = child_bounds[id(child)]
        apply_horizontal_size_rules(child, id_to_child, child_bounds, bounds, width_spec, padding, ctx)

        # Create horizontal MeasureSpec from boundaries
        margins = get_margins(child.attributes, ctx)
        child_width_dim = deref_dimension(child.attributes.get("android:layout_width"), ctx)

        child_width_spec = get_child_measure_spec_from_bounds(
            bounds.left, bounds.right,
            child_width_dim,
            margins.left, margins.right,
            padding.left, padding.right,
            width_spec
        )

        # Measure child horizontally (with unspecified height for now)
        temp_height_spec = MeasureSpec(MeasureSpecMode.UNSPECIFIED, 0)
        measure_child(child, child_width_spec, temp_height_spec, ctx)

    # Second pass: Apply vertical rules and measure children fully
    for child in sorted_vertical:
        if child.attributes.get("android:visibility") == "gone":
            continue

        bounds = child_bounds[id(child)]
        apply_vertical_size_rules(child, id_to_child, child_bounds, bounds, height_spec, padding, ctx)

        # Create vertical MeasureSpec from boundaries
        margins = get_margins(child.attributes, ctx)
        child_height_dim = deref_dimension(child.attributes.get("android:layout_height"), ctx)

        child_height_spec = get_child_measure_spec_from_bounds(
            bounds.top, bounds.bottom,
            child_height_dim,
            margins.top, margins.bottom,
            padding.top, padding.bottom,
            height_spec
        )

        # Re-measure child with proper dimensions
        child_width_dim = deref_dimension(child.attributes.get("android:layout_width"), ctx)
        child_width_spec = get_child_measure_spec_from_bounds(
            bounds.left, bounds.right,
            child_width_dim,
            margins.left, margins.right,
            padding.left, padding.right,
            width_spec
        )

        measure_child(child, child_width_spec, child_height_spec, ctx)

    # Calculate our own size based on children bounds
    is_wrap_width = width_spec.mode != MeasureSpecMode.EXACTLY
    is_wrap_height = height_spec.mode != MeasureSpecMode.EXACTLY

    if is_wrap_width or is_wrap_height:
        max_width = 0
        max_height = 0

        for child in view.children:
            if child.attributes.get("android:visibility") == "gone":
                continue

            margins = get_margins(child.attributes, ctx)

            # For wrap_content, calculate extent based on actual bounds
            # Android behavior: Use bounds if set (even if negative from alignParent* with wrap_content parent)
            # The max() calls below naturally handle negative values
            bounds = child_bounds[id(child)]

            if bounds.right != -1:
                child_right = bounds.right + margins.right
            else:
                # Use measured width
                child_right = (bounds.left if bounds.left != -1 else padding.left) + margins.left + child.width + margins.right

            if bounds.bottom != -1:
                child_bottom = bounds.bottom + margins.bottom
            else:
                child_bottom = (bounds.top if bounds.top != -1 else padding.top) + margins.top + child.height + margins.bottom

            # max() naturally handles negative values (e.g., from alignParentBottom when parent height is -1)
            max_width = max(max_width, child_right)
            max_height = max(max_height, child_bottom)

        desired_width = max_width + padding.right
        desired_height = max_height + padding.bottom
    else:
        desired_width = width_spec.size
        desired_height = height_spec.size

    # Apply min/max constraints
    min_width = deref_dimension_to_pixels(view.attributes.get("android:minWidth"), ctx, 0)
    min_height = deref_dimension_to_pixels(view.attributes.get("android:minHeight"), ctx, 0)
    max_width_attr = deref_dimension_to_pixels(
        view.attributes.get("android:maxWidth"), ctx,
        width_spec.size if width_spec.mode != MeasureSpecMode.UNSPECIFIED else desired_width
    )
    max_height_attr = deref_dimension_to_pixels(
        view.attributes.get("android:maxHeight"), ctx,
        height_spec.size if height_spec.mode != MeasureSpecMode.UNSPECIFIED else desired_height
    )

    desired_width = max(min_width, min(max_width_attr, desired_width))
    desired_height = max(min_height, min(max_height_attr, desired_height))

    # Resolve against MeasureSpec
    view.width = constrain_to_spec(desired_width, width_spec)
    view.height = constrain_to_spec(desired_height, height_spec)


def get_child_measure_spec_from_bounds(
    start: int,
    end: int,
    child_dimension,
    margin_start: int,
    margin_end: int,
    padding_start: int,
    padding_end: int,
    parent_spec: MeasureSpec
) -> MeasureSpec:
    """
    Create a MeasureSpec for a child based on its boundary constraints.

    This mirrors Android's logic for converting layout boundaries to MeasureSpecs.
    """
    # Both edges defined → EXACTLY with size = (end - start)
    if start != -1 and end != -1:
        size = max(0, end - start)
        return MeasureSpec(MeasureSpecMode.EXACTLY, size)

    # MATCH_PARENT with at least one edge defined
    if isinstance(child_dimension, DimensionMatchParent):
        if parent_spec.mode == MeasureSpecMode.UNSPECIFIED:
            # No constraint from parent
            return MeasureSpec(MeasureSpecMode.UNSPECIFIED, 0)

        # Calculate available space
        if start != -1:
            # Start edge defined, fill to parent end
            available = parent_spec.size - start - padding_end - margin_end
        elif end != -1:
            # End edge defined, fill from parent start
            available = end - padding_start - margin_start
        else:
            # No edges defined, use full parent space
            available = parent_spec.size - padding_start - padding_end - margin_start - margin_end

        return MeasureSpec(MeasureSpecMode.EXACTLY, max(0, available))

    # Only one edge defined → AT_MOST with available space
    if start != -1:
        # Start edge defined, child can grow toward parent end
        if parent_spec.mode != MeasureSpecMode.UNSPECIFIED:
            available = parent_spec.size - start - padding_end - margin_end
            return MeasureSpec(MeasureSpecMode.AT_MOST, max(0, available))
        else:
            return MeasureSpec(MeasureSpecMode.UNSPECIFIED, 0)

    if end != -1:
        # End edge defined, child can grow from parent start
        available = end - padding_start - margin_start
        return MeasureSpec(MeasureSpecMode.AT_MOST, max(0, available))

    # No edges defined → use normal dimension handling
    from measure_spec import get_child_measure_spec
    return get_child_measure_spec(
        parent_spec,
        padding_start + padding_end + margin_start + margin_end,
        child_dimension
    )


def sort_children_by_dependencies(
    children: list[View],
    id_to_child: dict[str, View],
    rule_names: list[str],
    ctx: RenderContext,
) -> list[View]:
    """
    Sort children using topological sort based on their dependency rules.

    Returns children in an order where dependencies are resolved before dependents.
    Raises ValueError if circular dependencies are detected.
    """
    # Use TopologicalSorter with id(view) as keys since View is not hashable
    sorter = TopologicalSorter()
    view_id_to_view: dict[int, View] = {}

    for child in children:
        if child.attributes.get("android:visibility") == "gone":
            continue

        view_id_to_view[id(child)] = child

        # Find dependencies for this child
        dependencies = []
        for rule_name in rule_names:
            rule_value = child.attributes.get(rule_name)
            if rule_value:
                # Check if it's a sibling reference (starts with @id/ or @+id/)
                if rule_value.startswith("@id/") or rule_value.startswith("@+id/"):
                    ref_id = rule_value[5:] if rule_value.startswith("@+id/") else rule_value[4:]
                    dependency = id_to_child.get(ref_id)
                    if dependency and dependency in children:
                        dependencies.append(id(dependency))

        # Add this child and its dependencies to the sorter (using ids)
        sorter.add(id(child), *dependencies)

    try:
        sorted_ids = list(sorter.static_order())
        # Convert ids back to Views
        return [view_id_to_view[view_id] for view_id in sorted_ids]
    except CycleError:
        raise ValueError("Circular dependencies cannot exist in RelativeLayout")


def resolve_rtl_rule(rule_name: str, is_rtl: bool) -> str:
    """Resolve START/END rules to LEFT/RIGHT based on layout direction."""
    if not is_rtl:
        return rule_name.replace("Start", "Left").replace("End", "Right")
    else:
        return rule_name.replace("Start", "Right").replace("End", "Left")


def apply_horizontal_size_rules(
    child: View,
    id_to_child: dict[str, View],
    all_child_bounds: dict[int, ChildBounds],
    bounds: ChildBounds,
    parent_width_spec: MeasureSpec,
    padding,
    ctx: RenderContext,
) -> None:
    """
    Apply horizontal positioning rules to calculate child's left and right boundaries.

    Modifies bounds in-place to set left/right constraints.
    """
    attrs = child.attributes
    margins = get_margins(attrs, ctx)

    # TODO: CENTER_IN_PARENT and CENTER_HORIZONTAL are not handled during measure.
    # These require the parent's final size and should be handled in the layout pass.

    # Resolve START/END to LEFT/RIGHT based on RTL
    if attrs.get(ALIGN_PARENT_START):
        rule = resolve_rtl_rule(ALIGN_PARENT_START, ctx.is_rtl)
        attrs = {**attrs, rule: "true"}
    if attrs.get(ALIGN_PARENT_END):
        rule = resolve_rtl_rule(ALIGN_PARENT_END, ctx.is_rtl)
        attrs = {**attrs, rule: "true"}
    if attrs.get(START_OF):
        rule = resolve_rtl_rule(START_OF, ctx.is_rtl)
        attrs = {**attrs, rule: attrs.get(START_OF)}
    if attrs.get(END_OF):
        rule = resolve_rtl_rule(END_OF, ctx.is_rtl)
        attrs = {**attrs, rule: attrs.get(END_OF)}
    if attrs.get(ALIGN_START):
        rule = resolve_rtl_rule(ALIGN_START, ctx.is_rtl)
        attrs = {**attrs, rule: attrs.get(ALIGN_START)}
    if attrs.get(ALIGN_END):
        rule = resolve_rtl_rule(ALIGN_END, ctx.is_rtl)
        attrs = {**attrs, rule: attrs.get(ALIGN_END)}

    # Apply rules in Android's priority order (highest to lowest priority)
    # Priority for left edge: RIGHT_OF > ALIGN_LEFT > ALIGN_PARENT_LEFT
    # Priority for right edge: LEFT_OF > ALIGN_RIGHT > ALIGN_PARENT_RIGHT

    # Apply parent alignment rules first (lowest priority)
    if deref_bool(attrs.get(ALIGN_PARENT_LEFT), ctx):
        bounds.left = padding.left + margins.left

    if deref_bool(attrs.get(ALIGN_PARENT_RIGHT), ctx):
        # Android behavior: Always set right bound, even if parent size is unknown (-1 for wrap_content)
        # This may result in negative values, which are naturally handled by max() in wrap calculation
        parent_width = parent_width_spec.size if parent_width_spec.mode != MeasureSpecMode.UNSPECIFIED else -1
        bounds.right = parent_width - padding.right - margins.right

    # Apply sibling alignment rules (medium priority, only if not already set)
    ref = get_referenced_view(attrs.get(ALIGN_LEFT), id_to_child)
    if ref and bounds.left == -1:
        ref_bounds = all_child_bounds[id(ref)]
        ref_margins = get_margins(ref.attributes, ctx)
        ref_left = ref_bounds.left if ref_bounds.left != -1 else padding.left + ref_margins.left
        bounds.left = ref_left + margins.left

    ref = get_referenced_view(attrs.get(ALIGN_RIGHT), id_to_child)
    if ref and bounds.right == -1:
        ref_bounds = all_child_bounds[id(ref)]
        ref_margins = get_margins(ref.attributes, ctx)
        ref_left = ref_bounds.left if ref_bounds.left != -1 else padding.left + ref_margins.left
        bounds.right = ref_left + ref.width - margins.right

    # Apply sibling positioning rules last (highest priority, unconditional)
    ref = get_referenced_view(attrs.get(LEFT_OF), id_to_child)
    if ref:
        ref_bounds = all_child_bounds[id(ref)]
        ref_margins = get_margins(ref.attributes, ctx)
        ref_left = ref_bounds.left if ref_bounds.left != -1 else padding.left + ref_margins.left
        bounds.right = ref_left - ref_margins.left - margins.right

    ref = get_referenced_view(attrs.get(RIGHT_OF), id_to_child)
    if ref:
        ref_bounds = all_child_bounds[id(ref)]
        ref_margins = get_margins(ref.attributes, ctx)
        ref_left = ref_bounds.left if ref_bounds.left != -1 else padding.left + ref_margins.left
        bounds.left = ref_left + ref.width + ref_margins.right + margins.left


def apply_vertical_size_rules(
    child: View,
    id_to_child: dict[str, View],
    all_child_bounds: dict[int, ChildBounds],
    bounds: ChildBounds,
    parent_height_spec: MeasureSpec,
    padding,
    ctx: RenderContext,
) -> None:
    """
    Apply vertical positioning rules to calculate child's top and bottom boundaries.

    Modifies bounds in-place to set top/bottom constraints.
    """
    attrs = child.attributes
    margins = get_margins(attrs, ctx)

    # TODO: CENTER_IN_PARENT and CENTER_VERTICAL are not handled during measure.
    # These require the parent's final size and should be handled in the layout pass.

    # Apply rules in Android's priority order (highest to lowest priority)
    # Priority for top edge: BELOW > ALIGN_TOP > ALIGN_PARENT_TOP
    # Priority for bottom edge: ABOVE > ALIGN_BOTTOM > ALIGN_PARENT_BOTTOM

    # Apply parent alignment rules first (lowest priority)
    if deref_bool(attrs.get(ALIGN_PARENT_TOP), ctx):
        bounds.top = padding.top + margins.top

    if deref_bool(attrs.get(ALIGN_PARENT_BOTTOM), ctx):
        # Android behavior: Always set bottom bound, even if parent size is unknown (-1 for wrap_content)
        # This may result in negative values, which are naturally handled by max() in wrap calculation
        parent_height = parent_height_spec.size if parent_height_spec.mode != MeasureSpecMode.UNSPECIFIED else -1
        bounds.bottom = parent_height - padding.bottom - margins.bottom

    # Apply sibling alignment rules (medium priority, only if not already set)
    ref = get_referenced_view(attrs.get(ALIGN_TOP), id_to_child)
    if ref and bounds.top == -1:
        ref_bounds = all_child_bounds[id(ref)]
        ref_margins = get_margins(ref.attributes, ctx)
        ref_top = ref_bounds.top if ref_bounds.top != -1 else padding.top + ref_margins.top
        bounds.top = ref_top + margins.top

    ref = get_referenced_view(attrs.get(ALIGN_BOTTOM), id_to_child)
    if ref and bounds.bottom == -1:
        ref_bounds = all_child_bounds[id(ref)]
        ref_margins = get_margins(ref.attributes, ctx)
        ref_top = ref_bounds.top if ref_bounds.top != -1 else padding.top + ref_margins.top
        bounds.bottom = ref_top + ref.height - margins.bottom

    # alignBaseline - TODO: Not implemented (medium priority)
    if attrs.get(ALIGN_BASELINE) and bounds.top == -1:
        print(f"Warning: {ALIGN_BASELINE} not implemented (requires text baseline metrics)")

    # Apply sibling positioning rules last (highest priority, unconditional)
    ref = get_referenced_view(attrs.get(ABOVE), id_to_child)
    if ref:
        ref_bounds = all_child_bounds[id(ref)]
        ref_margins = get_margins(ref.attributes, ctx)
        # Calculate ref_top: use ref_bounds.top if set, otherwise calculate from bottom if available
        if ref_bounds.top != -1:
            ref_top = ref_bounds.top
        elif ref_bounds.bottom != -1:
            # Referenced view is positioned from bottom (e.g., alignParentBottom)
            # Calculate its top position
            ref_top = ref_bounds.bottom - ref_margins.bottom - ref.height - ref_margins.top
        else:
            ref_top = padding.top + ref_margins.top
        bounds.bottom = ref_top - margins.bottom

    ref = get_referenced_view(attrs.get(BELOW), id_to_child)
    if ref:
        ref_bounds = all_child_bounds[id(ref)]
        ref_margins = get_margins(ref.attributes, ctx)
        ref_top = ref_bounds.top if ref_bounds.top != -1 else padding.top + ref_margins.top
        bounds.top = ref_top + ref.height + ref_margins.bottom + margins.top


def get_referenced_view(ref: str | None, id_to_child: dict[str, View]) -> View | None:
    """Extract view ID from a reference string and look it up."""
    if not ref:
        return None

    if ref.startswith("@id/"):
        ref_id = ref[4:]
    elif ref.startswith("@+id/"):
        ref_id = ref[5:]
    else:
        return None

    return id_to_child.get(ref_id)


def apply_horizontal_layout_rules(
    child: View,
    id_to_child: dict[str, View],
    all_child_bounds: dict[int, ChildBounds],
    bounds: ChildBounds,
    parent_width: int,
    padding,
    ctx: RenderContext,
) -> None:
    """
    Apply horizontal positioning rules during layout pass.

    Calculates left position for the child. Similar to apply_horizontal_size_rules
    but handles centering rules (which require final parent size).
    """
    attrs = child.attributes
    margins = get_margins(attrs, ctx)

    # Resolve START/END to LEFT/RIGHT based on RTL
    if attrs.get(ALIGN_PARENT_START):
        rule = resolve_rtl_rule(ALIGN_PARENT_START, ctx.is_rtl)
        attrs = {**attrs, rule: "true"}
    if attrs.get(ALIGN_PARENT_END):
        rule = resolve_rtl_rule(ALIGN_PARENT_END, ctx.is_rtl)
        attrs = {**attrs, rule: "true"}
    if attrs.get(START_OF):
        rule = resolve_rtl_rule(START_OF, ctx.is_rtl)
        attrs = {**attrs, rule: attrs.get(START_OF)}
    if attrs.get(END_OF):
        rule = resolve_rtl_rule(END_OF, ctx.is_rtl)
        attrs = {**attrs, rule: attrs.get(END_OF)}
    if attrs.get(ALIGN_START):
        rule = resolve_rtl_rule(ALIGN_START, ctx.is_rtl)
        attrs = {**attrs, rule: attrs.get(ALIGN_START)}
    if attrs.get(ALIGN_END):
        rule = resolve_rtl_rule(ALIGN_END, ctx.is_rtl)
        attrs = {**attrs, rule: attrs.get(ALIGN_END)}

    # Handle centering first (applies if no other horizontal rules)
    has_horizontal_rule = any(attrs.get(rule) for rule in [
        LEFT_OF, RIGHT_OF, ALIGN_LEFT, ALIGN_RIGHT,
        ALIGN_PARENT_LEFT, ALIGN_PARENT_RIGHT
    ])

    if not has_horizontal_rule:
        if deref_bool(attrs.get(CENTER_IN_PARENT), ctx) or deref_bool(attrs.get(CENTER_HORIZONTAL), ctx):
            # Center horizontally within parent
            available_width = parent_width - padding.left - padding.right - margins.left - margins.right
            bounds.left = padding.left + margins.left + (available_width - child.width) // 2
            return

    # Apply parent alignment rules (lowest priority)
    if deref_bool(attrs.get(ALIGN_PARENT_LEFT), ctx):
        bounds.left = padding.left + margins.left

    if deref_bool(attrs.get(ALIGN_PARENT_RIGHT), ctx):
        bounds.left = parent_width - padding.right - margins.right - child.width

    # Apply sibling alignment rules (medium priority)
    ref = get_referenced_view(attrs.get(ALIGN_LEFT), id_to_child)
    if ref and bounds.left == -1:
        ref_bounds = all_child_bounds[id(ref)]
        ref_left = ref_bounds.left if ref_bounds.left != -1 else padding.left
        bounds.left = ref_left

    ref = get_referenced_view(attrs.get(ALIGN_RIGHT), id_to_child)
    if ref and bounds.left == -1:
        ref_bounds = all_child_bounds[id(ref)]
        ref_left = ref_bounds.left if ref_bounds.left != -1 else padding.left
        bounds.left = ref_left + ref.width - child.width

    # Apply sibling positioning rules (highest priority)
    ref = get_referenced_view(attrs.get(LEFT_OF), id_to_child)
    if ref:
        ref_bounds = all_child_bounds[id(ref)]
        ref_margins = get_margins(ref.attributes, ctx)
        ref_left = ref_bounds.left if ref_bounds.left != -1 else padding.left
        bounds.left = ref_left - margins.right - child.width - ref_margins.left

    ref = get_referenced_view(attrs.get(RIGHT_OF), id_to_child)
    if ref:
        ref_bounds = all_child_bounds[id(ref)]
        ref_margins = get_margins(ref.attributes, ctx)
        ref_left = ref_bounds.left if ref_bounds.left != -1 else padding.left
        bounds.left = ref_left + ref.width + ref_margins.right + margins.left


def apply_vertical_layout_rules(
    child: View,
    id_to_child: dict[str, View],
    all_child_bounds: dict[int, ChildBounds],
    bounds: ChildBounds,
    parent_height: int,
    padding,
    ctx: RenderContext,
) -> None:
    """
    Apply vertical positioning rules during layout pass.

    Calculates top position for the child. Similar to apply_vertical_size_rules
    but handles centering rules (which require final parent size).
    """
    attrs = child.attributes
    margins = get_margins(attrs, ctx)

    # Handle centering first (applies if no other vertical rules)
    has_vertical_rule = any(attrs.get(rule) for rule in [
        ABOVE, BELOW, ALIGN_TOP, ALIGN_BOTTOM,
        ALIGN_PARENT_TOP, ALIGN_PARENT_BOTTOM
    ])

    if not has_vertical_rule:
        if deref_bool(attrs.get(CENTER_IN_PARENT), ctx) or deref_bool(attrs.get(CENTER_VERTICAL), ctx):
            # Center vertically within parent
            available_height = parent_height - padding.top - padding.bottom - margins.top - margins.bottom
            bounds.top = padding.top + margins.top + (available_height - child.height) // 2
            return

    # Apply parent alignment rules (lowest priority)
    if deref_bool(attrs.get(ALIGN_PARENT_TOP), ctx):
        bounds.top = padding.top + margins.top

    if deref_bool(attrs.get(ALIGN_PARENT_BOTTOM), ctx):
        bounds.top = parent_height - padding.bottom - margins.bottom - child.height

    # Apply sibling alignment rules (medium priority)
    ref = get_referenced_view(attrs.get(ALIGN_TOP), id_to_child)
    if ref and bounds.top == -1:
        ref_bounds = all_child_bounds[id(ref)]
        ref_top = ref_bounds.top if ref_bounds.top != -1 else padding.top
        bounds.top = ref_top

    ref = get_referenced_view(attrs.get(ALIGN_BOTTOM), id_to_child)
    if ref and bounds.top == -1:
        ref_bounds = all_child_bounds[id(ref)]
        ref_top = ref_bounds.top if ref_bounds.top != -1 else padding.top
        bounds.top = ref_top + ref.height - child.height

    # Apply sibling positioning rules (highest priority)
    ref = get_referenced_view(attrs.get(ABOVE), id_to_child)
    if ref:
        ref_bounds = all_child_bounds[id(ref)]
        ref_margins = get_margins(ref.attributes, ctx)
        ref_top = ref_bounds.top if ref_bounds.top != -1 else padding.top
        bounds.top = ref_top - margins.bottom - child.height - ref_margins.top

    ref = get_referenced_view(attrs.get(BELOW), id_to_child)
    if ref:
        ref_bounds = all_child_bounds[id(ref)]
        ref_margins = get_margins(ref.attributes, ctx)
        ref_top = ref_bounds.top if ref_bounds.top != -1 else padding.top
        bounds.top = ref_top + ref.height + ref_margins.bottom + margins.top
