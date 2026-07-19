import os
import uuid
from flask import Flask, render_template, request, send_file, redirect, url_for, flash

import template_generator
import glyph_processor
import font_builder

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = "dev-only-change-me"  # only used to flash messages, not for anything sensitive


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/template")
def download_template():
    template_path = os.path.join(OUTPUT_DIR, "template.png")
    layout_path = os.path.join(OUTPUT_DIR, "template_layout.json")
    if not (os.path.exists(template_path) and os.path.exists(layout_path)):
        template_generator.generate()
    return send_file(template_path, as_attachment=True, download_name="handwriting_template.png")


@app.route("/process", methods=["POST"])
def process():
    if "scan" not in request.files or request.files["scan"].filename == "":
        flash("Please choose a photo/scan of your filled-in worksheet.")
        return redirect(url_for("index"))

    family_name = request.form.get("font_name", "MyHandwriting").strip() or "MyHandwriting"

    scan_file = request.files["scan"]
    job_id = uuid.uuid4().hex[:10]
    scan_path = os.path.join(UPLOAD_DIR, f"{job_id}_{scan_file.filename}")
    scan_file.save(scan_path)

    layout_path = os.path.join(OUTPUT_DIR, "template_layout.json")
    if not os.path.exists(layout_path):
        template_generator.generate()

    try:
        glyphs = glyph_processor.extract_glyphs(scan_path, layout_path)
    except ValueError as e:
        flash(str(e))
        return redirect(url_for("index"))

    if len(glyphs) < 5:
        flash(
            f"Only found {len(glyphs)} legible letters. Make sure the photo is well-lit, "
            "flat, and all 4 corner squares are visible, then try again."
        )
        return redirect(url_for("index"))

    font_path = os.path.join(OUTPUT_DIR, f"{job_id}_{family_name}.ttf")
    font_builder.build_font(glyphs, font_path, family_name=family_name)

    return render_template(
        "result.html",
        font_file=os.path.basename(font_path),
        letters_found=sorted(glyphs.keys()),
        total_letters=len(template_generator.CHARACTERS),
        family_name=family_name,
    )


@app.route("/download/<path:filename>")
def download_font(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        flash("That font file was not found -- it may have expired. Please regenerate it.")
        return redirect(url_for("index"))
    return send_file(path, as_attachment=True, download_name=filename.split("_", 1)[-1])


if __name__ == "__main__":
    # make sure the template exists on first run
    if not os.path.exists(os.path.join(OUTPUT_DIR, "template.png")):
        template_generator.generate()
    app.run(debug=True, host="0.0.0.0", port=5000)
