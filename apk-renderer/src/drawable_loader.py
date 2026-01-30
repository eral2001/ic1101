"""
Utilities for discovering and loading drawable resources.
"""

from pathlib import Path
from typing import Optional
from PIL import Image
from drawable_xml_parser import parse_selector_drawable


def discover_drawables(res_dir: Path) -> dict[str, Path]:
    """
    Discover all drawable resources in a res/ directory.

    Scans all drawable-* folders and builds a mapping from resource name to file path.
    For resources with multiple densities, prefers higher density versions.

    Args:
        res_dir: Path to the res/ directory (e.g., "apk/res" or "/system/framework/res")

    Returns:
        Dictionary mapping drawable resource names to their file paths
        Example: {"ic_launcher": Path("res/drawable-hdpi/ic_launcher.png")}
    """
    drawables: dict[str, tuple[Path, int]] = {}  # name -> (path, priority)

    # Density priority (higher is better)
    density_priority = {
        "xxxhdpi": 5,
        "xxhdpi": 4,
        "xhdpi": 3,
        "hdpi": 2,
        "mdpi": 1,
        "ldpi": 0,
        "": 1,  # Default drawable/ folder has mdpi priority
    }

    if not res_dir.exists():
        return {}

    # Scan all drawable-* directories
    for drawable_dir in res_dir.glob("drawable*"):
        if not drawable_dir.is_dir():
            continue

        # Extract density qualifier from directory name
        # e.g., "drawable-hdpi" -> "hdpi", "drawable" -> ""
        dir_name = drawable_dir.name
        if dir_name == "drawable":
            density = ""
        elif dir_name.startswith("drawable-"):
            density = dir_name.split("-", 1)[1]
            # Handle compound qualifiers like "drawable-hdpi-v4"
            # Take just the first part as density
            density = density.split("-")[0]
        else:
            density = ""

        priority = density_priority.get(density, 1)

        # Scan all files in this directory
        for drawable_file in drawable_dir.iterdir():
            if not drawable_file.is_file():
                continue

            # Get resource name (filename without extension)
            # Handle 9-patch files specially: "foo.9.png" -> "foo"
            if drawable_file.name.endswith(".9.png"):
                resource_name = drawable_file.name[:-6]  # Remove ".9.png"
            else:
                resource_name = drawable_file.stem

            # Only keep if this is higher priority than existing
            if resource_name not in drawables or priority > drawables[resource_name][1]:
                drawables[resource_name] = (drawable_file, priority)

    # Return just the paths, not the priorities
    return {name: path for name, (path, _) in drawables.items()}


def load_drawable_image(drawable_path: Path) -> Optional[Image.Image]:
    """
    Load a drawable image from disk.

    Args:
        drawable_path: Path to the drawable file (PNG, JPG, etc.)

    Returns:
        PIL Image object, or None if loading failed
    """
    if not drawable_path.exists():
        return None

    try:
        # Load image with PIL
        img = Image.open(drawable_path)

        # Convert to RGBA for consistent handling
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        return img
    except Exception as e:
        print(f"Warning: Failed to load drawable {drawable_path}: {e}")
        return None


def get_drawable_path(
    drawable_ref: str,
    app_drawables: dict[str, Path],
    framework_drawables: dict[str, Path]
) -> Optional[Path]:
    """
    Resolve a drawable reference to its file path.

    If the drawable is an XML file (e.g., StateListDrawable), this will
    parse it and resolve to the actual image file.

    Args:
        drawable_ref: Drawable reference like "@drawable/ic_launcher" or "@android:drawable/ic_menu_add"
        app_drawables: App drawable mapping
        framework_drawables: Framework drawable mapping

    Returns:
        Path to the drawable file, or None if not found
    """
    if not drawable_ref or not drawable_ref.startswith("@"):
        return None

    # Strip @ prefix
    ref = drawable_ref[1:]

    # Check if it's a framework drawable
    path = None
    if ref.startswith("android:drawable/"):
        drawable_name = ref[len("android:drawable/"):]
        path = framework_drawables.get(drawable_name)
    elif ref.startswith("drawable/"):
        drawable_name = ref[len("drawable/"):]
        # Check app drawables first, then framework drawables
        # (Framework themes often reference drawables as @drawable/foo without android: prefix)
        path = app_drawables.get(drawable_name)
        if path is None:
            path = framework_drawables.get(drawable_name)

    if path is None:
        return None

    # If it's an XML file, try to parse it as a StateListDrawable
    if path.suffix.lower() == '.xml':
        resolved_path = parse_selector_drawable(path, app_drawables, framework_drawables)
        if resolved_path:
            return resolved_path
        # If parsing failed, return None (can't render XML directly)
        return None

    return path
