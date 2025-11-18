"""
Spacing system for StemSeparator GUI

PURPOSE: Consistent spacing and sizing across UI components.
CONTEXT: Uses 8px base unit for harmonious layout rhythm.
"""


class Spacing:
    """
    Consistent spacing scale based on 8px grid

    WHY: Using a consistent spacing system creates visual harmony and makes
         the UI feel more polished and professional.
    """

    # Base spacing units (8px grid)
    NONE = 0
    XXS = 2      # Micro spacing
    XS = 4       # Extra small
    SM = 8       # Small
    MD = 16      # Medium (base unit)
    LG = 24      # Large
    XL = 32      # Extra large
    XXL = 48     # 2x large
    XXXL = 64    # 3x large

    # Component-specific spacing
    BUTTON_PADDING_V = 12    # Vertical padding for buttons
    BUTTON_PADDING_H = 24    # Horizontal padding for buttons
    INPUT_PADDING = 10       # Padding for text inputs
    GROUP_PADDING = 20       # Padding inside group boxes
    CARD_PADDING = 16        # Padding for card-like components

    # Border radius
    RADIUS_SM = 4       # Small radius (checkboxes, small elements)
    RADIUS_MD = 8       # Medium radius (buttons, inputs)
    RADIUS_LG = 12      # Large radius (cards, group boxes)
    RADIUS_XL = 16      # Extra large radius
    RADIUS_FULL = 9999  # Fully rounded (pills, circles)

    # Icon sizes
    ICON_SM = 16
    ICON_MD = 24
    ICON_LG = 32
    ICON_XL = 48

    # Component heights
    BUTTON_HEIGHT_SM = 32
    BUTTON_HEIGHT_MD = 40
    BUTTON_HEIGHT_LG = 48
    INPUT_HEIGHT = 40
    SLIDER_HEIGHT = 6
    SLIDER_HANDLE_SIZE = 18
    PROGRESS_HEIGHT_SM = 12
    PROGRESS_HEIGHT_MD = 24
    PROGRESS_HEIGHT_LG = 32

    @classmethod
    def padding(cls, vertical: int, horizontal: int) -> str:
        """Generate QSS padding string"""
        return f"padding: {vertical}px {horizontal}px;"

    @classmethod
    def margin(cls, top: int, right: int, bottom: int, left: int) -> str:
        """Generate QSS margin string"""
        return f"margin: {top}px {right}px {bottom}px {left}px;"

    @classmethod
    def border_radius(cls, radius: int) -> str:
        """Generate QSS border-radius string"""
        return f"border-radius: {radius}px;"
