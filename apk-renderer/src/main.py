#!/usr/bin/env python3
"""
Android Layout Renderer CLI

Renders Android layout XML files to PNG images by simulating the Android
view system's measure, layout, and draw passes.
"""

import argparse
import sys
from pathlib import Path

from parser import parse_layout_xml
from registry import create_registry
from measurer import measure
from layouter import layout
from drawer import draw
from drawable_loader import discover_drawables
from resource_parser import load_values_resources
from models import MeasureSpec, MeasureSpecMode, RenderContext, FontConfig, create_font_config
from registry import Registry
from PIL import Image


def render_layout(
    xml_file: Path,
    output_file: Path,
    width: int,
    height: int,
    ctx: RenderContext,
    registry: Registry,
) -> None:
    """
    Render a single layout XML file to a PNG image.

    Args:
        xml_file: Path to the layout XML file
        output_file: Path to write the output PNG
        width: Screen width in dp
        height: Screen height in dp
        ctx: Rendering context with loaded resources
        registry: Unified view registry
    """
    from resources import deref_dimension_to_pixels

    root_view = parse_layout_xml(xml_file, ctx)

    # Determine actual dimensions
    layout_width = root_view.attributes.get("android:layout_width")
    layout_height = root_view.attributes.get("android:layout_height")

    actual_width = width
    actual_height = height

    if layout_width and layout_width not in ("match_parent", "fill_parent", "wrap_content"):
        actual_width = deref_dimension_to_pixels(layout_width, ctx, width)

    if layout_height and layout_height not in ("match_parent", "fill_parent", "wrap_content"):
        actual_height = deref_dimension_to_pixels(layout_height, ctx, height)

    # Measure pass
    width_spec = MeasureSpec(MeasureSpecMode.EXACTLY, actual_width)
    height_spec = MeasureSpec(MeasureSpecMode.EXACTLY, actual_height)
    measure(root_view, width_spec, height_spec, ctx, registry)

    # Layout pass
    layout(root_view, 0, 0, actual_width, actual_height, ctx, registry)

    # Draw pass
    canvas = Image.new("RGBA", (actual_width, actual_height), (255, 255, 255, 255))
    draw(root_view, canvas, ctx, registry)

    # Save output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_file)


def load_resources(res_dir: Path) -> dict:
    """
    Load resources from a res/ directory.

    Returns a dictionary containing:
    - drawables: dict[str, Path]
    - styles: dict[str, Style] (empty for now)
    - dimens: dict[str, str] (empty for now)
    - colors: dict[str, str] (empty for now)
    - strings: dict[str, str] (empty for now)
    - bools: dict[str, str] (empty for now)
    """
    resources = {
        'drawables': {},
        'styles': {},
        'dimens': {},
        'colors': {},
        'strings': {},
        'bools': {},
    }

    if not res_dir.exists():
        print(f"Warning: Resource directory not found: {res_dir}", file=sys.stderr)
        return resources

    # Load drawables
    resources['drawables'] = discover_drawables(res_dir)
    print(f"Loaded {len(resources['drawables'])} drawables from {res_dir}")

    # Load values resources (strings, dimens, colors, bools)
    values_resources = load_values_resources(res_dir)
    resources['strings'] = values_resources['strings']
    resources['dimens'] = values_resources['dimens']
    resources['colors'] = values_resources['colors']
    resources['bools'] = values_resources['bools']
    resources['styles'] = values_resources['styles']

    print(f"Loaded {len(resources['strings'])} strings, {len(resources['dimens'])} dimens, {len(resources['colors'])} colors, {len(resources['styles'])} styles")

    return resources


def main():
    parser = argparse.ArgumentParser(
        description='Render Android layout XML to PNG',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s \\
    --framework-dir ./build/framework-res-decoded \\
    --app-dir ./build/apktool-apps/AirCon-resources \\
    --xml-file ./build/apktool-apps/AirCon-resources/res/layout/main.xml \\
    --output-file output.png

  %(prog)s \\
    --framework-dir ./build/framework-res-decoded \\
    --app-dir ./build/apktool-apps/AirCon-resources \\
    --xml-file ./build/apktool-apps/AirCon-resources/res/layout/main.xml \\
    --output-file output.png \\
    --width 360 \\
    --height 640
        """
    )

    parser.add_argument(
        '--framework-dir',
        required=True,
        type=Path,
        help='Path to framework resources directory (e.g., ./build/framework-res-decoded/)'
    )

    parser.add_argument(
        '--app-dir',
        required=True,
        type=Path,
        help='Path to app resources directory (e.g., ./build/apktool-apps/AirCon-resources)'
    )

    parser.add_argument(
        '--xml-file',
        required=True,
        type=Path,
        help='Path to layout XML file to render'
    )

    parser.add_argument(
        '--output-file',
        required=True,
        type=Path,
        help='Output PNG file path'
    )

    parser.add_argument(
        '--width',
        type=int,
        default=800,
        help='Screen width in dp (default: 800)'
    )

    parser.add_argument(
        '--height',
        type=int,
        default=480,
        help='Screen height in dp (default: 480)'
    )

    parser.add_argument(
        '--density',
        type=float,
        default=1.0,
        help='Screen density multiplier (default: 1.0 for mdpi)'
    )

    parser.add_argument(
        '--font-scale',
        type=float,
        default=1.0,
        help='Font scale multiplier (default: 1.0)'
    )

    VALID_THEMES = [
        'ThemeBlue',
        'ThemeAmber',
        'ThemeBlueGreen',
        'ThemeGray',
        'ThemeRed',
        'ThemeViolet',
        'ThemeZiba',
    ]

    parser.add_argument(
        '--theme',
        type=str,
        default='ThemeBlue',
        choices=VALID_THEMES,
        help='Theme name to use for rendering (default: ThemeBlue)'
    )

    parser.add_argument(
        '--fonts-dir',
        required=True,
        type=Path,
        help='Path to device system fonts directory (e.g., /system/fonts/)'
    )

    parser.add_argument(
        '--system-fonts-file',
        required=True,
        type=Path,
        help='Path to system_fonts.xml'
    )

    parser.add_argument(
        '--fallback-fonts-file',
        required=True,
        type=Path,
        help='Path to fallback_fonts.xml'
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.framework_dir.exists():
        print(f"Error: Framework directory not found: {args.framework_dir}", file=sys.stderr)
        sys.exit(1)
    if not args.framework_dir.is_dir():
        print(f"Error: Framework path is not a directory: {args.framework_dir}", file=sys.stderr)
        sys.exit(1)

    # Sanity check: assert that the framework dir contains an AndroidManifest.xml,
    # which is usually created by apktool.
    framework_manifest = args.framework_dir / "AndroidManifest.xml"
    if not framework_manifest.exists():
        print(f"Error: AndroidManifest.xml not found in framework directory: {framework_manifest}", file=sys.stderr)
        sys.exit(1)
    if not framework_manifest.is_file():
        print(f"Error: AndroidManifest.xml is not a file: {framework_manifest}", file=sys.stderr)
        sys.exit(1)

    if not args.app_dir.exists():
        print(f"Error: App directory not found: {args.app_dir}", file=sys.stderr)
        sys.exit(1)
    if not args.app_dir.is_dir():
        print(f"Error: App path is not a directory: {args.app_dir}", file=sys.stderr)
        sys.exit(1)

    # Sanity check: assert that the app dir contains an AndroidManifest.xml,
    # which is usually created by apktool.
    app_manifest = args.app_dir / "AndroidManifest.xml"
    if not app_manifest.exists():
        print(f"Error: AndroidManifest.xml not found in app directory: {app_manifest}", file=sys.stderr)
        sys.exit(1)
    if not app_manifest.is_file():
        print(f"Error: AndroidManifest.xml is not a file: {app_manifest}", file=sys.stderr)
        sys.exit(1)

    if not args.xml_file.exists():
        print(f"Error: XML file not found: {args.xml_file}", file=sys.stderr)
        sys.exit(1)

    # Load resources
    print("Loading resources...")
    framework_res_dir = args.framework_dir / "res"
    if not framework_res_dir.exists():
        print(f"Error: Framework res/ directory not found: {framework_res_dir}", file=sys.stderr)
        sys.exit(1)
    if not framework_res_dir.is_dir():
        print(f"Error: Framework res/ path is not a directory: {framework_res_dir}", file=sys.stderr)
        sys.exit(1)

    app_res_dir = args.app_dir / "res"
    if not app_res_dir.exists():
        print(f"Error: App res/ directory not found: {app_res_dir}", file=sys.stderr)
        sys.exit(1)
    if not app_res_dir.is_dir():
        print(f"Error: App res/ path is not a directory: {app_res_dir}", file=sys.stderr)
        sys.exit(1)

    framework_resources = load_resources(framework_res_dir)
    app_resources = load_resources(app_res_dir)

    # Create font config
    if not args.fonts_dir.is_dir():
        print(f"Error: Fonts directory not found: {args.fonts_dir}", file=sys.stderr)
        sys.exit(1)

    assert args.system_fonts_file.exists(), f"System fonts file does not exist: {args.system_fonts_file}"
    assert args.system_fonts_file.is_file(), f"System fonts path is not a file: {args.system_fonts_file}"
    assert args.fallback_fonts_file.exists(), f"Fallback fonts file does not exist: {args.fallback_fonts_file}"
    assert args.fallback_fonts_file.is_file(), f"Fallback fonts path is not a file: {args.fallback_fonts_file}"

    font_config = create_font_config(args.fonts_dir, args.system_fonts_file, args.fallback_fonts_file)

    # Create render context
    ctx = RenderContext(
        font_config=font_config,
        framework_styles=framework_resources['styles'],
        framework_drawables=framework_resources['drawables'],
        framework_dimens=framework_resources['dimens'],
        framework_colors=framework_resources['colors'],
        framework_strings=framework_resources['strings'],
        framework_bools=framework_resources['bools'],
        app_styles=app_resources['styles'],
        app_drawables=app_resources['drawables'],
        app_dimens=app_resources['dimens'],
        app_colors=app_resources['colors'],
        app_strings=app_resources['strings'],
        app_bools=app_resources['bools'],
        theme_name=args.theme,
        density=args.density,
        font_scale=args.font_scale,
        is_rtl=False
    )

    print(f"\nRendering {args.xml_file.name}...")
    print(f"  Screen size: {args.width}×{args.height} dp")
    print(f"  Density: {args.density}x")

    # Create unified view registry
    registry = create_registry()

    try:
        render_layout(args.xml_file, args.output_file, args.width, args.height, ctx, registry)
    except Exception as e:
        print(f"   ✗ Failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print(f"   ✓ Saved to {args.output_file}")
    print("\n" + "=" * 60)
    print("✓ Rendering completed successfully!")
    print(f"✓ Output: {args.output_file.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
