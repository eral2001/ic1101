"""
Unified view registry for the three-pass Android layout system.

Maps view tag names to a ViewEntry containing the measure, layout, and draw
functions for that view type.
"""

from dataclasses import dataclass

from models import ViewMeasureFunc, ViewLayoutFunc
from drawer import ViewDrawFunc

Registry = dict[str, 'ViewEntry']


@dataclass
class ViewEntry:
    measure: ViewMeasureFunc
    layout: ViewLayoutFunc
    draw: ViewDrawFunc


def create_registry() -> Registry:
    """Create and populate the unified view registry."""
    # Android base views
    from views.android.view import measure_view, layout_view, draw_view
    from views.android.linear_layout import measure_linear_layout, layout_linear_layout
    from views.android.absolute_layout import measure_absolute_layout, layout_absolute_layout
    from views.android.frame_layout import measure_frame_layout, layout_frame_layout, draw_frame_layout
    from views.android.relative_layout import measure_relative_layout, layout_relative_layout
    from views.android.scroll_view import measure_scroll_view, layout_scroll_view
    from views.android.horizontal_scroll_view import measure_horizontal_scroll_view, layout_horizontal_scroll_view
    from views.android.space import measure_space, layout_space
    from views.android.image_view import measure_image_view, layout_image_view, draw_image_view
    from views.android.text_view import measure_text_view, layout_text_view, draw_text_view
    from views.android.button import measure_button, layout_button
    from views.android.progress_bar import measure_progress_bar, layout_progress_bar
    from views.android.rating_bar import measure_rating_bar, layout_rating_bar
    from views.android.list_view import measure_list_view

    # Mitsubishi-specific views
    from views.mitsubishi.image_view_ext_state import measure_image_view_ext_state, layout_image_view_ext_state
    from views.mitsubishi.auto_adjust_text_view import measure_auto_adjust_text_view, layout_auto_adjust_text_view, draw_auto_adjust_text_view
    from views.mitsubishi.absolute_layout_ext_state import measure_absolute_layout_ext_state, layout_absolute_layout_ext_state
    from views.mitsubishi.beep_button import measure_beep_button, layout_beep_button

    registry: Registry = {}

    # Android base views
    registry["View"] = ViewEntry(measure_view, layout_view, draw_view)
    registry["Space"] = ViewEntry(measure_space, layout_space, draw_view)
    registry["LinearLayout"] = ViewEntry(measure_linear_layout, layout_linear_layout, draw_view)
    registry["AbsoluteLayout"] = ViewEntry(measure_absolute_layout, layout_absolute_layout, draw_view)
    registry["FrameLayout"] = ViewEntry(measure_frame_layout, layout_frame_layout, draw_frame_layout)
    registry["RelativeLayout"] = ViewEntry(measure_relative_layout, layout_relative_layout, draw_view)
    registry["ScrollView"] = ViewEntry(measure_scroll_view, layout_scroll_view, draw_view)
    registry["HorizontalScrollView"] = ViewEntry(measure_horizontal_scroll_view, layout_horizontal_scroll_view, draw_view)
    registry["ImageView"] = ViewEntry(measure_image_view, layout_image_view, draw_image_view)
    registry["TextView"] = ViewEntry(measure_text_view, layout_text_view, draw_text_view)
    registry["Button"] = ViewEntry(measure_button, layout_button, draw_text_view)
    registry["ProgressBar"] = ViewEntry(measure_progress_bar, layout_progress_bar, draw_view)
    registry["RatingBar"] = ViewEntry(measure_rating_bar, layout_rating_bar, draw_view)
    registry["ListView"] = ViewEntry(measure_list_view, layout_view, draw_view)

    # Mitsubishi-specific views
    registry["ImageViewExtState"] = ViewEntry(measure_image_view_ext_state, layout_image_view_ext_state, draw_image_view)
    registry["AutoAdjustTextView"] = ViewEntry(measure_auto_adjust_text_view, layout_auto_adjust_text_view, draw_auto_adjust_text_view)
    registry["AbsoluteLayoutExtState"] = ViewEntry(measure_absolute_layout_ext_state, layout_absolute_layout_ext_state, draw_view)
    registry["BeepButton"] = ViewEntry(measure_beep_button, layout_beep_button, draw_text_view)

    return registry
