"""
9-patch image rendering support.

9-patch images are special PNG files with 1-pixel borders that define
how the image should be stretched to fit different sizes.
"""

from PIL import Image
from pathlib import Path


def is_ninepatch(path: Path) -> bool:
    """Check if a file is a 9-patch image (ends with .9.png)."""
    return path.name.endswith('.9.png')


def _parse_stretch_regions(border_pixels: list, content_size: int) -> list[tuple[int, int, bool]]:
    """
    Parse a border (top or left) to find stretchable regions.

    Args:
        border_pixels: List of pixel values from the border
        content_size: Size of the content dimension

    Returns:
        List of (start, end, is_stretchable) tuples defining regions.
        Coordinates are relative to content area (0-based).
    """
    # Black pixel is (0,0,0,255) or similar dark color
    def is_black(pixel):
        # Check if RGB values are very dark (threshold of 32)
        return pixel[0] < 32 and pixel[1] < 32 and pixel[2] < 32

    regions = []
    i = 0

    while i < content_size:
        # Check if current position starts a stretchable region
        if is_black(border_pixels[i]):
            # Find the end of this stretchable region
            start = i
            while i < content_size and is_black(border_pixels[i]):
                i += 1
            regions.append((start, i, True))  # Stretchable
        else:
            # Find the end of this fixed region
            start = i
            while i < content_size and not is_black(border_pixels[i]):
                i += 1
            regions.append((start, i, False))  # Fixed

    return regions


def render_ninepatch(img: Image.Image, target_width: int, target_height: int) -> Image.Image:
    """
    Render a 9-patch image at the specified size.

    9-patch format:
    - 1-pixel border on all sides contains stretch/padding guides
    - Top border (black pixels) marks horizontally stretchable columns
    - Left border (black pixels) marks vertically stretchable rows
    - Right/bottom borders mark content padding (ignored for rendering)
    - Content is everything except the border

    This implementation properly parses the stretch regions and only
    stretches the marked areas, keeping fixed regions at original size.

    Args:
        img: 9-patch image (includes 1px border)
        target_width: Desired output width
        target_height: Desired output height

    Returns:
        Rendered image at target size
    """
    # Content dimensions (excluding 1px border on all sides)
    content_width = img.width - 2
    content_height = img.height - 2

    # Parse top border (y=0, x=1 to width-2) for horizontal stretch regions
    top_border = [img.getpixel((x, 0)) for x in range(1, img.width - 1)]
    h_regions = _parse_stretch_regions(top_border, content_width)

    # Parse left border (x=0, y=1 to height-2) for vertical stretch regions
    left_border = [img.getpixel((0, y)) for y in range(1, img.height - 1)]
    v_regions = _parse_stretch_regions(left_border, content_height)

    # If no stretch regions found, fall back to stretching everything
    if not h_regions:
        h_regions = [(0, content_width, True)]
    if not v_regions:
        v_regions = [(0, content_height, True)]

    # Calculate target sizes for each region
    # Fixed regions keep their original size
    # Stretchable regions share the remaining space

    def calculate_target_sizes(regions, target_size, content_size):
        """Calculate output size for each region."""
        fixed_total = sum(end - start for start, end, stretch in regions if not stretch)
        stretch_count = sum(1 for _, _, stretch in regions if stretch)
        stretch_total_source = sum(end - start for start, end, stretch in regions if stretch)

        available_for_stretch = target_size - fixed_total

        sizes = []
        for start, end, is_stretch in regions:
            source_size = end - start
            if is_stretch and stretch_total_source > 0:
                # Distribute available space proportionally
                target_size_for_region = int(available_for_stretch * source_size / stretch_total_source)
            else:
                # Keep fixed size
                target_size_for_region = source_size
            sizes.append(target_size_for_region)

        return sizes

    h_sizes = calculate_target_sizes(h_regions, target_width, content_width)
    v_sizes = calculate_target_sizes(v_regions, target_height, content_height)

    # Create output image
    output = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))

    # Composite each region
    dest_y = 0
    for v_idx, (v_start, v_end, v_stretch) in enumerate(v_regions):
        dest_x = 0
        for h_idx, (h_start, h_end, h_stretch) in enumerate(h_regions):
            # Extract source region from content (offset by 1 for border)
            source_region = img.crop((
                h_start + 1,  # +1 to skip left border
                v_start + 1,  # +1 to skip top border
                h_end + 1,
                v_end + 1
            ))

            # Resize to target size
            target_w = h_sizes[h_idx]
            target_h = v_sizes[v_idx]

            if target_w > 0 and target_h > 0:
                if source_region.size != (target_w, target_h):
                    resized = source_region.resize((target_w, target_h), Image.Resampling.LANCZOS)
                else:
                    resized = source_region

                # Paste into output
                output.paste(resized, (dest_x, dest_y))

            dest_x += target_w

        dest_y += v_sizes[v_idx]

    return output
