import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import io, os, base64, sqlite3, csv, traceback
from datetime import datetime

st.set_page_config(page_title="Radiology Report Studio", layout="wide", initial_sidebar_state="expanded")

DB_PATH = "reports.db"

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created TEXT,
        hospital TEXT,
        doctor TEXT,
        patient_name TEXT,
        patient_id TEXT,
        age TEXT,
        gender TEXT,
        blood_group TEXT,
        referring TEXT,
        exam_date TEXT,
        view TEXT,
        technique TEXT,
        history TEXT,
        vitals TEXT,
        meds TEXT,
        allergies TEXT,
        diagnosis TEXT,
        treatment TEXT,
        image BLOB
    )""")
    conn.commit()
    return conn

conn = init_db()

def save_report_to_db(meta, img_bytes):
    c = conn.cursor()
    c.execute("""INSERT INTO reports (
        created,hospital,doctor,patient_name,patient_id,age,gender,blood_group,referring,exam_date,view,technique,
        history,vitals,meds,allergies,diagnosis,treatment,image
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (
        datetime.utcnow().isoformat(),
        meta.get("hospital",""),
        meta.get("doctor",""),
        meta.get("patient_name",""),
        meta.get("patient_id",""),
        meta.get("age",""),
        meta.get("gender",""),
        meta.get("blood_group",""),
        meta.get("referring",""),
        meta.get("exam_date",""),
        meta.get("view",""),
        meta.get("technique",""),
        meta.get("history",""),
        meta.get("vitals",""),
        meta.get("meds",""),
        meta.get("allergies",""),
        meta.get("diagnosis",""),
        meta.get("treatment",""),
        img_bytes
    ))
    conn.commit()
    return c.lastrowid

def query_reports(limit=50):
    c = conn.cursor()
    c.execute("SELECT id, created, hospital, doctor, patient_name, exam_date FROM reports ORDER BY id DESC LIMIT ?", (limit,))
    return c.fetchall()

def fetch_report(report_id):
    c = conn.cursor()
    c.execute("SELECT * FROM reports WHERE id=?", (report_id,))
    return c.fetchone()

def image_to_bytes(img: Image.Image):
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()

def bytes_to_image(b):
    return Image.open(io.BytesIO(b))

def make_pdf(report_meta, img_bytes, out_path="report.pdf"):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    w, h = A4
    c = canvas.Canvas(out_path, pagesize=A4)
    c.setTitle("Radiology Report")
    margin = 40
    y = h - margin
    c.setFont("Helvetica-Bold", 16)
    header = report_meta.get("hospital") or "Hospital / Institution"
    c.drawString(margin, y, header)
    c.setFont("Helvetica", 10)
    sub = f"Reporting Physician: {report_meta.get('doctor','')}"
    c.drawString(margin, y-18, sub)
    c.line(margin, y-26, w-margin, y-26)
    y -= 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Patient Details")
    y -= 16
    c.setFont("Helvetica", 10)
    lines = [
        f"Name: {report_meta.get('patient_name','')}",
        f"Patient ID: {report_meta.get('patient_id','')}",
        f"Age: {report_meta.get('age','')}",
        f"Gender: {report_meta.get('gender','')}",
        f"Blood Group: {report_meta.get('blood_group','')}",
        f"Referring Physician: {report_meta.get('referring','')}",
        f"Exam Date: {report_meta.get('exam_date','')}",
        f"View: {report_meta.get('view','')}",
        f"Technique: {report_meta.get('technique','')}",
    ]
    for ln in lines:
        c.drawString(margin, y, ln)
        y -= 14
    y -= 8
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Clinical History")
    y -= 14
    c.setFont("Helvetica", 10)
    for paragraph in (report_meta.get("history") or "").split("\n"):
        text = c.beginText(margin, y)
        text.setFont("Helvetica", 10)
        text.textLines(paragraph)
        c.drawText(text)
        y -= (12 * (paragraph.count("\n")+1) + 6)
    y -= 6
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Imaging")
    y -= 14
    # place image on right side
    try:
        im = ImageReader(io.BytesIO(img_bytes))
        iw, ih = im.getSize()
        max_w = w/2 - margin
        max_h = h/3
        scale = min(max_w/iw, max_h/ih, 1.0)
        draw_w = iw*scale
        draw_h = ih*scale
        c.drawImage(im, w - margin - draw_w, y - draw_h + 30, width=draw_w, height=draw_h)
    except Exception:
        pass
    c.setFont("Helvetica", 10)
    c.drawString(margin, y, "Chest X-Ray (attached image)")
    y -= (max(150, draw_h if 'draw_h' in locals() else 150) + 10)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Diagnosis")
    y -= 14
    c.setFont("Helvetica", 10)
    for paragraph in (report_meta.get("diagnosis") or "").split("\n"):
        text = c.beginText(margin, y)
        text.setFont("Helvetica", 10)
        text.textLines(paragraph)
        c.drawText(text)
        y -= (12 * (paragraph.count("\n")+1) + 6)
    y -= 6
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Treatment / Recommendations")
    y -= 14
    c.setFont("Helvetica", 10)
    for paragraph in (report_meta.get("treatment") or "").split("\n"):
        text = c.beginText(margin, y)
        text.setFont("Helvetica", 10)
        text.textLines(paragraph)
        c.drawText(text)
        y -= (12 * (paragraph.count("\n")+1) + 6)
    c.showPage()
    c.save()
    return out_path

# Grammar correction: try language_tool_python, fallback to no-op
def grammar_check(text):
    try:
        import language_tool_python
        tool = language_tool_python.LanguageTool('en-US')
        matches = tool.check(text)
        corrected = language_tool_python.utils.correct(text, matches)
        return corrected
    except Exception:
        return text

# UI styling and mode
if 'mode' not in st.session_state:
    st.session_state.mode = "dark"

def apply_theme(mode):
    if mode == "dark":
        primary = "#0b5394"
        bg1 = "#071428"
        bg2 = "#071b2a"
        txt = "white"
    else:
        primary = "#0b5394"
        bg1 = "#f7fbff"
        bg2 = "#ffffff"
        txt = "#0b2540"
    css = f"""
    <style>
    .stApp {{ background: linear-gradient(160deg, {bg1}, {bg2}); color: {txt}; }}
    .card {{ background: rgba(255,255,255,0.02); padding:12px; border-radius:12px; }}
    .title {{ font-size:28px; font-weight:700; color:{primary}; }}
    .small-muted {{ color: #7a8a99; font-size:12px; }}
    .btn {{ background: linear-gradient(90deg, {primary}, #2e75b6); color: white; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

apply_theme(st.session_state.mode)

st.title("Radiology Report Studio")

with st.sidebar:
    st.header("Settings")
    mode = st.radio("Theme", ["dark", "light"], index=0 if st.session_state.mode=="dark" else 1)
    st.session_state.mode = mode
    apply_theme(mode)
    st.markdown("---")
    st.subheader("Database")
    if st.button("List recent reports"):
        rows = query_reports(100)
        if rows:
            for r in rows:
                st.markdown(f"**ID {r[0]}** — {r[4]} — {r[2]} — {r[1][:19]}")
        else:
            st.write("No reports yet.")
    if st.button("Export all reports (CSV)"):
        c = conn.cursor()
        c.execute("SELECT id, created, hospital, doctor, patient_name, patient_id, age, gender, blood_group, exam_date FROM reports")
        rows = c.fetchall()
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["id","created","hospital","doctor","patient_name","patient_id","age","gender","blood_group","exam_date"])
        writer.writerows(rows)
        b = out.getvalue().encode()
        b64 = base64.b64encode(b).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="reports_export.csv">Download CSV</a>'
        st.markdown(href, unsafe_allow_html=True)

# Main form
with st.form("report_form", clear_on_submit=False):
    st.subheader("Institution & Reporter")
    col1, col2 = st.columns([2,2])
    with col1:
        hospital = st.text_input("Hospital / Institution", value="My Hospital")
        doctor = st.text_input("Reporting Physician", value="Dr. Example")
    with col2:
        logo_file = st.file_uploader("Upload Hospital Logo (optional)", type=["png","jpg","jpeg"])
    st.markdown("---")
    st.subheader("Patient & Exam Details")
    c1, c2, c3 = st.columns([2,1,1])
    with c1:
        patient_name = st.text_input("Patient Name")
        patient_id = st.text_input("Patient ID / MRN")
        age = st.text_input("Age")
    with c2:
        gender = st.selectbox("Gender", ["", "Male", "Female", "Other"])
        blood_group = st.text_input("Blood Group")
        referring = st.text_input("Referring Physician")
    with c3:
        exam_date = st.date_input("Exam Date")
        view = st.selectbox("View", ["Unknown","PA","AP","Lateral","AP Supine","Oblique"])
        technique = st.text_input("Technique")
    st.markdown("---")
    st.subheader("Clinical Info")
    history = st.text_area("Clinical History / Indication", height=120)
    vitals = st.text_area("Recent Vitals (BP/HR/SpO2/Temp)", height=80)
    meds = st.text_area("Current Medications", height=80)
    allergies = st.text_input("Allergies")
    st.markdown("---")
    st.subheader("Image Upload & Preprocessing")
    file = st.file_uploader("Upload Chest X-Ray", type=["png","jpg","jpeg"])
    contrast = st.slider("Contrast", 0.5, 2.0, 1.0, 0.05)
    brightness = st.slider("Brightness", 0.5, 2.0, 1.0, 0.05)
    if file:
        try:
            pil = Image.open(file).convert("L")
            preview = ImageOps.fit(pil, (800,800))
            preview = ImageEnhance.Contrast(preview).enhance(contrast)
            preview = ImageEnhance.Brightness(preview).enhance(brightness)
            st.image(preview, caption="Preview (adjusted)", use_column_width=True)
        except Exception:
            st.error("Unable to open image preview.")
    st.markdown("---")
    st.subheader("Doctor's Diagnosis & Treatment (enter manually)")
    diagnosis_in = st.text_area("Diagnosis (type manually)", height=120)
    treatment_in = st.text_area("Treatment / Recommendations (type manually)", height=160)

    cola, colb = st.columns([1,1])
    with cola:
        grammar_button = st.form_submit_button("Apply Grammar Correction")
    with colb:
        submit_button = st.form_submit_button("Save Report & Generate PDF")

    if grammar_button:
        try:
            corrected_diag = grammar_check(diagnosis_in)
            corrected_treat = grammar_check(treatment_in)
            diagnosis_in = corrected_diag
            treatment_in = corrected_treat
            st.success("Grammar correction applied to diagnosis and treatment text.")
        except Exception as e:
            st.error(f"Grammar correction failed: {e}")

    if submit_button:
        try:
            if not patient_name:
                st.error("Patient name is required.")
            else:
                img_bytes = None
                if file:
                    pil2 = Image.open(file).convert("L")
                    pil2 = ImageOps.fit(pil2, (1200,1200))
                    pil2 = ImageEnhance.Contrast(pil2).enhance(contrast)
                    pil2 = ImageEnhance.Brightness(pil2).enhance(brightness)
                    img_bytes = image_to_bytes(pil2)
                meta = {
                    "hospital": hospital, "doctor": doctor,
                    "patient_name": patient_name, "patient_id": patient_id, "age": age, "gender": gender,
                    "blood_group": blood_group, "referring": referring, "exam_date": exam_date.isoformat(),
                    "view": view, "technique": technique, "history": history, "vitals": vitals, "meds": meds,
                    "allergies": allergies, "diagnosis": diagnosis_in, "treatment": treatment_in
                }
                rid = save_report_to_db(meta, img_bytes)
                pdf_path = f"report_{rid}.pdf"
                make_pdf(meta, img_bytes or b"", out_path=pdf_path)
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                b64 = base64.b64encode(pdf_bytes).decode()
                href = f'<a href="data:application/octet-stream;base64,{b64}" download="report_{rid}.pdf">Download PDF (report_{rid}.pdf)</a>'
                st.success("Report saved and PDF generated.")
                st.markdown(href, unsafe_allow_html=True)
        except Exception as e:
            st.error("Failed to save report or generate PDF.")
            st.text(traceback.format_exc())

st.markdown("---")
st.subheader("Recent reports")
rows = query_reports(10)
if rows:
    for r in rows:
        id_, created, hosp, doc, pname, edate = r
        cols = st.columns([0.1,1,1,1,1])
        cols[0].write(f"{id_}")
        cols[1].write(pname)
        cols[2].write(hosp)
        cols[3].write(doc)
        cols[4].write(created[:19])
        if cols[0].button("View", key=f"view_{id_}"):
            rep = fetch_report(id_)
            if rep:
                _, created, hospital, doctor, patient_name, patient_id, age, gender, blood_group, referring, exam_date, view, technique, history, vitals, meds, allergies, diagnosis, treatment, image_blob = rep
                st.markdown(f"### Report ID {id_} — {patient_name}")
                st.write(f"Hospital: {hospital} | Doctor: {doctor} | Created: {created}")
                st.write("**Clinical history**")
                st.write(history)
                st.write("**Diagnosis**")
                st.write(diagnosis)
                st.write("**Treatment**")
                st.write(treatment)
                if image_blob:
                    try:
                        st.image(bytes_to_image(image_blob), caption="Saved image", use_column_width=True)
                    except Exception:
                        st.write("Saved image corrupted or unreadable.")
else:
    st.write("No saved reports yet.")
