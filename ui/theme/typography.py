"""
Typography system for StemSeparator GUI

PURPOSE: Consistent font sizing and weights across the application.
CONTEXT: Uses system fonts with fallbacks for cross-platform compatibility.
"""


class Typography:
    """Typography scale and font definitions"""

    # Font family stack (system fonts for native look)
    FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    FONT_FAMILY_MONO = "'SF Mono', Consolas, Monaco, 'Courier New', monospace"

    # Font sizes (in pixels)
    SIZE_DISPLAY = 28           # Large headings, hero text
    SIZE_H1 = 22               # Section headers
    SIZE_H2 = 18               # Subsection headers
    SIZE_H3 = 16               # Group box titles
    SIZE_BODY = 14             # Body text, buttons, inputs
    SIZE_SMALL = 12            # Labels, captions, secondary info
    SIZE_TINY = 10             # Metadata, timestamps

    # Font weights
    WEIGHT_LIGHT = 300
    WEIGHT_NORMAL = 400
    WEIGHT_MEDIUM = 500
    WEIGHT_SEMIBOLD = 600
    WEIGHT_BOLD = 700
    WEIGHT_EXTRABOLD = 800

    # Line heights (relative to font size)
    LINE_HEIGHT_TIGHT = 1.2
    LINE_HEIGHT_NORMAL = 1.5
    LINE_HEIGHT_RELAXED = 1.75

    # Letter spacing
    TRACKING_TIGHT = "-0.02em"
    TRACKING_NORMAL = "0em"
    TRACKING_WIDE = "0.05em"

    @classmethod
    def get_font_style(cls, size: int, weight: int = WEIGHT_NORMAL, family: str = None) -> str:
        """
        Generate QSS font style string

        Args:
            size: Font size in pixels
            weight: Font weight
            family: Font family (defaults to FONT_FAMILY)

        Returns:
            QSS font style string
        """
        family = family or cls.FONT_FAMILY
        return f"font-family: {family}; font-size: {size}px; font-weight: {weight};"

    @classmethod
    def display(cls) -> str:
        """Display text style"""
        return cls.get_font_style(cls.SIZE_DISPLAY, cls.WEIGHT_BOLD)

    @classmethod
    def h1(cls) -> str:
        """H1 heading style"""
        return cls.get_font_style(cls.SIZE_H1, cls.WEIGHT_SEMIBOLD)

    @classmethod
    def h2(cls) -> str:
        """H2 heading style"""
        return cls.get_font_style(cls.SIZE_H2, cls.WEIGHT_SEMIBOLD)

    @classmethod
    def h3(cls) -> str:
        """H3 heading style"""
        return cls.get_font_style(cls.SIZE_H3, cls.WEIGHT_MEDIUM)

    @classmethod
    def body(cls) -> str:
        """Body text style"""
        return cls.get_font_style(cls.SIZE_BODY, cls.WEIGHT_NORMAL)

    @classmethod
    def body_bold(cls) -> str:
        """Bold body text style"""
        return cls.get_font_style(cls.SIZE_BODY, cls.WEIGHT_SEMIBOLD)

    @classmethod
    def small(cls) -> str:
        """Small text style"""
        return cls.get_font_style(cls.SIZE_SMALL, cls.WEIGHT_NORMAL)

    @classmethod
    def mono(cls, size: int = SIZE_BODY) -> str:
        """Monospace text style (for time displays, code)"""
        return cls.get_font_style(size, cls.WEIGHT_NORMAL, cls.FONT_FAMILY_MONO)
