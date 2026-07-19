# Handwriting → Font

Turns a photo of your own filled-in worksheet into a real, installable
`.ttf` font — no API keys, no paid services, no training data required.

## How it works (and why there's no "AI training" step)

True freeform cursive segmentation (finding where one connected letter
ends and the next begins in an arbitrary photo) needs a trained deep
learning model and lots of labeled data — not realistic to spin up for
free in a personal project. So instead this uses the same trick real
handwriting-font tools (like Calligraphr) use:

1. **`template_generator.py`** creates a printable worksheet: one clearly
   labeled box per character (a–z, A–Z), plus 4 solid black squares in
   the corners.
2. You print it, write **one letter per box** in your natural cursive —
   with the pen touching the baseline at the start/end of the stroke,
   like it would mid-word — then photograph/scan it.
3. **`glyph_processor.py`** finds the 4 corner squares (searched
   independently per corner, so it can't be confused by handwriting),
   uses them to perspective-correct the photo back to the template's
   exact layout, then crops each box by its known coordinates. Because
   we control the layout, there's no fragile "where is each letter"
   guessing involved.
4. Each cropped box is thresholded and traced into vector polygon
   outlines (correctly keeping "holes" for closed loops, e.g. inside a
   lowercase `a`, `e`, `o`).
5. **`font_builder.py`** feeds those outlines into `fontTools` to build
   a real `.ttf`, one glyph per character, mapped to its keyboard key.

Because each glyph already has the pen-in/pen-out strokes baked in at a
consistent baseline, typed letters visually flow into each other close
enough to read as cursive — without needing OpenType contextual-joining
rules.

### Honest limitations
- Each letter is a **single fixed glyph** — it won't reshape based on
  neighboring letters the way true joined cursive does (that would
  require building "initial/medial/final" contextual forms, similar to
  how Arabic script fonts work, using OpenType `calt`/`curs` features —
  a solid v2 upgrade, and the per-pair combo images you mentioned
  — Aa, ab, ac… — are exactly the right raw material for that).
- Outlines are straight-line polygons (from `cv2.approxPolyDP`), so
  strokes look slightly faceted rather than perfectly smooth. Swapping
  in a Bezier-curve fit would smooth this out.
- Marker detection assumes reasonable photo quality (flat page, decent
  lighting, all 4 corners visible).

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000

## Project structure
```
app.py                 Flask routes (upload, process, download)
template_generator.py  Builds the printable worksheet + its layout JSON
glyph_processor.py     Perspective-correct scan → crop → vectorize
font_builder.py         Vector outlines → real .ttf via fontTools
templates/              HTML pages
```

## Extending it (combo-pair joining)
To add real joined cursive later:
1. Generate a second worksheet with 2-letter combo boxes (as you
   originally described).
2. Extract the joining stroke by diffing the combo glyph against the
   two isolated glyphs.
3. Build "final" and "initial" glyph variants per letter and wire up an
   OpenType `calt` feature (via `fontTools.feaLib`) so Word/etc.
   automatically substitutes the joined forms based on neighboring
   letters — the same mechanism Arabic script fonts use for letter
   shaping.
