from PIL import ImageFont
from models import FontConfig

def dimension_to_pixels_size(value: float) -> int:
    """For width/height - round, ensure non-zero stays non-zero"""
    res = int(value + 0.5)
    if res != 0:
        return res
    if value == 0:
        return 0
    return 1 if value > 0 else -1

def dimension_to_pixels_offset(value: float) -> int:
    """For x/y/margins - truncate"""
    return int(value)

def calculate_text_bounds(
    text: str,
    typeface: str | None,
    text_style: str | None,
    text_size: int,
    font_config: FontConfig,
    letter_spacing: float | None = None,
    line_spacing_extra: int | None = None,
    line_spacing_multiplier: float | None = None,
    max_width: int | None = None,
    use_single_line: bool = False,
) -> tuple[int, int]:
    """Returns (width, height) of rendered text."""
    
    if letter_spacing is not None:
        print(f"Warning: letter_spacing={letter_spacing} ignored (not implemented)")
    
    if line_spacing_extra is not None:
        print(f"Warning: line_spacing_extra={line_spacing_extra} ignored (not implemented)")
    
    if line_spacing_multiplier is not None:
        print(f"Warning: line_spacing_multiplier={line_spacing_multiplier} ignored (not implemented)")
    
    if max_width is not None and not use_single_line:
        print(f"Warning: text wrapping not implemented (max_width={max_width}, use_single_line={use_single_line})")
    
    path = font_config.resolve_font(typeface, text_style)
    
    if not path.exists():
        raise FileNotFoundError(f"Font file not found: {path}")
    
    if path.suffix.lower() not in (".ttf", ".otf"):
        raise ValueError(f"Unsupported font format: {path}")
    
    font = ImageFont.truetype(str(path), text_size)
    bbox = font.getbbox(text)  # (left, top, right, bottom)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    return (width, height)

def map_custom_view_tag_to_aosp_view_tag(custom_view_tag: str) -> str:
    # E.g.:
    # - given ImageViewExtState, returns ImageView
    # - given AutoAdjustTextView, returns TextView
    raise NotImplementedError()
