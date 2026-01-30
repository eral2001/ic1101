from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

@dataclass
class View:
    tag: str
    original_tag: str
    attributes: dict[str, str]
    children: list[View]
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

@dataclass
class Style:
    name: str
    parent: str | None
    items: dict[str, str]


def parse_system_fonts_xml(xml_path: Path) -> dict[str, list[str]]:
    """
    Parse Android's system_fonts.xml to build a family name -> font files mapping.

    The XML format is:
        <familyset>
          <family>
            <nameset><name>sans-serif</name><name>arial</name>...</nameset>
            <fileset>
              <file>Roboto-Regular.ttf</file>   <!-- index 0: regular -->
              <file>Roboto-Bold.ttf</file>       <!-- index 1: bold -->
              <file>Roboto-Italic.ttf</file>     <!-- index 2: italic -->
              <file>Roboto-BoldItalic.ttf</file> <!-- index 3: bold-italic -->
            </fileset>
          </family>
          ...
        </familyset>

    Returns a dict mapping each family name to its list of font filenames.
    """
    families: dict[str, list[str]] = {}
    tree = ET.parse(xml_path)
    root = tree.getroot()

    for family_elem in root.findall("family"):
        nameset = family_elem.find("nameset")
        fileset = family_elem.find("fileset")
        if nameset is None or fileset is None:
            continue

        files = [f.text.strip() for f in fileset.findall("file") if f.text]
        if not files:
            continue

        for name_elem in nameset.findall("name"):
            if name_elem.text:
                families[name_elem.text.strip().lower()] = files

    return families


def create_font_config(fonts_dir: Path, system_fonts_file: Path, fallback_fonts_file: Path) -> FontConfig:
    """
    Create a FontConfig, parsing system_fonts.xml and fallback_fonts.xml from the device.

    System fonts take priority over fallback fonts for duplicate family names.
    """
    families: dict[str, list[str]] = {}

    # Load fallback fonts first (lower priority)
    fallback = parse_system_fonts_xml(fallback_fonts_file)
    families.update(fallback)
    print(f"Loaded {len(fallback)} font family mappings from {fallback_fonts_file}")

    # Load system fonts second (higher priority, overwrites fallback duplicates)
    system = parse_system_fonts_xml(system_fonts_file)
    families.update(system)
    print(f"Loaded {len(system)} font family mappings from {system_fonts_file}")

    return FontConfig(fonts_dir=fonts_dir, families=families)


# Typeface attribute value -> family name mapping (Android convention)
_TYPEFACE_TO_FAMILY = {
    "sans": "sans-serif",
    "serif": "serif",
    "monospace": "monospace",
    "normal": "sans-serif",
}


@dataclass
class FontConfig:
    fonts_dir: Path
    families: dict[str, list[str]] = field(default_factory=dict)  # name -> [regular, bold, italic, bold_italic]

    def resolve_font(self, typeface: str | None, text_style: str | None) -> Path:
        """
        Resolve a font file path based on typeface and text style.

        Uses the families mapping from system_fonts.xml when available,
        falling back to well-known font paths on the host system.
        """
        # Map typeface to family name
        if typeface is None:
            family_name = "sans-serif"
        else:
            family_name = _TYPEFACE_TO_FAMILY.get(typeface.lower(), typeface.lower())

        # Compute style index: 0=regular, 1=bold, 2=italic, 3=bold-italic
        style_index = 0
        if text_style:
            ts = text_style.lower()
            is_bold = "bold" in ts
            is_italic = "italic" in ts
            if is_bold and is_italic:
                style_index = 3
            elif is_bold:
                style_index = 1
            elif is_italic:
                style_index = 2

        # Try families mapping
        files = self.families.get(family_name)
        if not files and family_name != "sans-serif":
            # Fall back to default family
            files = self.families.get("sans-serif")

        if files:
            # Clamp index to available files
            idx = min(style_index, len(files) - 1)
            font_path = self.fonts_dir / files[idx]
            if font_path.exists():
                return font_path

        # Last resort: return first .ttf found in fonts_dir
        for ttf in sorted(self.fonts_dir.glob("*.ttf")):
            return ttf

        raise FileNotFoundError(
            f"No font found for typeface={typeface!r} text_style={text_style!r} in {self.fonts_dir}"
        )

@dataclass
class RenderContext:
    font_config: FontConfig
    framework_styles: dict[str, Style]
    framework_drawables: dict[str, Path]
    framework_dimens: dict[str, str]
    framework_colors: dict[str, str]
    framework_strings: dict[str, str]
    framework_bools: dict[str, str]
    app_styles: dict[str, Style]
    app_drawables: dict[str, Path]
    app_dimens: dict[str, str]
    app_colors: dict[str, str]
    app_strings: dict[str, str]
    app_bools: dict[str, str]
    theme_name: str
    density: float = 1.0
    font_scale: float = 1.0
    is_rtl: bool = False

    def resolve_theme_attr(self, attr_name: str) -> str | None:
        """
        Walk theme inheritance chain to find attribute value.

        This resolves theme attribute references like ?attr/colorPrimary or
        ?android:attr/textColorPrimary by looking in the current theme and
        walking up the theme inheritance chain.

        Args:
            attr_name: Attribute name, can be:
                - "colorPrimary" (looks in app theme)
                - "android:colorPrimary" (looks in framework theme)
                - Full references like "?attr/..." will be parsed

        Returns:
            Resolved value or None if not found
        """
        if not self.theme_name:
            return None

        # Import here to avoid circular dependency
        from style_parser import resolve_theme_attribute

        return resolve_theme_attribute(
            attr_name,
            self.theme_name,
            self.app_styles,
            self.framework_styles
        )

class MeasureSpecMode(Enum):
    UNSPECIFIED = 0  # Parent hasn't imposed any constraint
    EXACTLY = 1      # Parent has determined exact size
    AT_MOST = 2      # Child can be up to this size

@dataclass
class MeasureSpec:
    mode: MeasureSpecMode
    size: int

@dataclass
class Dimension:
    pass

@dataclass
class DimensionMatchParent(Dimension):
    pass

@dataclass
class DimensionWrapContent(Dimension):
    pass

@dataclass
class DimensionPixels(Dimension):
    value: int

@dataclass
class Padding:
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0

@dataclass
class Margins:
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0


# Measurement function type aliases
# MeasureChildCallback: 4-parameter callback that ViewGroups receive (Registry is captured in closure)
MeasureChildCallback = Callable[['View', 'MeasureSpec', 'MeasureSpec', 'RenderContext'], None]

# ViewMeasureFunc: ViewGroup measure functions receive a 4-param child callback
ViewMeasureFunc = Callable[['View', 'MeasureSpec', 'MeasureSpec', 'RenderContext', MeasureChildCallback], None]

# Layout function type aliases
# LayoutChildCallback: 5-parameter callback that ViewGroups receive (Registry is captured in closure)
LayoutChildCallback = Callable[['View', int, int, int, int, 'RenderContext'], None]

# ViewLayoutFunc: ViewGroup layout functions receive a 5-param child callback
ViewLayoutFunc = Callable[['View', int, int, int, int, 'RenderContext', LayoutChildCallback], None]
