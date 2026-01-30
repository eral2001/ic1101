import xml.etree.ElementTree as ET
from pathlib import Path
from models import RenderContext, View


# Android XML namespace
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


def parse_layout_xml(xml_path: Path, ctx: RenderContext) -> View:
    """
    Parse an Android layout XML file and build a View tree.

    Args:
        xml_path: Path to the layout XML file
        ctx: RenderContext with resources and configuration

    Returns:
        Root View of the parsed layout tree
    """
    tree = ET.parse(xml_path)
    root_element = tree.getroot()

    # Parse the root element into a View tree
    return parse_element(root_element, ctx)


def parse_element(element: ET.Element, ctx: RenderContext) -> View:
    """
    Recursively parse an XML element into a View.

    Args:
        element: XML element to parse
        ctx: RenderContext for resolving references

    Returns:
        View object representing this element and its children
    """
    # Extract tag name (handle fully qualified class names)
    original_tag = element.tag
    tag = extract_tag_name(original_tag)

    # Handle special tags
    if tag == "merge":
        # <merge> is a placeholder that should be replaced by its children
        # For now, treat it as a FrameLayout
        # TODO: Proper merge handling requires knowing the parent layout type
        tag = "FrameLayout"

    if tag == "requestFocus":
        # <requestFocus> is a special tag that doesn't render
        # Return a dummy view that will be filtered out
        return View(
            tag="requestFocus",
            original_tag=original_tag,
            attributes={},
            children=[]
        )

    # Extract attributes with android: namespace
    attributes = extract_attributes(element)

    # Handle <include> tag
    if tag == "include":
        # TODO: Load and parse the included layout file
        # For now, create a placeholder
        layout_ref = attributes.get("layout")
        print(f"Warning: <include layout=\"{layout_ref}\"> not fully implemented")
        # Return empty FrameLayout as placeholder
        return View(
            tag="FrameLayout",
            original_tag=original_tag,
            attributes=attributes,
            children=[]
        )

    # Parse child elements recursively
    children = []
    for child_element in element:
        child_view = parse_element(child_element, ctx)
        # Filter out special non-rendering views
        if child_view.tag != "requestFocus":
            children.append(child_view)

    return View(
        tag=tag,
        original_tag=original_tag,
        attributes=attributes,
        children=children
    )


def extract_tag_name(full_tag: str) -> str:
    """
    Extract the simple tag name from a potentially fully-qualified class name.

    Examples:
        "LinearLayout" -> "LinearLayout"
        "android.widget.LinearLayout" -> "LinearLayout"
        "com.example.CustomView" -> "CustomView"

    Args:
        full_tag: The full tag name from XML

    Returns:
        Simple class name
    """
    # Handle namespace prefix (rare but possible)
    if "}" in full_tag:
        full_tag = full_tag.split("}", 1)[1]

    # Handle fully qualified class names
    if "." in full_tag:
        return full_tag.split(".")[-1]

    return full_tag


def extract_attributes(element: ET.Element) -> dict[str, str]:
    """
    Extract all attributes from an XML element, handling the android: namespace.

    Args:
        element: XML element

    Returns:
        Dictionary mapping attribute names to values (with android: prefix preserved)
    """
    attributes = {}

    for key, value in element.attrib.items():
        # Handle android: namespace
        if key.startswith(ANDROID_NS):
            # Remove namespace URI, keep "android:" prefix
            attr_name = "android:" + key[len(ANDROID_NS):]
            attributes[attr_name] = value
        else:
            # Custom attributes or no namespace
            attributes[key] = value

    return attributes
