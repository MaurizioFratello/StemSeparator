"""
Typography system for StemSeparator GUI

PURPOSE: Consistent font sizing and weights across the application.
CONTEXT: Uses system fonts with fallbacks for cross-platform compatibility.
         Optimized for macOS with SF Pro Text/Display font stack.
"""


class Typography:
    """Typography scale and font definitions"""

    # Font family stack (macOS-optimized, system fonts for native look)
    # WHY: -apple-system first for macOS SF Pro, then cross-platform fallbacks
    FONT_FAMILY = "-apple-system, 'SF Pro Text', system-ui, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    FONT_FAMILY_MONO = "'SF Mono', Menlo, Monaco, Consolas, 'Courier New', monospace"

    # Font sizes (in pixels) - macOS-optimized
    # WHY: macOS native apps typically use 13px for body text, not 14px
    SIZE_DISPLAY = 26           # Large headings (macOS convention: slightly smaller than other platforms)
    SIZE_H1 = 20                # Section headers (macOS standard for large headers)
    SIZE_H2 = 17                # Subsection headers (macOS standard for medium headers)
    SIZE_H3 = 15                # Group box titles (slightly larger than body)
    SIZE_BODY = 13              # Body text, buttons, inputs (macOS default!)
    SIZE_SMALL = 11             # Labels, captions, secondary info (macOS small text)
    SIZE_TINY = 9               # Metadata, timestamps (macOS caption text)

    # Font weights - extended for SF Pro compatibility
    # WHY: SF Pro has more weight variants than standard fonts
    WEIGHT_ULTRALIGHT = 100     # SF Pro Ultralight
    WEIGHT_THIN = 200           # SF Pro Thin
    WEIGHT_LIGHT = 300          # SF Pro Light
    WEIGHT_NORMAL = 400         # SF Pro Regular
    WEIGHT_MEDIUM = 500         # SF Pro Medium
    WEIGHT_SEMIBOLD = 600       # SF Pro Semibold
    WEIGHT_BOLD = 700           # SF Pro Bold
    WEIGHT_HEAVY = 800          # SF Pro Heavy
    WEIGHT_BLACK = 900          # SF Pro Black
    WEIGHT_EXTRABOLD = 800      # Alias for Heavy (backward compatibility)

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
