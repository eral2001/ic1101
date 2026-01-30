
from pathlib import Path
from PIL import Image
import re
from models import Margins, Padding, RenderContext, Dimension, DimensionMatchParent, DimensionPixels, DimensionWrapContent, Style
from text_utils import dimension_to_pixels_size, dimension_to_pixels_offset
from gravity import parse_gravity, Gravity
from drawable_xml_parser import get_drawable_intrinsic_size

DIMENSION_PATTERN = re.compile(r'^(-?\d+(?:\.\d+)?)(px|dp|dip|sp|pt|in|mm)?$')

def deref_dimension(value: str | None, ctx: RenderContext) -> Dimension:
    if value is None:
        return DimensionWrapContent()
    
    if value in ("match_parent", "fill_parent"):
        return DimensionMatchParent()
    
    if value == "wrap_content":
        return DimensionWrapContent()
    
    # App dimen reference
    if value.startswith("@dimen/"):
        resolved = ctx.app_dimens.get(value[7:])
        if resolved is None:
            print(f"Warning: Unknown app dimen: {value}")
            return DimensionWrapContent()
        return deref_dimension(resolved, ctx)

    # Framework dimen reference
    if value.startswith("@android:dimen/"):
        resolved = ctx.framework_dimens.get(value[15:])
        if resolved is None:
            print(f"Warning: Unknown framework dimen: {value}")
            return DimensionWrapContent()
        return deref_dimension(resolved, ctx)
    
    # Theme attribute reference
    if value.startswith("?android:"):
        attr_name = value[9:]
        resolved = ctx.resolve_theme_attr(attr_name)
        if resolved is None:
            raise ValueError(f"Unknown theme attr: {value}")
        return deref_dimension(resolved, ctx)
    
    if value.startswith("?attr/"):
        attr_name = value[6:]
        resolved = ctx.resolve_theme_attr(attr_name)
        if resolved is None:
            raise ValueError(f"Unknown theme attr: {value}")
        return deref_dimension(resolved, ctx)

    if value.startswith("?"):
        attr_name = value[1:]
        resolved = ctx.resolve_theme_attr(attr_name)
        if resolved is None:
            print(f"Warning: theme attr not found: {value}")
            return DimensionWrapContent()
        return deref_dimension(resolved, ctx)

    # Literal value with optional unit
    match = DIMENSION_PATTERN.match(value)
    if match:
        numeric = float(match.group(1))
        unit = match.group(2)

        if unit in (None, "px"):
            return DimensionPixels(numeric)
        elif unit in ("dp", "dip"):
            return DimensionPixels(numeric * ctx.density)
        elif unit == "sp":
            return DimensionPixels(numeric * ctx.density * ctx.font_scale)
        elif unit == "pt":
            # 1pt = 1/72 inch, and 1 inch = 160dp at baseline density
            # So 1pt = (1/72) * 160 * density ≈ 2.222 * density pixels
            return DimensionPixels(numeric * ctx.density * (160.0 / 72.0))
        elif unit == "in":
            # 1 inch = 160dp at baseline density
            return DimensionPixels(numeric * ctx.density * 160.0)
        elif unit == "mm":
            # 1mm = 1/25.4 inches
            return DimensionPixels(numeric * ctx.density * 160.0 / 25.4)

    raise ValueError(f"Cannot parse dimension: {value}")

def deref_dimension_to_pixels(value: str | None, ctx: RenderContext, default: int) -> int:
    """
    Resolve a dimension reference to pixels for sizes (width/height/minWidth/textSize).
    Uses rounding, ensures non-zero stays non-zero.
    Returns default if None, match_parent, or wrap_content.
    """
    if value is None:
        return default
    
    dim = deref_dimension(value, ctx)
    
    match dim:
        case DimensionPixels(v):
            return dimension_to_pixels_size(v)
        case DimensionMatchParent():
            print(f"Warning: 'match_parent' invalid where pixel value expected: {value}")
            return default
        case DimensionWrapContent():
            print(f"Warning: 'wrap_content' invalid where pixel value expected: {value}")
            return default
        case _:
            print(f"Warning: unexpected dimension type {dim} for '{value}'")
            return default

def deref_dimension_to_offset(value: str | None, ctx: RenderContext, default: int) -> int:
    """
    Resolve a dimension reference to pixels for offsets (x/y/padding/margins).
    Uses truncation.
    Returns default if None, match_parent, or wrap_content.
    """
    if value is None:
        return default
    
    dim = deref_dimension(value, ctx)
    
    match dim:
        case DimensionPixels(v):
            return dimension_to_pixels_offset(v)
        case DimensionMatchParent():
            print(f"Warning: 'match_parent' invalid where offset expected: {value}")
            return default
        case DimensionWrapContent():
            print(f"Warning: 'wrap_content' invalid where offset expected: {value}")
            return default
        case _:
            print(f"Warning: unexpected dimension type {dim} for '{value}'")
            return default

def deref_string(ref: str | None, ctx: RenderContext) -> str:
    """Resolve a string reference to its actual text content."""

    if ref is None:
        return ""

    # App string reference
    if ref.startswith("@string/"):
        name = ref[8:]
        resolved = ctx.app_strings.get(name)
        if resolved is None:
            print(f"Warning: string not found: {ref}")
            return ""
        return resolved
    
    # Framework string reference
    if ref.startswith("@android:string/"):
        name = ref[16:]
        resolved = ctx.framework_strings.get(name)
        if resolved is None:
            print(f"Warning: framework string not found: {ref}")
            return ""
        return resolved
    
    # Theme attribute references
    if ref.startswith("?android:"):
        attr_name = ref[9:]
        resolved = ctx.resolve_theme_attr(attr_name)
        if resolved is None:
            print(f"Warning: theme attr not found: {ref}")
            return ""
        return deref_string(resolved, ctx)
    
    if ref.startswith("?attr/"):
        attr_name = ref[6:]
        resolved = ctx.resolve_theme_attr(attr_name)
        if resolved is None:
            print(f"Warning: theme attr not found: {ref}")
            return ""
        return deref_string(resolved, ctx)
    
    if ref.startswith("?"):
        attr_name = ref[1:]
        resolved = ctx.resolve_theme_attr(attr_name)
        if resolved is None:
            print(f"Warning: theme attr not found: {ref}")
            return ""
        return deref_string(resolved, ctx)
    
    # Literal text
    return ref

def deref_bool(value: str | None, ctx: RenderContext, default: bool = False) -> bool:
    """
    Resolve a boolean attribute to a bool value.
    
    Handles literal "true"/"false", @bool/ references, and theme attributes.
    Returns default if not specified or on error.
    """
    if value is None:
        return default
    
    # Literal values
    if value == "true":
        return True
    if value == "false":
        return False
    
    # App bool reference
    if value.startswith("@bool/"):
        resolved = ctx.app_bools.get(value[6:])
        if resolved is None:
            print(f"Warning: unknown app bool: {value}")
            return default
        return deref_bool(resolved, ctx, default)
    
    # Framework bool reference
    if value.startswith("@android:bool/"):
        resolved = ctx.framework_bools.get(value[14:])
        if resolved is None:
            print(f"Warning: unknown framework bool: {value}")
            return default
        return deref_bool(resolved, ctx, default)
    
    # Theme attribute references
    if value.startswith("?android:"):
        resolved = ctx.resolve_theme_attr(value[9:])
        if resolved is None:
            print(f"Warning: theme attr not found: {value}")
            return default
        return deref_bool(resolved, ctx, default)
    
    if value.startswith("?attr/"):
        resolved = ctx.resolve_theme_attr(value[6:])
        if resolved is None:
            print(f"Warning: theme attr not found: {value}")
            return default
        return deref_bool(resolved, ctx, default)
    
    if value.startswith("?"):
        resolved = ctx.resolve_theme_attr(value[1:])
        if resolved is None:
            print(f"Warning: theme attr not found: {value}")
            return default
        return deref_bool(resolved, ctx, default)
    
    print(f"Warning: cannot parse bool value: {value}")
    return default

def deref_color(value: str | None, ctx: RenderContext) -> tuple[int, int, int, int] | None:
    """
    Resolve a color attribute to an RGBA tuple.

    Handles literal hex colors (#RRGGBB, #AARRGGBB), @color/ references,
    and theme attributes.

    Returns:
        RGBA tuple (r, g, b, a) with values 0-255, or None if not found
    """
    if value is None:
        return None

    # Literal hex color
    if value.startswith("#"):
        hex_color = value[1:]

        # #RGB
        if len(hex_color) == 3:
            r = int(hex_color[0] * 2, 16)
            g = int(hex_color[1] * 2, 16)
            b = int(hex_color[2] * 2, 16)
            return (r, g, b, 255)

        # #RRGGBB
        elif len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b, 255)

        # #AARRGGBB
        elif len(hex_color) == 8:
            a = int(hex_color[0:2], 16)
            r = int(hex_color[2:4], 16)
            g = int(hex_color[4:6], 16)
            b = int(hex_color[6:8], 16)
            return (r, g, b, a)

        else:
            print(f"Warning: invalid hex color format: {value}")
            return None

    # App color reference (with fallback to framework colors)
    if value.startswith("@color/"):
        name = value[7:]
        resolved = ctx.app_colors.get(name)
        # Fall back to framework colors if not found in app
        if resolved is None:
            resolved = ctx.framework_colors.get(name)
        if resolved is None:
            print(f"Warning: unknown color: {value}")
            return None
        return deref_color(resolved, ctx)

    # Framework color reference
    if value.startswith("@android:color/"):
        resolved = ctx.framework_colors.get(value[15:])
        if resolved is None:
            print(f"Warning: unknown framework color: {value}")
            return None
        return deref_color(resolved, ctx)

    # Theme attribute references
    if value.startswith("?android:"):
        resolved = ctx.resolve_theme_attr(value[9:])
        if resolved is None:
            print(f"Warning: theme attr not found: {value}")
            return None
        return deref_color(resolved, ctx)

    if value.startswith("?attr/"):
        resolved = ctx.resolve_theme_attr(value[6:])
        if resolved is None:
            print(f"Warning: theme attr not found: {value}")
            return None
        return deref_color(resolved, ctx)

    if value.startswith("?"):
        resolved = ctx.resolve_theme_attr(value[1:])
        if resolved is None:
            print(f"Warning: theme attr not found: {value}")
            return None
        return deref_color(resolved, ctx)

    print(f"Warning: cannot parse color value: {value}")
    return None

def deref_float(value: str | None, ctx: RenderContext) -> float | None:
    """
    Follow dimen refs and parse to float.
    Used for letterSpacing, lineSpacingMultiplier, alpha, etc.
    Returns None if not specified or on error.
    """
    if value is None:
        return None
    
    # App dimen reference
    if value.startswith("@dimen/"):
        resolved = ctx.app_dimens.get(value[7:])
        if resolved is None:
            print(f"Warning: unknown app dimen: {value}")
            return None
        return deref_float(resolved, ctx)
    
    # Framework dimen reference
    if value.startswith("@android:dimen/"):
        resolved = ctx.framework_dimens.get(value[15:])
        if resolved is None:
            print(f"Warning: unknown framework dimen: {value}")
            return None
        return deref_float(resolved, ctx)
    
    # Theme attribute references
    if value.startswith("?android:"):
        resolved = ctx.resolve_theme_attr(value[9:])
        if resolved is None:
            print(f"Warning: theme attr not found: {value}")
            return None
        return deref_float(resolved, ctx)
    
    if value.startswith("?attr/"):
        resolved = ctx.resolve_theme_attr(value[6:])
        if resolved is None:
            print(f"Warning: theme attr not found: {value}")
            return None
        return deref_float(resolved, ctx)
    
    if value.startswith("?"):
        resolved = ctx.resolve_theme_attr(value[1:])
        if resolved is None:
            print(f"Warning: theme attr not found: {value}")
            return None
        return deref_float(resolved, ctx)
    
    # Literal float value
    try:
        return float(value)
    except ValueError:
        print(f"Warning: cannot parse float: {value}")
        return None

def deref_gravity(value: str | None, ctx: RenderContext, default: Gravity = Gravity.NONE) -> Gravity:
    """
    Resolve a gravity attribute, following theme references.
    
    Handles:
    - Literal values like "center|bottom"
    - ?attr/someGravity
    - ?android:attr/someGravity
    
    Returns default if None or not found.
    """
    if value is None:
        return default
    
    # Theme attribute references
    if value.startswith("?android:"):
        resolved = ctx.resolve_theme_attr(value[9:])
        if resolved is None:
            print(f"Warning: theme attr not found: {value}")
            return default
        return deref_gravity(resolved, ctx, default)
    
    if value.startswith("?attr/"):
        resolved = ctx.resolve_theme_attr(value[6:])
        if resolved is None:
            print(f"Warning: theme attr not found: {value}")
            return default
        return deref_gravity(resolved, ctx, default)
    
    if value.startswith("?"):
        resolved = ctx.resolve_theme_attr(value[1:])
        if resolved is None:
            print(f"Warning: theme attr not found: {value}")
            return default
        return deref_gravity(resolved, ctx, default)
    
    # Literal gravity value
    return parse_gravity(value, default)

def deref_drawable_path(ref: str, ctx: RenderContext) -> Path | None:
    """
    Follow drawable references to get the file path.
    Returns None if not found.
    """
    if ref.startswith("@drawable/"):
        name = ref[10:]
        # Check app drawables first, then fall back to framework
        path = ctx.app_drawables.get(name)
        if path is None:
            path = ctx.framework_drawables.get(name)
        return path

    if ref.startswith("@android:drawable/"):
        name = ref[18:]
        return ctx.framework_drawables.get(name)
    
    # Theme attribute references
    if ref.startswith("?android:"):
        resolved = ctx.resolve_theme_attr(ref[9:])
        if resolved is None:
            print(f"Warning: theme attr not found: {ref}")
            return None
        return deref_drawable_path(resolved, ctx)
    
    if ref.startswith("?attr/"):
        resolved = ctx.resolve_theme_attr(ref[6:])
        if resolved is None:
            print(f"Warning: theme attr not found: {ref}")
            return None
        return deref_drawable_path(resolved, ctx)
    
    if ref.startswith("?"):
        resolved = ctx.resolve_theme_attr(ref[1:])
        if resolved is None:
            print(f"Warning: theme attr not found: {ref}")
            return None
        return deref_drawable_path(resolved, ctx)
    
    print(f"Warning: unknown drawable reference format: {ref}")
    return None

def get_style_chain(ref: str, ctx: RenderContext) -> dict[str, str]:
    """
    Resolve a style reference and walk its inheritance chain.

    Returns a flattened dict of all items, with child values
    overriding parent values.

    Returns empty dict if style not found.
    """
    from style_parser import get_style_chain as get_style_chain_impl

    return get_style_chain_impl(ref, ctx.app_styles, ctx.framework_styles)

def get_padding(attributes: dict[str, str], ctx: RenderContext) -> Padding:
    general = attributes.get("android:padding")
    general_px = deref_dimension_to_offset(general, ctx, 0) if general is not None else 0

    def get_side(key: str) -> int:
        value = attributes.get(key)
        if value is not None:
            return deref_dimension_to_offset(value, ctx, 0)
        return general_px

    return Padding(
        left=get_side("android:paddingLeft"),
        right=get_side("android:paddingRight"),
        top=get_side("android:paddingTop"),
        bottom=get_side("android:paddingBottom"),
    )

def get_margins(attributes: dict[str, str], ctx: RenderContext) -> Margins:
    general = attributes.get("android:layout_margin")
    general_px = deref_dimension_to_offset(general, ctx, 0) if general is not None else 0

    def get_side(key: str) -> int:
        value = attributes.get(key)
        if value is not None:
            return deref_dimension_to_offset(value, ctx, 0)
        return general_px

    return Margins(
        left=get_side("android:layout_marginLeft"),
        right=get_side("android:layout_marginRight"),
        top=get_side("android:layout_marginTop"),
        bottom=get_side("android:layout_marginBottom"),
    )

def get_drawable_size(ref: str, ctx: RenderContext) -> tuple[int, int]:
    """Get intrinsic dimensions of a drawable. Returns (0, 0) if unknown."""
    
    path = deref_drawable_path(ref, ctx)
    
    if path is None:
        print(f"Warning: drawable not found: {ref}")
        return (0, 0)

    if not path.exists():
        print(f"Warning: drawable file missing: {path}")
        return (0, 0)
    
    suffix = path.suffix.lower()
    
    # Nine-patch: 1px border on each side
    if path.name.endswith(".9.png"):
        with Image.open(path) as img:
            width = max(0, img.width - 2)
            height = max(0, img.height - 2)
            if width == 0 or height == 0:
                print(f"Warning: nine-patch too small: {path} ({img.width}x{img.height} raw)")
            return (width, height)
    
    # Regular image
    if suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        with Image.open(path) as img:
            if img.width == 0 or img.height == 0:
                print(f"Warning: zero-dimension image: {path} ({img.width}x{img.height})")
            return (img.width, img.height)
    
    # XML drawable (StateListDrawable, vector graphics, shape drawables, etc.)
    if suffix == ".xml":
        # Try to get intrinsic size from the XML drawable
        size = get_drawable_intrinsic_size(path, ctx.app_drawables, ctx.framework_drawables)
        if size:
            return size
        # If parsing failed, return a reasonable default size (24dp is a common icon size)
        print(f"Warning: XML drawable sizing not implemented, using default 24x24: {path}")
        return (24, 24)

    print(f"Warning: unknown drawable type: {path}")
    return (0, 0)

def get_text_size(value: str | int | None, ctx: RenderContext, default: int = 14) -> int:
    """Resolve textSize, handling the case where it's already an int from defaults.

    Raw int values (from TEXTVIEW_DEFAULTS) and the default are treated as sp,
    so density and font_scale are applied. String values like "14sp" are handled
    by deref_dimension_to_pixels which already applies these factors.
    """
    if value is None:
        return int(default * ctx.density * ctx.font_scale)
    if isinstance(value, int):
        return int(value * ctx.density * ctx.font_scale)
    return deref_dimension_to_pixels(value, ctx, int(default * ctx.density * ctx.font_scale))

def lookup_style(ref: str, ctx: RenderContext) -> Style | None:
    """
    Parse a style reference and return the Style object.
    
    Handles:
    - @style/Foo           → app style
    - @android:style/Foo   → framework style
    - ?attr/foo            → theme attr → style
    - ?android:attr/foo    → theme attr → style
    - ?foo                 → theme attr → style
    
    Returns None if not found.
    """
    raise NotImplementedError()
