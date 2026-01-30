"""
Parse XML drawable files (StateListDrawable, etc.)

Android supports various XML-based drawables that define visual elements
programmatically. This module handles parsing and resolving them to actual images.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Tuple


def parse_selector_drawable(xml_path: Path, app_drawables: dict[str, Path], framework_drawables: dict[str, Path]) -> Optional[Path]:
    """
    Parse a StateListDrawable (selector) XML file and return the default drawable.

    StateListDrawable defines different drawables for different states (pressed, focused, etc.).
    For static rendering, we use the default state (last item without state conditions).

    Example XML:
        <selector xmlns:android="http://schemas.android.com/apk/res/android">
            <item android:state_pressed="true" android:drawable="@drawable/btn_pressed"/>
            <item android:state_focused="true" android:drawable="@drawable/btn_focused"/>
            <item android:drawable="@drawable/btn_normal"/>
        </selector>

    Args:
        xml_path: Path to the selector XML file
        app_drawables: App drawable mapping
        framework_drawables: Framework drawable mapping

    Returns:
        Path to the default drawable, or None if parsing fails
    """
    if not xml_path.exists():
        return None

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Check if this is a selector (StateListDrawable)
        if root.tag != 'selector':
            return None

        # Find all items
        items = root.findall('item')
        if not items:
            return None

        # Look for the default item (no state attributes, typically last)
        # Android uses the first matching item, so we iterate in order
        default_item = None
        for item in items:
            # Check if this item has any state attributes
            has_state = any(attr.startswith('state_') for attr in item.attrib.keys()
                          if attr.startswith('{http://schemas.android.com/apk/res/android}state_') or attr.startswith('android:state_'))

            if not has_state:
                # This is a default item (no state conditions)
                default_item = item
                break

        # If no default item found, use the last item
        if default_item is None:
            default_item = items[-1]

        # Get the drawable reference
        drawable_ref = default_item.get('{http://schemas.android.com/apk/res/android}drawable') or \
                       default_item.get('android:drawable')

        if not drawable_ref:
            return None

        # Resolve the drawable reference
        return resolve_drawable_reference(drawable_ref, app_drawables, framework_drawables)

    except Exception as e:
        print(f"Warning: Failed to parse selector drawable {xml_path}: {e}")
        return None


def get_selector_default_reference(xml_path: Path) -> Optional[str]:
    """
    Parse a StateListDrawable (selector) XML file and return the default reference.

    This returns the raw reference string (e.g., "@drawable/foo" or "@color/bar")
    without resolving it, allowing the caller to handle both drawables and colors.

    Args:
        xml_path: Path to the selector XML file

    Returns:
        Reference string, or None if parsing fails
    """
    if not xml_path.exists():
        return None

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Check if this is a selector (StateListDrawable)
        if root.tag != 'selector':
            return None

        # Find all items
        items = root.findall('item')
        if not items:
            return None

        # Look for the default item (no state attributes, typically last)
        default_item = None
        for item in items:
            # Check if this item has any state attributes
            has_state = any(
                attr.startswith('{http://schemas.android.com/apk/res/android}state_') or attr.startswith('android:state_')
                for attr in item.attrib.keys()
            )

            if not has_state:
                # This is a default item (no state conditions)
                default_item = item
                break

        # If no default item found, use the last item
        if default_item is None:
            default_item = items[-1]

        # Get the drawable reference (could be @drawable or @color)
        ref = default_item.get('{http://schemas.android.com/apk/res/android}drawable') or \
              default_item.get('android:drawable')

        return ref

    except Exception as e:
        print(f"Warning: Failed to parse selector {xml_path}: {e}")
        return None


def resolve_drawable_reference(drawable_ref: str, app_drawables: dict[str, Path], framework_drawables: dict[str, Path]) -> Optional[Path]:
    """
    Resolve a drawable reference to its file path.

    Args:
        drawable_ref: Drawable reference like "@drawable/ic_launcher" or "@android:drawable/ic_menu"
        app_drawables: App drawable mapping
        framework_drawables: Framework drawable mapping

    Returns:
        Path to the drawable file, or None if not found
    """
    if not drawable_ref or not drawable_ref.startswith('@'):
        return None

    # Strip @ prefix
    ref = drawable_ref[1:]

    # Check if it's a framework drawable
    if ref.startswith('android:drawable/'):
        drawable_name = ref[len('android:drawable/'):]
        return framework_drawables.get(drawable_name)
    elif ref.startswith('drawable/'):
        drawable_name = ref[len('drawable/'):]
        # Check app drawables first, then framework
        path = app_drawables.get(drawable_name)
        if path is None:
            path = framework_drawables.get(drawable_name)
        return path

    return None


def get_drawable_intrinsic_size(xml_path: Path, app_drawables: dict[str, Path], framework_drawables: dict[str, Path]) -> Optional[Tuple[int, int]]:
    """
    Get the intrinsic size of an XML drawable.

    For StateListDrawable, returns the size of the default drawable.

    Args:
        xml_path: Path to the XML drawable file
        app_drawables: App drawable mapping
        framework_drawables: Framework drawable mapping

    Returns:
        Tuple of (width, height) in pixels, or None if size cannot be determined
    """
    # For now, try to parse as selector and get default drawable size
    drawable_path = parse_selector_drawable(xml_path, app_drawables, framework_drawables)
    if not drawable_path:
        return None

    # If the resolved drawable is an image, load it and get size
    if drawable_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
        try:
            from PIL import Image
            img = Image.open(drawable_path)
            # For 9-patch, return content size (minus 2px border)
            if drawable_path.name.endswith('.9.png'):
                return (img.width - 2, img.height - 2)
            return (img.width, img.height)
        except Exception:
            return None

    return None
