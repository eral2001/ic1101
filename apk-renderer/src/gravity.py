from enum import IntFlag

class Gravity(IntFlag):
    """
    Android gravity flags. Can be combined with | operator.
    
    Matches Android's Gravity.java constants.
    """
    NONE = 0x0000
    
    # Horizontal axis
    LEFT = 0x03
    RIGHT = 0x05
    CENTER_HORIZONTAL = 0x01
    FILL_HORIZONTAL = 0x07
    
    # Vertical axis
    TOP = 0x30
    BOTTOM = 0x50
    CENTER_VERTICAL = 0x10
    FILL_VERTICAL = 0x70
    
    # Combined
    CENTER = 0x11  # CENTER_HORIZONTAL | CENTER_VERTICAL
    FILL = 0x77    # FILL_HORIZONTAL | FILL_VERTICAL
    
    # RTL-aware (these resolve to LEFT/RIGHT based on layout direction)
    RELATIVE_LAYOUT_DIRECTION = 0x00800000
    START = 0x00800003  # RELATIVE_LAYOUT_DIRECTION | LEFT
    END = 0x00800005    # RELATIVE_LAYOUT_DIRECTION | RIGHT

# Axis masks for extracting horizontal/vertical components
HORIZONTAL_GRAVITY_MASK = 0x07
VERTICAL_GRAVITY_MASK = 0x70

# Map of string names to gravity values
GRAVITY_MAP: dict[str, Gravity] = {
    "top": Gravity.TOP,
    "bottom": Gravity.BOTTOM,
    "left": Gravity.LEFT,
    "right": Gravity.RIGHT,
    "center": Gravity.CENTER,
    "center_vertical": Gravity.CENTER_VERTICAL,
    "center_horizontal": Gravity.CENTER_HORIZONTAL,
    "fill": Gravity.FILL,
    "fill_vertical": Gravity.FILL_VERTICAL,
    "fill_horizontal": Gravity.FILL_HORIZONTAL,
    "start": Gravity.START,
    "end": Gravity.END,
    "clip_vertical": Gravity.NONE,  # We don't implement clipping
    "clip_horizontal": Gravity.NONE,
}

def parse_gravity(value: str | None, default: Gravity = Gravity.NONE) -> Gravity:
    """
    Parse a gravity string like "center|bottom" or "top|left".
    
    Returns combined flags, or default if None or invalid.
    """
    if value is None:
        return default
    
    result = Gravity.NONE
    
    for part in value.split("|"):
        part = part.strip().lower()
        if part in GRAVITY_MAP:
            result |= GRAVITY_MAP[part]
        else:
            print(f"Warning: unknown gravity value '{part}'")
    
    return result if result != Gravity.NONE else default

def get_horizontal_gravity(gravity: Gravity) -> Gravity:
    """Extract just the horizontal component of gravity."""
    return Gravity(gravity & HORIZONTAL_GRAVITY_MASK)

def get_vertical_gravity(gravity: Gravity) -> Gravity:
    """Extract just the vertical component of gravity."""
    return Gravity(gravity & VERTICAL_GRAVITY_MASK)

def apply_gravity(
    gravity: Gravity,
    content_width: int,
    content_height: int,
    container_left: int,
    container_top: int,
    container_right: int,
    container_bottom: int,
    is_rtl: bool = False,
) -> tuple[int, int, int, int]:
    """
    Apply gravity to position content within a container.
    
    Returns (left, top, right, bottom) of the positioned content.
    
    This mirrors Android's Gravity.apply().
    """
    container_width = container_right - container_left
    container_height = container_bottom - container_top
    
    # Resolve RTL-aware gravity
    resolved_gravity = resolve_gravity_rtl(gravity, is_rtl)
    
    h_gravity = get_horizontal_gravity(resolved_gravity)
    v_gravity = get_vertical_gravity(resolved_gravity)
    
    # Horizontal positioning
    if h_gravity == Gravity.FILL_HORIZONTAL:
        out_left = container_left
        out_right = container_right
    elif h_gravity == Gravity.RIGHT:
        out_right = container_right
        out_left = out_right - content_width
    elif h_gravity == Gravity.CENTER_HORIZONTAL:
        out_left = container_left + (container_width - content_width) // 2
        out_right = out_left + content_width
    else:  # LEFT or default
        out_left = container_left
        out_right = out_left + content_width
    
    # Vertical positioning
    if v_gravity == Gravity.FILL_VERTICAL:
        out_top = container_top
        out_bottom = container_bottom
    elif v_gravity == Gravity.BOTTOM:
        out_bottom = container_bottom
        out_top = out_bottom - content_height
    elif v_gravity == Gravity.CENTER_VERTICAL:
        out_top = container_top + (container_height - content_height) // 2
        out_bottom = out_top + content_height
    else:  # TOP or default
        out_top = container_top
        out_bottom = out_top + content_height
    
    return (out_left, out_top, out_right, out_bottom)

def resolve_gravity_rtl(gravity: Gravity, is_rtl: bool) -> Gravity:
    """
    Resolve START/END to LEFT/RIGHT based on layout direction.
    """
    if not (gravity & Gravity.RELATIVE_LAYOUT_DIRECTION):
        return gravity
    
    # Has relative flag, resolve it
    h_gravity = get_horizontal_gravity(gravity)
    
    if h_gravity == Gravity.START:
        resolved_h = Gravity.RIGHT if is_rtl else Gravity.LEFT
    elif h_gravity == Gravity.END:
        resolved_h = Gravity.LEFT if is_rtl else Gravity.RIGHT
    else:
        resolved_h = h_gravity
    
    # Replace horizontal component
    return Gravity((gravity & VERTICAL_GRAVITY_MASK) | resolved_h)
