#!/usr/bin/env python3
"""
Bulk Android Layout Renderer

Renders all layout XML files across all app directories under a given
apps directory. Loads framework resources once and app resources once per
app for efficiency.
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from main import load_resources, render_layout
from models import RenderContext, create_font_config
from registry import create_registry


def main():
    parser = argparse.ArgumentParser(
        description='Bulk render Android layout XMLs to PNGs',
    )

    parser.add_argument(
        '--framework-dir',
        required=True,
        type=Path,
        help='Path to framework resources directory'
    )

    parser.add_argument(
        '--apps-dir',
        required=True,
        type=Path,
        help='Path to directory containing app subdirectories'
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        required=True,
        help='Output directory for rendered PNGs (must not already exist)'
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
        help='Path to system_fonts.xml (e.g., /system/etc/system_fonts.xml)'
    )

    parser.add_argument(
        '--fallback-fonts-file',
        required=True,
        type=Path,
        help='Path to fallback_fonts.xml (e.g., /system/etc/fallback_fonts.xml)'
    )

    args = parser.parse_args()

    # Validate inputs
    assert args.apps_dir.exists(), f"Apps directory does not exist: {args.apps_dir}"
    assert args.apps_dir.is_dir(), f"Apps directory is not a directory: {args.apps_dir}"
    assert not args.output_dir.exists(), f"Output directory already exists: {args.output_dir}"

    # Discover all (app_subdir, layout_xml) pairs, grouped by app
    jobs_by_app: dict[Path, list[Path]] = defaultdict(list)
    total_jobs = 0
    for app_dir in sorted(args.apps_dir.iterdir()):
        if not app_dir.is_dir():
            continue
        res_dir = app_dir / "res"
        if not res_dir.is_dir():
            continue
        for layout_dir in sorted(res_dir.glob("layout*")):
            if not layout_dir.is_dir():
                continue
            for xml_file in sorted(layout_dir.glob("*.xml")):
                jobs_by_app[app_dir].append(xml_file)
                total_jobs += 1

    if total_jobs == 0:
        print("No layout XML files found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {total_jobs} layouts across {len(jobs_by_app)} apps.")

    # Create output directory
    args.output_dir.mkdir(parents=True)

    # Load framework resources once
    print("Loading framework resources...")
    framework_res_dir = args.framework_dir / "res"
    framework_resources = load_resources(framework_res_dir)

    # Create font config once
    if not args.fonts_dir.is_dir():
        print(f"Error: Fonts directory not found: {args.fonts_dir}", file=sys.stderr)
        sys.exit(1)

    assert args.system_fonts_file.exists(), f"System fonts file does not exist: {args.system_fonts_file}"
    assert args.system_fonts_file.is_file(), f"System fonts path is not a file: {args.system_fonts_file}"
    assert args.fallback_fonts_file.exists(), f"Fallback fonts file does not exist: {args.fallback_fonts_file}"
    assert args.fallback_fonts_file.is_file(), f"Fallback fonts path is not a file: {args.fallback_fonts_file}"

    font_config = create_font_config(args.fonts_dir, args.system_fonts_file, args.fallback_fonts_file)

    # Create registry once
    registry = create_registry()

    failures = 0
    completed = 0

    for app_dir, xml_files in jobs_by_app.items():
        app_name = app_dir.name
        print(f"\nLoading resources for {app_name}...")
        app_res_dir = app_dir / "res"
        app_resources = load_resources(app_res_dir)

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
            is_rtl=False,
        )

        for xml_file in xml_files:
            completed += 1
            layout_dir_name = xml_file.parent.name
            layout_name = xml_file.stem
            output_file = args.output_dir / f"{app_name}--{layout_dir_name}--{layout_name}--{args.theme}.png"

            print(f"[{completed}/{total_jobs}] {app_name}/{layout_name}")

            try:
                render_layout(xml_file, output_file, args.width, args.height, ctx, registry)
            except Exception as e:
                failures += 1
                print(f"  FAILED: {e}", file=sys.stderr)

    print(f"\nDone. {total_jobs - failures}/{total_jobs} succeeded.")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
