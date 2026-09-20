import os
import uuid
from io import BytesIO

from flask import (
    Flask,
    render_template,
    request,
    send_file
)

from werkzeug.utils import secure_filename

from playwright.sync_api import sync_playwright


app = Flask(__name__)


# ==================================================
# UPLOAD CONFIGURATION
# ==================================================

UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads"
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "jfif"
}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ==================================================
# TEMPLATE CONFIGURATION
# ==================================================

ALLOWED_TEMPLATES = {
    "modern_blue": "cv_templates/modern_blue.html",
    "minimal": "cv_templates/minimal.html",
    "dark_executive": "cv_templates/dark_executive.html"
}


def get_template_name(template_value):
    """
    Template value ko safe HTML template path mein convert karta hai.
    """

    template_value = (template_value or "modern_blue").strip()

    # Agar value already template path ho
    for template_key, template_path in ALLOWED_TEMPLATES.items():
        if template_value == template_path:
            return template_key, template_path

    # Agar sirf template key ho
    if template_value in ALLOWED_TEMPLATES:
        return (
            template_value,
            ALLOWED_TEMPLATES[template_value]
        )

    return (
        "modern_blue",
        ALLOWED_TEMPLATES["modern_blue"]
    )


# ==================================================
# FORM DATA HELPER
# ==================================================

def get_cv_data():
    """
    Form se CV ka complete data collect karta hai.
    """

    selected_template, selected_template_file = get_template_name(
        request.form.get("template", "modern_blue")
    )

    data = {
        "name": request.form.get("name", "").strip(),
        "email": request.form.get("email", "").strip(),
        "phone": request.form.get("phone", "").strip(),
        "job_title": request.form.get("job_title", "").strip(),
        "summary": request.form.get("summary", "").strip(),
        "skills": request.form.get("skills", "").strip(),
        "languages": request.form.get("languages", "").strip(),
        "education": request.form.get("education", "").strip(),
        "experience": request.form.get("experience", "").strip(),
        "linkedin": request.form.get("linkedin", "").strip(),
        "references": request.form.get("references", "").strip(),
        "template": selected_template,
        "template_file": selected_template_file,
        "photo": request.form.get("photo", "").strip()
    }

    return data


# ==================================================
# HOME PAGE
# ==================================================

@app.route("/")
def home():
    return render_template("index.html")


# ==================================================
# CREATE CV / PREVIEW
# ==================================================

@app.route("/create", methods=["GET", "POST"])
def create_cv():

    if request.method == "GET":
        return render_template("create_cv.html")

    # --------------------------------------------------
    # FORM DATA
    # --------------------------------------------------

    data = get_cv_data()

    selected_template = data["template"]

    # ==================================================
    # PROFILE PHOTO UPLOAD
    # ==================================================

    if selected_template == "dark_executive":

        photo_file = request.files.get("photo")

        if (
            photo_file
            and photo_file.filename
            and allowed_file(photo_file.filename)
        ):

            original_filename = secure_filename(
                photo_file.filename
            )

            extension = os.path.splitext(
                original_filename
            )[1].lower()

            unique_filename = (
                f"{uuid.uuid4().hex}{extension}"
            )

            photo_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                unique_filename
            )

            try:
                photo_file.save(photo_path)

                data["photo"] = unique_filename

            except Exception as error:
                print("Photo save error:", error)
                data["photo"] = ""

    # ==================================================
    # RENDER SELECTED TEMPLATE
    # ==================================================

    return render_template(
        data["template_file"],
        data=data
    )


# ==================================================
# PDF DOWNLOAD
# ==================================================

@app.route("/download", methods=["POST"])
def download_cv():

    # --------------------------------------------------
    # GET DATA FROM PREVIEW FORM
    # --------------------------------------------------

    data = get_cv_data()

    # --------------------------------------------------
    # SAFE PHOTO FILENAME
    # --------------------------------------------------

    if data["photo"]:
        data["photo"] = os.path.basename(
            data["photo"]
        )

    # --------------------------------------------------
    # RENDER SAME HTML TEMPLATE
    # --------------------------------------------------

    html = render_template(
        data["template_file"],
        data=data
    )

    # Browser ke static files, images aur CSS load karne
    # ke liye base URL add kar rahe hain.
    base_url = request.url_root

    if "<head>" in html:

        html = html.replace(
            "<head>",
            f'<head><base href="{base_url}">',
            1
        )

    else:

        html = (
            f'<base href="{base_url}">'
            + html
        )

    # ==================================================
    # CONVERT HTML TO PDF USING CHROMIUM
    # ==================================================

    try:

        with sync_playwright() as playwright:

            browser = playwright.chromium.launch(
                headless=True
            )

            page = browser.new_page(
                viewport={
                    "width": 1200,
                    "height": 1600
                },
                device_scale_factor=1
            )

            page.set_content(
                html,
                wait_until="networkidle"
            )

            # Browser preview jaisa hi PDF generate hoga
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,

                margin={
                    "top": "0",
                    "right": "0",
                    "bottom": "0",
                    "left": "0"
                }
            )

            browser.close()

    except Exception as error:

        print("PDF generation error:", error)

        return (
            "PDF generate nahi ho saka. "
            "Terminal mein 'playwright install chromium' run karein.",
            500
        )

    # ==================================================
    # SEND PDF TO USER
    # ==================================================

    return send_file(
        BytesIO(pdf_bytes),
        as_attachment=True,
        download_name="professional_cv.pdf",
        mimetype="application/pdf"
    )


# ==================================================
# RUN APP
# ==================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )