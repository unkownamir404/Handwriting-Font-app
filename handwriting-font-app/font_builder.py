"""
Turns the per-character vector outlines produced by glyph_processor.py
into an actual installable .ttf font file, using fontTools (free, no API,
no network calls). Each letter becomes one glyph; because every sample
was drawn with the pen touching the baseline (as it naturally does
mid-cursive-word), consecutive glyphs will visually flow into each other
when typed -- the same technique real handwriting-font tools use.
"""
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

UPM = 1000                 # units per em
BASELINE_FRACTION = 0.72   # where the writing baseline sits within each cell (leaves room for descenders)
SIDE_BEARING = 40          # left/right breathing room, in font units
ASCENT = 800
DESCENT = -200


def _signed_area(points):
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def _with_winding(points, want_positive):
    area = _signed_area(points)
    if (area > 0) != want_positive:
        return list(reversed(points))
    return points


def _pixels_to_font_units(points, cell_height, scale):
    baseline_px = cell_height * BASELINE_FRACTION
    out = []
    for (px, py) in points:
        fx = px * scale
        fy = (baseline_px - py) * scale
        out.append((fx, fy))
    return out


def _build_glyph(char_data):
    """char_data: {"contours": [{"points": [[x,y],...], "hole": bool}], "width": w, "height": h}"""
    scale = UPM / float(char_data["height"])
    pen = TTGlyphPen(None)

    min_x, max_x = None, None
    for contour in char_data["contours"]:
        pts = _pixels_to_font_units(contour["points"], char_data["height"], scale)
        pts = _with_winding(pts, want_positive=not contour["hole"])
        pen.moveTo(pts[0])
        for pt in pts[1:]:
            pen.lineTo(pt)
        pen.closePath()
        for (x, _y) in pts:
            min_x = x if min_x is None else min(min_x, x)
            max_x = x if max_x is None else max(max_x, x)

    glyph = pen.glyph()
    if min_x is None:
        min_x, max_x = 0, 0
    advance_width = int((max_x - min_x) + 2 * SIDE_BEARING)
    left_side_bearing = int(SIDE_BEARING - min_x) if min_x else SIDE_BEARING
    return glyph, max(advance_width, 100), left_side_bearing


def build_font(glyph_data, out_path, family_name="MyHandwriting", style_name="Regular"):
    """
    glyph_data: dict[char] -> {"contours": [...], "width": int, "height": int}
        as produced by glyph_processor.extract_glyphs
    out_path: where to save the .ttf
    """
    glyph_order = [".notdef", "space"]
    glyphs = {}
    metrics = {}
    cmap = {}

    # .notdef: empty but valid
    empty_pen = TTGlyphPen(None)
    glyphs[".notdef"] = empty_pen.glyph()
    metrics[".notdef"] = (UPM // 2, 0)

    # space
    space_pen = TTGlyphPen(None)
    glyphs["space"] = space_pen.glyph()
    metrics["space"] = (int(UPM * 0.42), 0)
    cmap[ord(" ")] = "space"

    for ch, data in glyph_data.items():
        glyph_name = f"char_{ord(ch):04X}"  # safe, unique glyph name for any character
        glyph, adv_width, lsb = _build_glyph(data)
        glyphs[glyph_name] = glyph
        metrics[glyph_name] = (adv_width, lsb)
        cmap[ord(ch)] = glyph_name
        glyph_order.append(glyph_name)

    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=ASCENT, descent=DESCENT)
    fb.setupNameTable({
        "familyName": family_name,
        "styleName": style_name,
        "uniqueFontIdentifier": f"{family_name}-{style_name}",
        "fullName": f"{family_name} {style_name}",
        "psName": f"{family_name}-{style_name}".replace(" ", ""),
        "version": "Version 1.0",
    })
    fb.setupOS2(sTypoAscender=ASCENT, sTypoDescender=DESCENT, usWinAscent=ASCENT, usWinDescent=abs(DESCENT))
    fb.setupPost()

    fb.font.save(out_path)
    return out_path
