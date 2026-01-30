"""
Parse and resolve Android styles and themes.

Handles style inheritance, theme attribute resolution, and proper
cascading of items across app and framework styles.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

# Import Style from models to avoid duplication
import sys
from pathlib import Path as PathType
# Ensure models can be imported (it's in the same directory)
from models import Style


def parse_styles_xml(xml_path: Path) -> dict[str, Style]:
    """
    Parse styles.xml and return a mapping of style names to Style objects.

    Example styles.xml:
        <style name="AppTheme" parent="@android:style/Theme">
            <item name="colorPrimary">#3F51B5</item>
        </style>

    Returns:
        {"AppTheme": Style(name="AppTheme", parent="@android:style/Theme", ...)}
    """
    if not xml_path.exists():
        return {}

    tree = ET.parse(xml_path)
    root = tree.getroot()

    styles = {}
    for style_elem in root.findall("style"):
        name = style_elem.get("name")
        if not name:
            continue

        parent = style_elem.get("parent")

        # Parse item elements
        items = {}
        for item_elem in style_elem.findall("item"):
            item_name = item_elem.get("name")
            item_value = item_elem.text or ""
            if item_name:
                items[item_name] = item_value

        styles[name] = Style(
            name=name,
            parent=parent,
            items=items
        )

    return styles


def resolve_style_reference(ref: str) -> tuple[str, bool]:
    """
    Parse a style reference and return (style_name, is_framework).

    Examples:
        "@style/MyStyle" -> ("MyStyle", False)
        "@android:style/Widget.Button" -> ("Widget.Button", True)
        "Widget.Button" -> ("Widget.Button", False)  # Implicit app reference
    """
    if ref.startswith("@android:style/"):
        return (ref[15:], True)
    elif ref.startswith("@style/"):
        return (ref[7:], False)
    elif ref.startswith("?android:style/"):
        return (ref[15:], True)
    elif ref.startswith("?style/"):
        return (ref[7:], False)
    else:
        # No prefix - assume app style
        return (ref, False)


def get_style_chain(
    style_ref: str,
    app_styles: dict[str, Style],
    framework_styles: dict[str, Style],
    visited: Optional[set[str]] = None
) -> dict[str, str]:
    """
    Resolve a style reference and return all items with inheritance.

    This walks up the parent chain and merges items, with child
    items taking precedence over parent items.

    Args:
        style_ref: Style reference like "@style/MyStyle" or "@android:style/Theme"
        app_styles: App styles registry
        framework_styles: Framework styles registry
        visited: Set of visited styles (for cycle detection)

    Returns:
        Dictionary of all resolved items
    """
    if visited is None:
        visited = set()

    # Parse the reference
    style_name, is_framework = resolve_style_reference(style_ref)

    # Detect cycles
    full_ref = f"{'framework' if is_framework else 'app'}:{style_name}"
    if full_ref in visited:
        print(f"Warning: Circular style reference detected: {full_ref}")
        return {}
    visited.add(full_ref)

    # Look up the style
    styles_dict = framework_styles if is_framework else app_styles
    style = styles_dict.get(style_name)

    if not style:
        # Try the other registry as fallback
        other_dict = app_styles if is_framework else framework_styles
        style = other_dict.get(style_name)
        if not style:
            print(f"Warning: Style not found: {style_ref}")
            return {}

    # Start with parent items (if any)
    resolved = {}
    if style.parent:
        parent_attrs = get_style_chain(style.parent, app_styles, framework_styles, visited)
        resolved.update(parent_attrs)

    # Override with this style's items
    resolved.update(style.items)

    return resolved


def resolve_theme_attribute(
    attr_name: str,
    theme_name: str,
    app_styles: dict[str, Style],
    framework_styles: dict[str, Style]
) -> Optional[str]:
    """
    Resolve a theme attribute reference like ?attr/colorPrimary.

    This looks up the attribute in the current theme and walks up
    the theme's parent chain if needed.

    Args:
        attr_name: Attribute name (without ? prefix)
        theme_name: Current theme name (e.g., "AppTheme")
        app_styles: App styles registry
        framework_styles: Framework styles registry

    Returns:
        Resolved value or None if not found
    """
    if not theme_name:
        return None

    # Determine if looking for framework attr or app attr
    if attr_name.startswith("android:"):
        # ?android:attr/foo -> look in framework theme
        attr_name = attr_name[8:]  # Remove "android:" prefix
        # Get theme items from framework
        theme_ref = f"@android:style/{theme_name}"
    else:
        # ?attr/foo -> look in app theme first
        theme_ref = f"@style/{theme_name}"

    # Get all theme items (with inheritance)
    theme_attrs = get_style_chain(theme_ref, app_styles, framework_styles)

    # Look up the attribute
    return theme_attrs.get(attr_name)


def load_all_styles(res_dir: Path) -> dict[str, Style]:
    """
    Load all styles from a res/ directory.

    This includes styles from:
    - res/values/styles.xml
    - res/values-*/styles.xml (TODO: handle qualifiers)

    Returns:
        Dictionary mapping style names to Style objects
    """
    all_styles = {}

    # Load from values/styles.xml
    values_dir = res_dir / "values"
    if values_dir.exists():
        styles_xml = values_dir / "styles.xml"
        if styles_xml.exists():
            styles = parse_styles_xml(styles_xml)
            all_styles.update(styles)

    # TODO: Load from qualified directories (values-v21, values-night, etc.)

    return all_styles
