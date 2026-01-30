"""
Parse Android resource XML files (strings, dimens, colors, etc.)
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from style_parser import load_all_styles


def parse_strings_xml(xml_path: Path) -> dict[str, str]:
    """
    Parse strings.xml and return a mapping of string names to values.

    Handles both forms:
        <string name="app_name">MyApp</string>
        <item type="string" name="foo">@android:string/bar</item>
    """
    if not xml_path.exists():
        return {}

    tree = ET.parse(xml_path)
    root = tree.getroot()

    strings = {}
    for string_elem in root.findall("string"):
        name = string_elem.get("name")
        value = string_elem.text or ""
        if name:
            strings[name] = value

    for item_elem in root.findall("item"):
        if item_elem.get("type") == "string":
            name = item_elem.get("name")
            value = item_elem.text or ""
            if name:
                strings[name] = value

    return strings


def parse_dimens_xml(xml_path: Path) -> dict[str, str]:
    """
    Parse dimens.xml and return a mapping of dimen names to values.

    Handles both forms:
        <dimen name="activity_margin">16dp</dimen>
        <item type="dimen" name="foo">@android:dimen/bar</item>
    """
    if not xml_path.exists():
        return {}

    tree = ET.parse(xml_path)
    root = tree.getroot()

    dimens = {}
    for dimen_elem in root.findall("dimen"):
        name = dimen_elem.get("name")
        value = dimen_elem.text or ""
        if name:
            dimens[name] = value

    for item_elem in root.findall("item"):
        if item_elem.get("type") == "dimen":
            name = item_elem.get("name")
            value = item_elem.text or ""
            if name:
                dimens[name] = value

    return dimens


def parse_colors_xml(xml_path: Path) -> dict[str, str]:
    """
    Parse colors.xml and return a mapping of color names to values.

    Handles both forms:
        <color name="primary">#FF5722</color>
        <item type="color" name="foo">@android:color/bar</item>
    """
    if not xml_path.exists():
        return {}

    tree = ET.parse(xml_path)
    root = tree.getroot()

    colors = {}
    for color_elem in root.findall("color"):
        name = color_elem.get("name")
        value = color_elem.text or ""
        if name:
            colors[name] = value

    for item_elem in root.findall("item"):
        if item_elem.get("type") == "color":
            name = item_elem.get("name")
            value = item_elem.text or ""
            if name:
                colors[name] = value

    return colors


def _get_color_from_element(elem) -> str | None:
    """Extract a color value from a selector child element.

    Checks android:color first, then falls back to android:drawable
    (which can reference @color/ resources).
    """
    ns = '{http://schemas.android.com/apk/res/android}'
    color = elem.get(f'{ns}color') or elem.get('android:color')
    if color:
        return color
    # Some entries use android:drawable to reference a @color/ resource
    drawable = elem.get(f'{ns}drawable') or elem.get('android:drawable')
    if drawable:
        return drawable
    return None


def parse_color_state_list(xml_path: Path) -> str | None:
    """
    Parse a color state list XML and return the default color.

    Color state lists define different colors for different states.
    We extract the default color (the item with no state conditions).

    Handles both <item> and <color> child elements, and both
    android:color and android:drawable attributes.

    Example:
        <selector>
            <item android:color="#FF0000" android:state_pressed="true"/>
            <item android:color="#00FF00"/>
        </selector>
        -> "#00FF00"
    """
    if not xml_path.exists():
        return None

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        if root.tag != 'selector':
            return None

        # Collect all child elements (both <item> and <color> tags)
        children = list(root)
        if not children:
            return None

        # Find the default entry (no state attributes)
        for child in children:
            # Check if this element has ANY android state attributes
            state_attrs = [attr for attr in child.attrib.keys()
                          if (attr.startswith('{http://schemas.android.com/apk/res/android}state_')
                              or attr.startswith('android:state_'))]

            if not state_attrs:
                color = _get_color_from_element(child)
                if color:
                    return color

        # If no default found, use the last entry
        if children:
            color = _get_color_from_element(children[-1])
            return color

        return None
    except Exception as e:
        print(f"Warning: Failed to parse color state list {xml_path}: {e}")
        return None


def parse_bools_xml(xml_path: Path) -> dict[str, str]:
    """
    Parse bools.xml and return a mapping of bool names to values.

    Handles both forms:
        <bool name="is_tablet">true</bool>
        <item type="bool" name="foo">@android:bool/bar</item>
    """
    if not xml_path.exists():
        return {}

    tree = ET.parse(xml_path)
    root = tree.getroot()

    bools = {}
    for bool_elem in root.findall("bool"):
        name = bool_elem.get("name")
        value = bool_elem.text or ""
        if name:
            bools[name] = value

    for item_elem in root.findall("item"):
        if item_elem.get("type") == "bool":
            name = item_elem.get("name")
            value = item_elem.text or ""
            if name:
                bools[name] = value

    return bools


def load_values_resources(res_dir: Path) -> dict:
    """
    Load all resource values from a res/ directory.

    Parses values/*.xml files and returns a dict with:
    - strings: dict[str, str]
    - dimens: dict[str, str]
    - colors: dict[str, str]
    - bools: dict[str, str]
    - styles: dict[str, Style]
    """
    values_dir = res_dir / "values"

    resources = {
        'strings': {},
        'dimens': {},
        'colors': {},
        'bools': {},
        'styles': {},
    }

    if not values_dir.exists():
        return resources

    # Parse each resource type
    strings_xml = values_dir / "strings.xml"
    if strings_xml.exists():
        resources['strings'] = parse_strings_xml(strings_xml)

    dimens_xml = values_dir / "dimens.xml"
    if dimens_xml.exists():
        resources['dimens'] = parse_dimens_xml(dimens_xml)

    colors_xml = values_dir / "colors.xml"
    if colors_xml.exists():
        resources['colors'] = parse_colors_xml(colors_xml)

    # Also load color state list XML files from res/color/
    color_dir = res_dir / "color"
    if color_dir.exists():
        for color_xml in color_dir.glob("*.xml"):
            # Parse color state list and extract default color
            name = color_xml.stem
            default_color = parse_color_state_list(color_xml)
            if default_color:
                resources['colors'][name] = default_color

    bools_xml = values_dir / "bools.xml"
    if bools_xml.exists():
        resources['bools'] = parse_bools_xml(bools_xml)

    # Load styles from entire res/ directory (handles inheritance)
    resources['styles'] = load_all_styles(res_dir)

    return resources
