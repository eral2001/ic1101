from models import MeasureSpec, RenderContext, View
from registry import Registry


def measure(view: View, width_spec: MeasureSpec, height_spec: MeasureSpec, ctx: RenderContext, registry: Registry) -> None:
    """
    Measure a view and set its width/height.

    Delegates to registered view-specific measurement functions.

    Args:
        view: The view to measure
        width_spec: Width constraint from parent
        height_spec: Height constraint from parent
        ctx: Rendering context with resources and configuration
        registry: Unified view registry
    """
    visibility = view.attributes.get("android:visibility", "visible")
    if visibility == "gone":
        view.width = 0
        view.height = 0
        return

    # Look up measurement function for this view type
    entry = registry.get(view.tag)

    if entry is not None:
        measure_func = entry.measure
    else:
        # Try to find a fallback for custom views
        # Custom views often inherit from standard views (e.g., ImageViewExtState extends ImageView)
        measure_func = None
        if "ImageView" in view.tag:
            fallback = registry.get("ImageView")
            if fallback:
                measure_func = fallback.measure
                print(f"Warning: Unknown view '{view.tag}', falling back to ImageView measurement")
        elif "TextView" in view.tag or "Button" in view.tag:
            fallback = registry.get("TextView")
            if fallback:
                measure_func = fallback.measure
                print(f"Warning: Unknown view '{view.tag}', falling back to TextView measurement")
        else:
            fallback = registry.get("View")
            if fallback:
                measure_func = fallback.measure
                print(f"Warning: Unknown view '{view.tag}', falling back to generic View measurement")

        if measure_func is None:
            raise NotImplementedError(f"No measurement function registered for view type '{view.tag}'")

    # Create a closure that captures the registry for recursive measurement
    def measure_child(child: View, child_width_spec: MeasureSpec, child_height_spec: MeasureSpec, child_ctx: RenderContext) -> None:
        measure(child, child_width_spec, child_height_spec, child_ctx, registry)

    measure_func(view, width_spec, height_spec, ctx, measure_child)
