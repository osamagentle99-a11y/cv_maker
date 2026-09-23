import os
import uuid
import re
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

    # Invalid value ke liye default template
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
# BUILD RESUME TEXT FOR ATS
# ==================================================

def build_resume_text(data):
    """
    CV data ko ATS checker ke liye plain text resume mein convert karta hai.
    """

    return f"""
Name: {data.get('name', '')}
Job Title: {data.get('job_title', '')}
Email: {data.get('email', '')}
Phone: {data.get('phone', '')}
LinkedIn: {data.get('linkedin', '')}

Professional Summary:
{data.get('summary', '')}

Skills:
{data.get('skills', '')}

Languages:
{data.get('languages', '')}

Education:
{data.get('education', '')}

Experience:
{data.get('experience', '')}

References:
{data.get('references', '')}
""".strip()


# ==================================================
# ATS CHECKING HELPER
# ==================================================

def calculate_ats_result(resume_text, job_description):
    """
    Resume aur Job Description ko compare karke ATS result calculate karta hai.
    """

    resume_text = (resume_text or "").strip()
    job_description = (job_description or "").strip()

    # --------------------------------------------------
    # STOP WORDS
    # --------------------------------------------------

    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "your",
        "you",
        "are",
        "our",
        "will",
        "have",
        "has",
        "been",
        "was",
        "were",
        "they",
        "their",
        "about",
        "into",
        "using",
        "use",
        "work",
        "working",
        "job",
        "role",
        "candidate",
        "years",
        "year",
        "required",
        "preferred",
        "responsibilities",
        "requirements",
        "skills",
        "ability",
        "strong",
        "good",
        "excellent",
        "knowledge",
        "experience",
        "must",
        "should",
        "can",
        "our",
        "you'll",
        "we",
        "be",
        "to",
        "of",
        "in",
        "on",
        "a",
        "an",
        "is",
        "as",
        "or",
        "at",
        "by"
    }

    # --------------------------------------------------
    # EXTRACT JOB KEYWORDS
    # --------------------------------------------------

    job_words = re.findall(
        r"\b[a-zA-Z][a-zA-Z0-9+#.-]*\b",
        job_description.lower()
    )

    job_keywords = []

    for word in job_words:
        if (
            len(word) >= 3
            and word not in stop_words
            and word not in job_keywords
        ):
            job_keywords.append(word)

    # --------------------------------------------------
    # RESUME TEXT
    # --------------------------------------------------

    resume_lower = resume_text.lower()

    # --------------------------------------------------
    # MATCHED / MISSING KEYWORDS
    # --------------------------------------------------

    matched_keywords = []
    missing_keywords = []

    for keyword in job_keywords:

        # Word/phrase presence check
        if keyword in resume_lower:
            matched_keywords.append(keyword)
        else:
            missing_keywords.append(keyword)

    # --------------------------------------------------
    # EMAIL VALIDATION
    # --------------------------------------------------

    email_pattern = (
        r"\b[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    )

    emails = re.findall(
        email_pattern,
        resume_text
    )

    email_status = "valid" if emails else "missing"

    # --------------------------------------------------
    # LINKEDIN VALIDATION
    # --------------------------------------------------

    linkedin_pattern = (
        r"(?:https?://)?"
        r"(?:www\.)?"
        r"linkedin\.com/in/"
        r"[A-Za-z0-9_-]+"
        r"/?"
    )

    linkedin_matches = re.findall(
        linkedin_pattern,
        resume_text,
        re.IGNORECASE
    )

    linkedin_status = (
        "valid" if linkedin_matches else "missing"
    )

    # --------------------------------------------------
    # ATS SCORE
    # --------------------------------------------------
    #
    # 80 points = Job-description keyword matching
    # 10 points = Email
    # 10 points = LinkedIn
    #

    if job_keywords:
        keyword_score = (
            len(matched_keywords)
            / len(job_keywords)
        ) * 80
    else:
        keyword_score = 0

    contact_score = 0

    if email_status == "valid":
        contact_score += 10

    if linkedin_status == "valid":
        contact_score += 10

    score = round(
        keyword_score + contact_score
    )

    # Safety: score always remains 0-100
    score = max(0, min(score, 100))

    return {
        "score": score,
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords,
        "emails": emails,
        "email_status": email_status,
        "linkedin_matches": linkedin_matches,
        "linkedin_status": linkedin_status
    }


# ==================================================
# HOME PAGE
# ==================================================

@app.route("/")
def home():
    return render_template("index.html")


# ==================================================
# ATS CHECKER
# ==================================================

@app.route("/ats-checker", methods=["GET", "POST"])
def ats_checker():

    if request.method == "POST":

        resume_text = request.form.get(
            "resume_text",
            ""
        ).strip()

        job_description = request.form.get(
            "job_description",
            ""
        ).strip()

        result = calculate_ats_result(
            resume_text,
            job_description
        )

        return render_template(
            "ats_checker.html",
            resume_text=resume_text,
            job_description=job_description,
            score=result["score"],
            matched_keywords=result["matched_keywords"],
            missing_keywords=result["missing_keywords"],
            emails=result["emails"],
            email_status=result["email_status"],
            linkedin_matches=result["linkedin_matches"],
            linkedin_status=result["linkedin_status"]
        )

    return render_template(
        "ats_checker.html"
    )


# ==================================================
# CREATE CV / PREVIEW
# ==================================================

@app.route("/create", methods=["GET", "POST"])
def create_cv():

    # --------------------------------------------------
    # OPEN CREATE PAGE
    # --------------------------------------------------

    if request.method == "GET":
        return render_template("create_cv.html")

    # --------------------------------------------------
    # FORM DATA
    # --------------------------------------------------

    data = get_cv_data()
    selected_template = data["template"]

    # --------------------------------------------------
    # ATS CHECKER FROM CREATE PAGE
    # --------------------------------------------------

    if request.form.get("action") == "ats":

        # If ATS form already contains resume text,
        # use that text.
        resume_text = request.form.get(
            "resume_text",
            ""
        ).strip()

        # If no resume text was submitted, build it
        # automatically from the CV fields.
        if not resume_text:
            resume_text = build_resume_text(data)

        job_description = request.form.get(
            "job_description",
            ""
        ).strip()

        result = calculate_ats_result(
            resume_text,
            job_description
        )

        return render_template(
            "ats_checker.html",
            resume_text=resume_text,
            job_description=job_description,
            score=result["score"],
            matched_keywords=result["matched_keywords"],
            missing_keywords=result["missing_keywords"],
            emails=result["emails"],
            email_status=result["email_status"],
            linkedin_matches=result["linkedin_matches"],
            linkedin_status=result["linkedin_status"],
            cv_data=data
        )

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
                print(
                    "Photo save error:",
                    error
                )

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

    # --------------------------------------------------
    # BASE URL FOR STATIC FILES
    # --------------------------------------------------

    base_url = (
        request.url_root.rstrip("/")
        + "/"
    )

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

    # --------------------------------------------------
    # FIX PROFILE PHOTO URL FOR PDF
    # --------------------------------------------------

    if data["photo"]:

        photo_url = (
            request.url_root.rstrip("/")
            + "/static/uploads/"
            + data["photo"]
        )

        html = html.replace(
            f"/static/uploads/{data['photo']}",
            photo_url
        )

    browser = None

    # ==================================================
    # CONVERT HTML TO PDF USING CHROMIUM
    # ==================================================

    try:

        with sync_playwright() as playwright:

            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-software-rasterizer"
                ]
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
                wait_until="domcontentloaded",
                timeout=15000
            )

            page.wait_for_timeout(800)

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
            browser = None

    except Exception as error:

        print(
            "PDF generation error:",
            repr(error)
        )

        if browser:

            try:
                browser.close()
            except Exception:
                pass

        return (
            "PDF generate nahi ho saka. "
            "Please dobara try karein.",
            500
        )

    # ==================================================
    # SEND PDF
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
