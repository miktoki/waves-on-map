"""Hex and colormap utilities.

Small helpers to map scalar values to hex colors using matplotlib colormaps,
compute a hex color's relative luminance, and convert hex to an rgba() string.
"""

from typing import Optional

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt


def blend_hex(base_hex: str, overlay_hex: str, alpha: float) -> str:
    """Blend overlay_hex onto base_hex with given alpha (0..1) and return hex.

    Uses simple linear interpolation per channel and returns a 6-char hex.
    """
    if not base_hex:
        base_hex = "#000000"
    if not overlay_hex:
        overlay_hex = "#000000"
    b = base_hex.lstrip("#")
    o = overlay_hex.lstrip("#")
    if len(b) == 3:
        br, bg, bb = (int(b[i] * 2, 16) for i in range(3))
    else:
        br, bg, bb = (int(b[i : i + 2], 16) for i in (0, 2, 4))
    if len(o) == 3:
        or_, og, ob = (int(o[i] * 2, 16) for i in range(3))
    else:
        or_, og, ob = (int(o[i : i + 2], 16) for i in (0, 2, 4))

    a = max(0.0, min(1.0, alpha))
    rr = int(round(br * (1 - a) + or_ * a))
    rg = int(round(bg * (1 - a) + og * a))
    rb = int(round(bb * (1 - a) + ob * a))
    return f"#{rr:02x}{rg:02x}{rb:02x}"


def value_to_hex(x: float, a: float, b: float, cmap_name: str = "viridis") -> str:
    """Map scalar x in [a,b] to a HEX color using the named matplotlib colormap.

    The value is clipped to [0,1] after normalization. Returns a 6-char hex string
    beginning with '#'.
    """
    if b == a:
        norm = 0.0
    else:
        norm = (x - a) / (b - a)
    norm = max(0.0, min(1.0, norm))
    cmap = plt.get_cmap(cmap_name)  # type: ignore
    rgb = cmap(norm)[:3]
    return mcolors.rgb2hex(rgb)


def value_to_rgba(
    x: float,
    a: float,
    b: float,
    cmap_name: str = "viridis",
    alpha_min: float = 0.0,
    alpha_max: float = 0.12,
) -> str:
    """Map scalar x in [a,b] to an `rgba(r,g,b,a)` CSS string using the named
    matplotlib colormap where alpha is 0 at the minimum (a) and increases
    linearly to ``alpha_max`` at the maximum (b).

    Alpha is clamped to [0,1]. If ``b == a`` the value is treated as the
    minimum (alpha == alpha_min).
    """
    if b == a:
        norm = 0.0
    else:
        norm = (x - a) / (b - a)
    norm = max(0.0, min(1.0, norm))
    alpha = alpha_min + norm * (alpha_max - alpha_min)
    alpha = max(0.0, min(1.0, alpha))
    hexcolor = value_to_hex(x, a, b, cmap_name)
    return hex_to_rgba(hexcolor, alpha)


def hex_luminance(hexcolor: Optional[str]) -> float:
    """Return the relative luminance (0..1) for a given hex color string.

    If ``hexcolor`` is falsy, returns 1.0 (light) to be conservative for contrast.
    """
    if not hexcolor:
        return 1.0
    h = hexcolor.lstrip("#")
    if len(h) == 3:
        r, g, b = (int(h[i] * 2, 16) for i in range(3))
    else:
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    rn, gn, bn = [v / 255.0 for v in (r, g, b)]
    return 0.2126 * rn + 0.7152 * gn + 0.0722 * bn


def hex_to_rgba(hexcolor: str, alpha: float = 0.12) -> str:
    """Convert a hex color to an `rgba(r,g,b,a)` CSS string.

    Alpha is clamped to [0,1].
    """
    if not hexcolor:
        return f"rgba(0,0,0,{max(0.0, min(1.0, alpha))})"
    h = hexcolor.lstrip("#")
    if len(h) == 3:
        r, g, b = (int(h[i] * 2, 16) for i in range(3))
    else:
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    a = max(0.0, min(1.0, alpha))
    return f"rgba({r},{g},{b},{a})"
