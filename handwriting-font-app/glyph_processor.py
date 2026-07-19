"""
Takes a photo/scan of the filled-in worksheet + the template_layout.json
that describes where every character box lives, and produces, per
character, a set of vector polygon outlines (outer shape + any "holes",
e.g. the closed loop inside a lowercase 'a' or 'e').

No deep learning here on purpose -- because we control the template
layout, we don't need to "figure out" where letters are, just correct
the page's perspective/scale and crop known boxes. That's what makes
this reliable without training data or paid APIs.
"""
import json
import cv2
import numpy as np


def _order_corners(pts):
    """Given 4 (x,y) points, return them as top_left, top_right, bottom_left, bottom_right."""
    pts = np.array(pts, dtype="float32")
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).flatten()
    top_left = pts[np.argmin(s)]
    bottom_right = pts[np.argmax(s)]
    top_right = pts[np.argmin(d)]
    bottom_left = pts[np.argmax(d)]
    return top_left, top_right, bottom_left, bottom_right


def _best_square_in_region(binary, x0, y0, x1, y1):
    """Find the most square/solid dark blob within a sub-region of the binary image."""
    region = binary[y0:y1, x0:x1]
    contours, _ = cv2.findContours(region, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    region_area = (x1 - x0) * (y1 - y0)

    best = None
    best_score = -1
    for c in contours:
        area = cv2.contourArea(c)
        if not (0.001 * region_area < area < 0.6 * region_area):
            continue
        bx, by, bw, bh = cv2.boundingRect(c)
        aspect = bw / float(bh) if bh else 0
        if not (0.6 < aspect < 1.6):
            continue
        solidity = area / float(bw * bh)
        if solidity < 0.85:  # a solid black square should be nearly fully filled
            continue
        if solidity > best_score:
            best_score = solidity
            best = (x0 + bx + bw / 2.0, y0 + by + bh / 2.0)
    return best


def _find_markers(gray_img):
    """
    Find the 4 solid black square corner markers in a photographed page by
    searching within each corner quadrant separately -- this is far more
    robust than a global search, since it can't confuse a marker with a
    similarly-shaped handwritten letter somewhere in the middle of the page.
    """
    h, w = gray_img.shape
    _, binary = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # generous corner search windows (35% of page each way) to tolerate
    # rotation/perspective in a handheld photo
    fw, fh = int(w * 0.35), int(h * 0.35)
    regions = {
        "top_left": (0, 0, fw, fh),
        "top_right": (w - fw, 0, w, fh),
        "bottom_left": (0, h - fh, fw, h),
        "bottom_right": (w - fw, h - fh, w, h),
    }

    found = {}
    for name, (x0, y0, x1, y1) in regions.items():
        pt = _best_square_in_region(binary, x0, y0, x1, y1)
        if pt is not None:
            found[name] = pt

    if len(found) < 4:
        missing = [k for k in regions if k not in found]
        raise ValueError(
            f"Could not find corner marker(s): {', '.join(missing)}. "
            "Make sure all 4 black corner squares are visible, well-lit, and the photo isn't cropped."
        )

    return found["top_left"], found["top_right"], found["bottom_left"], found["bottom_right"]


def _warp_to_template(image, layout):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    tl, tr, bl, br = _find_markers(gray)
    src_pts = np.array([tl, tr, bl, br], dtype="float32")

    m = layout["markers"]

    def center(box):
        x1, y1, x2, y2 = box
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    dst_pts = np.array(
        [center(m["top_left"]), center(m["top_right"]), center(m["bottom_left"]), center(m["bottom_right"])],
        dtype="float32",
    )

    H = cv2.getPerspectiveTransform(src_pts, dst_pts)
    page_w, page_h = layout["page_size"]
    warped = cv2.warpPerspective(image, H, (page_w, page_h), borderValue=(255, 255, 255))
    return warped


def _vectorize_cell(cell_bgr, simplify_epsilon=1.5):
    """Threshold a cropped cell to find ink, return polygon contours (with hole flags)."""
    gray = cv2.cvtColor(cell_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # remove speckle noise
    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    results = []
    if hierarchy is None:
        return results

    hierarchy = hierarchy[0]
    for i, cnt in enumerate(contours):
        if cv2.contourArea(cnt) < 8:
            continue
        approx = cv2.approxPolyDP(cnt, simplify_epsilon, True)
        points = approx.reshape(-1, 2).tolist()
        if len(points) < 3:
            continue
        # in RETR_CCOMP, hierarchy[i][3] == parent index; a contour with a parent is a hole
        is_hole = hierarchy[i][3] != -1
        results.append({"points": points, "hole": is_hole})
    return results


def extract_glyphs(scan_image_path, layout_path):
    """
    Returns: dict[char] -> {"contours": [{"points": [[x,y], ...], "hole": bool}, ...],
                             "width": int, "height": int}
    Coordinates are local to each cropped character cell (origin top-left, y grows downward).
    """
    with open(layout_path) as f:
        layout = json.load(f)

    image = cv2.imread(scan_image_path)
    if image is None:
        raise ValueError(f"Could not read image: {scan_image_path}")

    warped = _warp_to_template(image, layout)

    glyphs = {}
    for ch, (x1, y1, x2, y2) in layout["cells"].items():
        cell = warped[y1:y2, x1:x2]
        if cell.size == 0:
            continue
        contours = _vectorize_cell(cell)
        if not contours:
            continue  # user left this box blank
        glyphs[ch] = {
            "contours": contours,
            "width": x2 - x1,
            "height": y2 - y1,
        }
    return glyphs
