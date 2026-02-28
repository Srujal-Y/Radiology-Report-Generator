import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import io, sqlite3, base64, hashlib, uuid, traceback
from datetime import datetime
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
import torch
import torchvision.transforms as transforms
from torchvision import models

st.set_page_config(page_title="Radiology Report Studio", layout="wide")

# ---------------- Database ----------------
DB_PATH = "reports.db"
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created TEXT,
        hospital TEXT,
        doctor TEXT,
        doctor_license TEXT,
        reviewer TEXT,
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
        impression TEXT,
        treatment TEXT,
        verification_hash TEXT
    )""")
    conn.commit()
    return conn
conn = init_db()

# ---------------- Utilities ----------------
def image_to_bytes(img: Image.Image):
    buf = io.BytesIO()
    if img.mode != "RGB": img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()

def _wrap_text_to_lines(text, font_name, font_size, max_width):
    parts = []
    for paragraph in str(text).split("\n"):
        current = ""
        for word in paragraph.split():
            test = (current + " " + word).strip()
            if stringWidth(test, font_name, font_size) > max_width:
                if current: parts.append(current)
                current = word
            else:
                current = test
        if current: parts.append(current)
        if not paragraph.strip(): parts.append("")
    return parts

def make_qr_image(data):
    qr = qrcode.QRCode(border=1, box_size=10)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def save_report_to_db(meta, verification_hash=""):
    c = conn.cursor()
    c.execute("""INSERT INTO reports (
        created,hospital,doctor,doctor_license,reviewer,patient_name,patient_id,age,gender,blood_group,referring,
        exam_date,view,technique,history,vitals,meds,allergies,diagnosis,impression,treatment,verification_hash
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (
        datetime.utcnow().isoformat(),
        meta["hospital"], meta["doctor"], meta["doctor_license"], meta["reviewer"],
        meta["patient_name"], meta["patient_id"], meta["age"], meta["gender"], meta["blood_group"],
        meta["referring"], meta["exam_date"], meta["view"], meta["technique"],
        meta["history"], meta["vitals"], meta["meds"], meta["allergies"],
        meta["diagnosis"], meta["impression"], meta["treatment"], verification_hash
    ))
    conn.commit()
    return c.lastrowid

# ---------------- PDF Generation ----------------
def make_pdf(meta, images_bytes_list, logo_bytes=None, sig_doc_bytes=None, sig_rev_bytes=None,
             out_path="report.pdf", page_format="A4", orientation="portrait",
             add_watermark=True, watermark_text="CONFIDENTIAL – RADIOLOGY REPORT",
             embed_qr_footer=True, include_page_numbers=True):

    pagesz = A4
    if orientation=="landscape": pagesz = (A4[1], A4[0])
    w,h = pagesz
    c = canvas.Canvas(out_path, pagesize=pagesz)
    margin = 18*mm
    content_width = w - 2*margin
    line_height = 14
    report_seed = (meta["hospital"] + meta["patient_name"] + meta["patient_id"] + str(uuid.uuid4())).encode()
    verification_hash = hashlib.sha256(report_seed).hexdigest()
    y = h - margin

    def draw_footer():
        footer_y = 12*mm
        if include_page_numbers:
            c.setFont("Helvetica",9)
            c.setFillColor(colors.HexColor("#444444"))
            c.drawCentredString(w/2, footer_y, f"Page {c.getPageNumber()}")
        if embed_qr_footer:
            try:
                qr = ImageReader(make_qr_image(verification_hash))
                qrsz = 20*mm
                c.drawImage(qr, w-margin-qrsz, footer_y-4*mm, width=qrsz, height=qrsz, mask='auto')
            except: pass

    def draw_watermark():
        if not add_watermark: return
        c.saveState()
        c.setFont("Helvetica-Bold",48)
        c.setFillColor(colors.Color(0,0,0,alpha=0.06))
        c.translate(w/2,h/2)
        c.rotate(45)
        c.drawCentredString(0,0, watermark_text)
        c.restoreState()

    def block(title, text, bgcolor):
        nonlocal y
        if y < 60*mm:
            draw_footer(); draw_watermark(); c.showPage(); y = h - margin
        lines = _wrap_text_to_lines(text, "Helvetica", 11, content_width-16)
        box_height = (len(lines)+2)*line_height + 6
        c.setFillColor(bgcolor)
        c.rect(margin, y-box_height, content_width, box_height, fill=1)
        c.setFont("Helvetica-Bold",13); c.setFillColor(colors.black)
        c.drawString(margin+6, y-line_height, title)
        c.setFont("Helvetica",11)
        ty = y - 2*line_height
        for ln in lines:
            c.drawString(margin+10, ty, ln)
            ty -= line_height
        y -= box_height + 6

    # ---------------- Cover Page ----------------
    if logo_bytes or meta["hospital"]:
        c.setFillColor(colors.white)
        c.rect(0,0,w,h,fill=1)
        if logo_bytes:
            try:
                logo = ImageReader(io.BytesIO(logo_bytes))
                c.drawImage(logo, (w-60*mm)/2, h-80*mm, width=60*mm, height=60*mm, preserveAspectRatio=True)
            except: pass
        c.setFont("Helvetica-Bold",28)
        c.setFillColor(colors.HexColor("#0b5394"))
        c.drawCentredString(w/2, h-100*mm, meta["hospital"])
        c.setFont("Helvetica",16)
        c.drawCentredString(w/2, h-115*mm, "Radiology Diagnostic Report")
        draw_footer(); draw_watermark(); c.showPage()
        y = h - margin

    # ---------------- Patient Details ----------------
    patient_txt = f"Patient: {meta['patient_name']}\nPatient ID: {meta['patient_id']}\nAge: {meta['age']}  Gender: {meta['gender']}  Blood Group: {meta['blood_group']}\nReferring: {meta['referring']}\nExam Date: {meta['exam_date']}"
    block("Patient Details", patient_txt, colors.HexColor("#f7f7f7"))

    block("Clinical History / Indication", meta.get("history",""), colors.HexColor("#ffffff"))
    block("Vitals / Medications / Allergies", f"{meta.get('vitals','')}\nMedications: {meta.get('meds','')}\nAllergies: {meta.get('allergies','')}", colors.HexColor("#fbfbfb"))
    block("Diagnosis", meta.get("diagnosis",""), colors.HexColor("#fff2cc"))
    block("Impression (AI-Assisted / Auto-Generated)", meta.get("impression",""), colors.HexColor("#fff7e6"))
    block("Treatment / Recommendations", meta.get("treatment",""), colors.HexColor("#e2f0d9"))

    # ---------------- X-Ray Images ----------------
    for b in images_bytes_list:
        if y < 80*mm:
            draw_footer(); draw_watermark(); c.showPage(); y = h - margin
        try:
            img = Image.open(io.BytesIO(b))
            iw, ih = img.size
            max_w = content_width
            max_h = h - 2*margin - 60*mm
            scale = min(max_w/iw, max_h/ih, 1.0)
            disp_w = iw*scale
            disp_h = ih*scale
            c.drawImage(ImageReader(img), (w-disp_w)/2, y-disp_h, width=disp_w, height=disp_h)
            y -= disp_h + 10
        except: pass

    # ---------------- Signatures ----------------
    sig_y = 50*mm
    sig_w, sig_h = 50*mm, 20*mm
    if sig_doc_bytes:
        try:
            sig = ImageReader(io.BytesIO(sig_doc_bytes))
            c.drawImage(sig, margin, sig_y, width=sig_w, height=sig_h, mask='auto')
            c.setFont("Helvetica",10)
            c.drawString(margin, sig_y-12, f"Reporting Doctor: {meta.get('doctor','')}")
            c.drawString(margin, sig_y-24, f"License: {meta.get('doctor_license','')}")
        except: pass
    if sig_rev_bytes:
        try:
            sig = ImageReader(io.BytesIO(sig_rev_bytes))
            c.drawImage(sig, w/2, sig_y, width=sig_w, height=sig_h, mask='auto')
            c.setFont("Helvetica",10)
            c.drawString(w/2, sig_y-12, f"Reviewer: {meta.get('reviewer','')}")
        except: pass

    draw_footer(); draw_watermark(); c.showPage(); c.save()
    return out_path, verification_hash

# ---------------- AI Chest X-Ray Diagnosis ----------------
device = "cuda" if torch.cuda.is_available() else "cpu"
transform = transforms.Compose([
    transforms.Resize((224,224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])
])
model = models.resnet50(pretrained=True)
model.fc = torch.nn.Linear(model.fc.in_features, 5)
model = model.to(device)
model.eval()
LABELS = ["Pneumonia","COVID-19","Effusion","Nodule","Normal"]
def predict_multilabel(img_bytes):
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    inp = transform(img).unsqueeze(0).to(device)
    with torch.no_grad():
        out = torch.sigmoid(model(inp)).cpu().numpy()[0]
    return {LABELS[i]: float(out[i]) for i in range(len(LABELS))}

# ---------------- Streamlit ----------------
st.title("Radiology Report Studio")
with st.form("report_form", clear_on_submit=False):
    st.subheader("Hospital & Doctor Info")
    hospital=st.text_input("Hospital / Institution")
    doctor=st.text_input("Reporting Physician")
    doctor_license=st.text_input("Doctor License / Reg #")
    reviewer=st.text_input("Reviewer (optional)")
    logo_file=st.file_uploader("Upload Hospital Logo (optional)", type=None)

    st.subheader("Patient Info")
    patient_name=st.text_input("Patient Name")
    patient_id=st.text_input("Patient ID / MRN")
    age=st.text_input("Age")
    gender=st.selectbox("Gender", ["","Male","Female","Other"])
    blood_group=st.text_input("Blood Group")
    referring=st.text_input("Referring Physician")

    st.subheader("Clinical Info & Images")
    history=st.text_area("Clinical History / Indication", height=120)
    vitals=st.text_area("Recent Vitals (BP/HR/SpO2/Temp)", height=80)
    meds=st.text_area("Current Medications", height=80)
    allergies=st.text_input("Allergies")
    uploaded_files=st.file_uploader("Upload Chest X-Ray Images", type=None, accept_multiple_files=True)
    contrast=st.slider("Contrast",0.5,2.0,1.0,0.05)
    brightness=st.slider("Brightness",0.5,2.0,1.0,0.05)
    images_bytes_list=[]
    for file in uploaded_files:
        try:
            pil=Image.open(io.BytesIO(file.getvalue())).convert("L")
            pil=ImageOps.fit(pil,(1200,1200))
            pil=ImageEnhance.Contrast(pil).enhance(contrast)
            pil=ImageEnhance.Brightness(pil).enhance(brightness)
            images_bytes_list.append(image_to_bytes(pil))
            st.image(pil, caption=f"Preview: {file.name}", use_column_width=True)
        except: pass

    st.subheader("Signatures")
    sig_doc_file=st.file_uploader("Upload Doctor Signature", type=None)
    sig_rev_file=st.file_uploader("Upload Reviewer Signature", type=None)

    st.subheader("Diagnosis & Treatment")
    diagnosis_in=st.text_area("Diagnosis", height=140)
    impression_in=st.text_area("Impression (optional - auto-generated if blank)", height=80)
    treatment_in=st.text_area("Treatment / Recommendations", height=160)

    submitted=st.form_submit_button("Save Report & Generate PDF")
    if submitted:
        try:
            logo_bytes=image_to_bytes(Image.open(io.BytesIO(logo_file.getvalue()))) if logo_file else None
        except: logo_bytes=None
        sig_doc_bytes=image_to_bytes(Image.open(io.BytesIO(sig_doc_file.getvalue()))) if sig_doc_file else None
        sig_rev_bytes=image_to_bytes(Image.open(io.BytesIO(sig_rev_file.getvalue()))) if sig_rev_file else None

        if not impression_in and images_bytes_list:
            combined_pred=[]
            for b in images_bytes_list:
                res=predict_multilabel(b)
                for k,v in res.items():
                    if v>0.5: combined_pred.append(k)
            impression_in=", ".join(combined_pred) if combined_pred else "No acute findings"

        meta={
            "hospital":hospital,"doctor":doctor,"doctor_license":doctor_license,"reviewer":reviewer,
            "patient_name":patient_name,"patient_id":patient_id,"age":age,"gender":gender,
            "blood_group":blood_group,"referring":referring,"exam_date":str(datetime.utcnow().date()),
            "view":"","technique":"","history":history,"vitals":vitals,"meds":meds,"allergies":allergies,
            "diagnosis":diagnosis_in,"impression":impression_in,"treatment":treatment_in
        }

        pdf_path,verification_hash=make_pdf(meta, images_bytes_list, logo_bytes, sig_doc_bytes, sig_rev_bytes)
        rid=save_report_to_db(meta, verification_hash)
        st.success(f"Report Generated (ID {rid})")
        with open(pdf_path,"rb") as f:
            b64=base64.b64encode(f.read()).decode()
            st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="report.pdf">Download PDF</a>',unsafe_allow_html=True)

        if images_bytes_list:
            st.subheader("AI Automated Multi-Label Diagnosis")
            for i,b in enumerate(images_bytes_list):
                res=predict_multilabel(b)
                st.write(f"Image {i+1} Predictions:")
                for k,v in res.items():
                    st.write(f"{k}: {v:.2f}")