import os
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from werkzeug.utils import secure_filename

from crack_detection import detect_crack, save_image

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
OUTPUT_FOLDER = BASE_DIR / "outputs"

UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["OUTPUT_FOLDER"] = str(OUTPUT_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-development-secret")


def allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def safe_float(value, default=100.0):
    try:
        number = float(value)
        return number if number > 0 else default
    except (TypeError, ValueError):
        return default


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    image = request.files.get("image")
    if image is None or image.filename == "":
        flash("Please select or capture an image first.", "error")
        return redirect(url_for("index"))

    if not allowed_file(image.filename):
        flash("Invalid file type. Please use JPG, JPEG, or PNG.", "error")
        return redirect(url_for("index"))

    analysis_id = uuid.uuid4().hex[:12].upper()
    extension = image.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(f"{analysis_id}.{extension}")
    input_path = UPLOAD_FOLDER / filename
    image.save(input_path)

    pixels_per_cm = safe_float(request.form.get("pixels_per_cm"), 100.0)
    mode = request.form.get("detection_mode", "structural").lower()
    if mode not in {"sensitive", "standard", "structural"}:
        mode = "structural"

    try:
        # This is the single processing path for both uploaded and camera images.
        result = detect_crack(str(input_path), pixels_per_cm=pixels_per_cm, mode=mode, tile_size=640, overlap=80, use_tiling=True)

        original_filename = f"{analysis_id}_original.png"
        detected_filename = f"{analysis_id}_detected.png"
        original_path = OUTPUT_FOLDER / original_filename
        detected_path = OUTPUT_FOLDER / detected_filename

        save_image(result["original"], str(original_path))
        save_image(result["detected"], str(detected_path))

        # Save the actual result data for the report route.
        report_data = {
            "analysis_id": analysis_id,
            "date": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "original_filename": original_filename,
            "detected_filename": detected_filename,
            "length_cm": result["length_cm"],
            "width_cm": result["width_cm"],
            "area_cm2": result["area_cm2"],
            "severity": result["severity"],
            "severity_message": result["severity_message"],
            "pixels_per_cm": pixels_per_cm,
            "mode": result["mode"],
            "tiled": result["tiled"],
            "tile_size": result["tile_size"],
            "overlap": result["overlap"],
            "crack_count": result["crack_count"],
        }

        # A simple server-side text representation avoids a database dependency.
        # It is only used to build the downloadable report.
        import json
        with open(OUTPUT_FOLDER / f"{analysis_id}.json", "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        return render_template(
            "result.html",
            result=report_data,
        )

    except Exception as exc:
        # Remove a bad upload if processing failed.
        try:
            input_path.unlink(missing_ok=True)
        except Exception:
            pass
        flash(f"Image processing failed: {exc}", "error")
        return redirect(url_for("index"))


@app.route("/download-report/<analysis_id>")
def download_report(analysis_id):
    import json
    import html

    data_path = OUTPUT_FOLDER / f"{analysis_id}.json"
    if not data_path.exists():
        flash("Analysis report was not found.", "error")
        return redirect(url_for("index"))

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Generate a self-contained HTML report. It is downloadable and printable
    # to PDF from any modern browser without adding another dependency.
    original_url = url_for("static_output", filename=data["original_filename"], _external=True)
    detected_url = url_for("static_output", filename=data["detected_filename"], _external=True)

    html_report = render_template(
        "report.html",
        data=data,
        original_url=original_url,
        detected_url=detected_url,
    )

    report_path = OUTPUT_FOLDER / f"{analysis_id}_report.html"
    report_path.write_text(html_report, encoding="utf-8")

    return send_file(
        report_path,
        as_attachment=True,
        download_name=f"concrete_crack_report_{analysis_id}.html",
        mimetype="text/html",
    )


@app.route("/outputs/<path:filename>")
def static_output(filename):
    return send_file(OUTPUT_FOLDER / filename)


@app.errorhandler(413)
def too_large(_error):
    flash("Image is too large. Maximum allowed size is 10 MB.", "error")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
