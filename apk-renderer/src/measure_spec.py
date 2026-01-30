from models import MeasureSpec, MeasureSpecMode
from models import Dimension, DimensionPixels, DimensionMatchParent, DimensionWrapContent
from text_utils import dimension_to_pixels_size

def constrain_to_spec(size: int, spec: MeasureSpec) -> int:
    """Constrain a desired size to a MeasureSpec."""
    match spec.mode:
        case MeasureSpecMode.EXACTLY:
            return spec.size
        case MeasureSpecMode.AT_MOST:
            return min(size, spec.size)
        case MeasureSpecMode.UNSPECIFIED:
            return size

def get_child_measure_spec(spec: MeasureSpec, padding: int, child_dim: Dimension) -> MeasureSpec:
    """
    Calculate MeasureSpec for a child based on parent's spec and child's LayoutParams.
    This mirrors Android's ViewGroup.getChildMeasureSpec().
    
    Args:
        spec: Parent's MeasureSpec for this dimension
        padding: Parent's padding + child's margin (space already used)
        child_dim: Child's layout_width or layout_height as Dimension
    """
    available = max(0, spec.size - padding)
    
    match (spec.mode, child_dim):
        # Parent is EXACTLY
        case (MeasureSpecMode.EXACTLY, DimensionPixels(value)):
            return MeasureSpec(MeasureSpecMode.EXACTLY, dimension_to_pixels_size(value))
        case (MeasureSpecMode.EXACTLY, DimensionMatchParent()):
            return MeasureSpec(MeasureSpecMode.EXACTLY, available)
        case (MeasureSpecMode.EXACTLY, DimensionWrapContent()):
            return MeasureSpec(MeasureSpecMode.AT_MOST, available)
        
        # Parent is AT_MOST
        case (MeasureSpecMode.AT_MOST, DimensionPixels(value)):
            return MeasureSpec(MeasureSpecMode.EXACTLY, dimension_to_pixels_size(value))
        case (MeasureSpecMode.AT_MOST, DimensionMatchParent()):
            return MeasureSpec(MeasureSpecMode.AT_MOST, available)
        case (MeasureSpecMode.AT_MOST, DimensionWrapContent()):
            return MeasureSpec(MeasureSpecMode.AT_MOST, available)
        
        # Parent is UNSPECIFIED
        case (MeasureSpecMode.UNSPECIFIED, DimensionPixels(value)):
            return MeasureSpec(MeasureSpecMode.EXACTLY, dimension_to_pixels_size(value))
        case (MeasureSpecMode.UNSPECIFIED, DimensionMatchParent()):
            return MeasureSpec(MeasureSpecMode.UNSPECIFIED, 0)
        case (MeasureSpecMode.UNSPECIFIED, DimensionWrapContent()):
            return MeasureSpec(MeasureSpecMode.UNSPECIFIED, 0)
    
    raise ValueError(f"Unhandled case: {spec.mode}, {child_dim}")
